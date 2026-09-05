"""make seed — 3 residents × 14 days (2 shifts/day) + 1 acute incident on day 12 → records/{patient_id}.

Every seeded line goes through the same gates as production: observations are extracted by the
same Intake lexicon, compared to baseline by the same comparator, checked by the same red-flag
rules, and written only via record.write_timeline as approved + confirmed_by nurse.
"""

from __future__ import annotations

import json
import random
import shutil
import sys
from datetime import date, datetime, timedelta, timezone

TPE = timezone(timedelta(hours=8))
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "apps" / "api"))

from agents.comparator import compare  # noqa: E402
from core.ids import new_id  # noqa: E402
from core.llm import MockLLM  # noqa: E402  (seed fixtures use the deterministic template double)
from core.settings import get_settings  # noqa: E402
from graphs.path_a import ROUTE_LABELS, compile_incident  # noqa: E402
from ingest import doctor_order, vitals as vitals_ingest  # noqa: E402
from ingest.lexicon import extract_with_lexicon  # noqa: E402
from record import care_circle  # noqa: E402
from record.store import RecordStore  # noqa: E402
from record_schema import (  # noqa: E402
    ISBAR,
    AllergyIntolerance,
    LifeEvent,
    Baseline,
    BaselineDelta,
    BaselineEntry,
    CareCircleMember,
    CaregiverSection,
    Condition,
    Contact,
    Encounter,
    Facility,
    FollowUp,
    MedicationStatement,
    MinimalSBAR,
    Notification,
    NurseSection,
    Observation,
    OnsiteAssessment,
    Order,
    OrderFollowUp,
    Profile,
    Provenance,
    Vitals,
)
from red_flags.rules import RedFlagInput, evaluate  # noqa: E402


_ZH_NUM = ["零", "一", "兩", "三", "四", "五", "六", "七", "八", "九", "十"]


def _intake_phrase(rng: random.Random, v: float) -> str:
    n = max(0, min(10, round(v * 10)))
    table = {
        10: ["飯都吃完", "三餐都吃完", "吃得很好，都吃完"],
        9: ["吃了九分", "差不多都吃完，剩一點"],
        8: ["吃了八分", "吃八分左右"],
        7: ["吃了七分", "吃七分左右"],
        6: ["吃六分", "吃了六分"],
        5: ["只吃一半", "吃一半"],
        4: ["吃四分", "吃不到一半"],
        3: ["吃三分", "只吃三分"],
    }
    return rng.choice(table.get(n, ["只吃幾口"]))


def _sleep_phrase(rng: random.Random, n: int) -> str:
    table = {
        0: ["睡得好，沒起來", "一覺到天亮"],
        1: ["晚上起來一次上廁所", "晚上起來一次"],
        2: ["晚上起來兩次", "晚上起來兩次上廁所"],
        3: ["晚上起來三次", "晚上起來三次，說睡不著"],
        4: ["晚上起來四次，睡不好", "晚上起來四次"],
    }
    return rng.choice(table.get(min(n, 5), ["晚上起來五次，幾乎沒睡"]))


def generate_days(story: dict, n_days: int, seed: int) -> list[list[str]]:
    """Realistic 14-day curves with seeded jitter (no two-value alternation)."""
    rng = random.Random(seed)
    i0, i1 = story["intake"]
    s0, s1 = story["sleep"]
    w0, w1 = story["water"]
    days: list[list[str]] = []
    for i in range(n_days):
        f = i / max(n_days - 1, 1)
        intake = max(0.1, min(1.0, i0 + (i1 - i0) * f + rng.gauss(0, 0.06)))
        sleep = max(0, min(5, round(s0 + (s1 - s0) * f + rng.gauss(0, 0.55))))
        water = rng.randint(w0, w1)
        day = f"{_intake_phrase(rng, intake)}，喝了{_ZH_NUM[water]}杯水"
        if rng.random() < 0.6:
            day += f"，{rng.choice(story['extras'])}"
        night = _sleep_phrase(rng, sleep)
        days.append([day, night])
    return days


def _dt(d: date, hhmm: str) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime(d.year, d.month, d.day, h, m, tzinfo=TPE)


def seed(root: Path | None = None, quiet: bool = False) -> RecordStore:
    data = json.loads((HERE / "residents.json").read_text(encoding="utf-8"))
    root = root or get_settings().records_root
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    store = RecordStore(root)
    nurses = data["nurses"]
    day1 = date.fromisoformat(data["day1"])
    last_round = date.fromisoformat(data["last_round_date"])
    identities: dict = dict(data["identities"])
    for r in data["residents"]:
        identities[r["patient_id"]] = {"role": "patient", "name": r["code_name"]}
        fam = r["emergency_contacts"][0]
        identities[r["family_member_id"]] = {
            "role": "family", "name": f"{fam['name']}（{fam['relation']}）", "patient_id": r["patient_id"],
        }

    for r in data["residents"]:
        pid = r["patient_id"]
        lang = r["caregiver_language"]
        nurse = r["primary_nurse"]
        profile = Profile(
            patient_id=pid,
            health_id=r["health_id"],
            code_name=r["code_name"],
            sex=r["sex"],
            birth_year=r["birth_year"],
            room=r["room"],
            one_liner=r.get("one_liner", ""),
            conditions=[Condition(**c) for c in r["conditions"]],
            allergies=[AllergyIntolerance(**a) for a in r["allergies"]],
            medications=[MedicationStatement(**m) for m in r["medications"]],
            dnr=r["dnr"],
            emergency_contacts=[Contact(**c) for c in r["emergency_contacts"]],
            contract_facility=Facility(**r["contract_facility"]),
            caregiver_code_name=r["caregiver_code_name"],
            caregiver_language=lang,
            primary_nurse=nurse,
        )
        b_ts = _dt(last_round, "10:00")
        b_prov = Provenance(source="nurse_confirmed", author=nurse, confirmed_by=nurse, ts=b_ts)
        baseline = Baseline(
            entries=[
                BaselineEntry(
                    dimension=dim,  # type: ignore[arg-type]
                    value=spec["value"],
                    description=spec["description"],
                    valid_from=last_round,
                    set_by="nurse_confirmed",
                    confirmed_by=nurse,
                    provenance=b_prov,
                )
                for dim, spec in r["baseline"].items()
            ],
            vitals_usual=Vitals(**r["vitals_usual"]),
        )
        store.init_record(profile, baseline)
        _seed_care_circle(store, profile, r, data, identities)
        _seed_history(store, profile, r.get("history", []), nurses)

        # --- last round: Encounter + Order (with follow-up status for RoundPage §③) ------------
        o_prov = Provenance(source="doctor_ordered", author=nurses["doctor"], confirmed_by=nurse, ts=b_ts)
        enc_id, ord_id = new_id("enc", b_ts), new_id("ord", b_ts)
        items = doctor_order.parse_order(r["last_order"]["text"])
        store.write_timeline(
            pid,
            Encounter(
                id=enc_id, patient_id=pid, ts=b_ts, status="approved", confirmed_by=nurse, provenance=o_prov,
                encounter_type="round", doctor=nurses["doctor"], summary=f"巡診：{r['last_order']['text'][:50]}",
                order_ids=[ord_id],
            ),
        )
        store.write_timeline(
            pid,
            Order(
                id=ord_id, patient_id=pid, ts=b_ts + timedelta(minutes=5), status="approved", confirmed_by=nurse,
                provenance=o_prov, doctor=nurses["doctor"], raw_text=r["last_order"]["text"], items=items,
                encounter_id=enc_id, follow_up=OrderFollowUp(**r["last_order"]["follow_up"]),
            ),
        )

        # --- 14 days × 2 shifts -----------------------------------------------------------------
        recent: list[Observation] = []
        incident_cfg = r.get("incident")
        days = generate_days(r["story"], 14, seed={"P001": 41, "P002": 42, "P003": 43}[pid])
        if incident_cfg:
            days[incident_cfg["day"] - 1][1] = "INCIDENT"
        for i, (day_text, night_text) in enumerate(days, start=1):
            d = day1 + timedelta(days=i - 1)
            for shift, text, hhmm in (("day", day_text, "08:30"), ("night", night_text, "20:30")):
                if text == "INCIDENT":
                    _seed_incident(store, profile, baseline, recent, incident_cfg, d, nurses, lang)
                    continue
                ts = _dt(d, hhmm)
                obs = extract_with_lexicon(text, lang, ts=ts)
                deltas = compare(obs, baseline, recent, d)
                rf = evaluate(
                    RedFlagInput(observation=obs, vitals=None, baseline_vitals=baseline.vitals_usual,
                                 on_anticoagulant=profile.on_anticoagulant)
                )
                assert not rf.notify_now, f"seed sentence unexpectedly red: {text}"
                sbar = MockLLM().minimal_sbar(obs, deltas)
                sbar.status, sbar.confirmed_by = "approved", nurse
                entry = Observation(
                    id=new_id("obs", ts), patient_id=pid, ts=ts, status="approved", confirmed_by=nurse,
                    provenance=Provenance(source="nurse_confirmed", author=nurse, confirmed_by=nurse, ts=ts,
                                          language_original=lang),
                    shift=shift, observation=obs, deltas=deltas, minimal_sbar=sbar,
                    vitals=vitals_ingest.measure(pid, d, shift), red_flags=rf,
                )
                store.write_timeline(pid, entry)
                recent.append(entry)
        if not quiet:
            n = len(store.load_timeline(pid))
            print(f"seeded {pid} {profile.code_name}: {n} timeline entries, {len(store.load_documents(pid))} documents")
    care_circle_save = getattr(care_circle, "save_identities")
    care_circle_save(identities)
    return store


def _seed_history(store, profile, history: list[dict], nurses: dict) -> None:
    """Lifelong events (VISION §7): imported from discharge summaries / prior records (demo seed),
    written as approved entries with the source facility in provenance."""
    for h in history:
        ts = _dt(date.fromisoformat(h["date"]), "10:00")
        store.write_timeline(
            profile.patient_id,
            LifeEvent(
                id=new_id("evt", ts), patient_id=profile.patient_id, ts=ts, status="approved",
                confirmed_by=nurses["head"],
                provenance=Provenance(source="doctor_ordered", author=h["facility"], confirmed_by=nurses["head"], ts=ts),
                event_type=h["type"], title=h["title"], summary=h.get("summary", ""), facility=h["facility"],
                ended=date.fromisoformat(h["ended"]) if h.get("ended") else None,
            ),
        )


def _seed_care_circle(store, profile, r, data, identities) -> None:
    """Patient-owned access (VISION §15–18): the person, one family member, the facility's
    caregivers, nurses and the visiting doctor — each with a scope subset, all granted by the
    person (or their family as proxy)."""
    pid, hid = profile.patient_id, profile.health_id
    t0 = _dt(date.fromisoformat(data["last_round_date"]), "09:00")
    fam_id = r["family_member_id"]
    rows: list[tuple[str, str, str]] = [(pid, "patient", profile.code_name), (fam_id, "family", identities[fam_id]["name"])]
    rows += [(k, v["role"], v["name"]) for k, v in identities.items() if v["role"] in ("caregiver", "nurse", "doctor")]
    for member_id, role, name in rows:
        care_circle.grant(
            pid,
            CareCircleMember(
                health_id=hid, member_id=member_id, name=name, role=role,
                scopes=care_circle.DEFAULT_SCOPES[role], valid_from=t0,
                valid_to=None if role != "doctor" else _dt(date.fromisoformat(data["last_round_date"]) + timedelta(days=365), "09:00"),
                granted_by=pid if role == "patient" else fam_id if role == "family" else pid,
            ),
        )


def _seed_incident(store, profile, baseline, recent, cfg, d, nurses, lang) -> None:
    """Day-12 acute incident for P001, built with the same compiler the Path A graph uses."""
    pid = profile.patient_id
    nurse = profile.primary_nurse
    ts = _dt(d, cfg["time"])
    obs = extract_with_lexicon(cfg["text"], lang, ts=ts)
    deltas: list[BaselineDelta] = compare(obs, baseline, recent, d)
    rf_pre = evaluate(RedFlagInput(observation=obs, vitals=None, baseline_vitals=baseline.vitals_usual,
                                   on_anticoagulant=profile.on_anticoagulant))
    assert rf_pre.notify_now, "seed incident must trip a red flag (fall + anticoagulant)"
    oa = OnsiteAssessment(
        vitals=Vitals(**cfg["onsite"]["vitals"], measured_by=nurse, ts=ts + timedelta(minutes=8)),
        consciousness=cfg["onsite"]["consciousness"], wound=cfg["onsite"]["wound"], notes=cfg["onsite"]["notes"],
        assessed_by=nurse, ts=ts + timedelta(minutes=8),
    )
    rf = evaluate(RedFlagInput(observation=obs, vitals=oa.vitals, baseline_vitals=baseline.vitals_usual,
                               on_anticoagulant=profile.on_anticoagulant))
    recent_lines = [f"{o.ts.date()} {o.minimal_sbar.s[:50] if o.minimal_sbar else o.observation.raw_text[:50]}" for o in recent[-4:]]
    isbar: ISBAR = MockLLM().draft_isbar(profile, baseline, obs, deltas, recent_lines)
    isbar.author = "nurse"
    isbar.nurse_assessment = cfg["nurse_assessment"]
    isbar.nurse_recommendation = cfg["nurse_recommendation"]
    isbar.status, isbar.confirmed_by, isbar.confirmed_at = "approved", nurse, ts + timedelta(minutes=14)
    cs = CaregiverSection(
        raw_text=obs.raw_text, language=lang, translation_zh=obs.translation_zh, domains=obs.domains,
        seems_different=True, incident_flags=obs.incident_flags, followups=obs.followups, unknown=obs.unknown,
        provenance=Provenance(source="caregiver_said", author=profile.caregiver_code_name, ts=ts, language_original=lang),
    )
    ns = NurseSection(onsite_assessment=oa, isbar=isbar, confirmed_by=nurse, confirmed_at=ts + timedelta(minutes=14))
    route = cfg["route"]
    entry, doc = compile_incident(
        profile=profile, obs=obs, caregiver_section=cs, nurse_section=ns, red_flags=rf, route=route,
        nurse_id=nurse, ts=ts + timedelta(minutes=15), generated_from=[o.id for o in recent[-6:]],
    )
    from agents.subagents import handoff_packager

    hp = handoff_packager.package(profile, baseline, isbar, [entry.id, *entry.related_ids], route, nurse)
    hp.generated_at = ts + timedelta(minutes=16)
    doc.notifications = [
        Notification(to="nurse", channel="screen", content="【紅燈】" + "；".join(f for h in rf_pre.hits for f in h.facts),
                     status="displayed_only", sent_at=ts + timedelta(minutes=1)),
        Notification(to="hospital", channel="phone", content=f"{ROUTE_LABELS[route]}：電話交班（通話版 ISBAR）",
                     status="displayed_only", sent_at=ts + timedelta(minutes=20)),
        Notification(to="family", channel="line", content=cfg["family_message"], status="displayed_only",
                     approved_by=nurse, sent_at=ts + timedelta(minutes=25)),
    ]
    fu_q = {"id": "Bagaimana keadaannya sekarang? Sudah lebih baik?"}.get(lang, "他現在怎麼樣？有比較好嗎？")
    doc.follow_up = FollowUp(due_at=ts + timedelta(hours=12), question=fu_q, answer=cfg.get("follow_up_answer"),
                             answered_at=ts + timedelta(hours=12, minutes=5), set_by=nurse)
    store.write_timeline(pid, entry)
    store.write_document(pid, doc)
    store.write_document(pid, hp)
    print(f"  seeded incident {entry.id} ({entry.incident_kind}) with IncidentFile {doc.id} + HandoffPage {hp.id}")


if __name__ == "__main__":
    s = seed()
    print(f"records at {s.root}: {s.list_patients()}")
