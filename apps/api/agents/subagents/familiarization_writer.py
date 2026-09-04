"""familiarization_writer — the RoundPage is WRITTEN by the subagent (the model).

Code provides facts (`build_context`) and assembles/validates what the subagent submits
(`validate_and_assemble`): ① who, ② only the dimensions that changed (each sentence cites
1–3 timeline entries, shown as a clickable「N 筆紀錄」link, never raw ids), ③ last orders
done/effective, ④ questions only. The chart is the two changed dimensions.

`draft_from_facts` is the MODEL_PROVIDER=mock test double (deterministic templates) so the
graphs can be tested without a key; production never uses it (no silent fallback).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field
from record_schema import (
    DIMENSION_LABELS,
    OrderFollowUpLine,
    Provenance,
    RoundPage,
    TrendLine,
    TrendReport,
)

from agents.subagents import trend_analyzer
from core.ids import new_id
from core.llm import BANNED_DIAGNOSTIC_TERMS, scrub_clinical_language
from record.store import get_store

MAX_LINES = 22


class ChangeLine(BaseModel):
    dimension: str
    text: str = Field(description="一句話，引用照護者原話，說明變化與時間")
    evidence_refs: list[str] = Field(
        default_factory=list, description="1–3 筆 timeline id（從 context.evidence 挑）"
    )


class FollowUpLine(BaseModel):
    order_id: str
    text: str
    done: bool | None = None
    effective: bool | None = None
    note: str = ""


class RoundPageSubmission(BaseModel):
    who: str = Field(description="① 一句話的人：這是誰、平常怎樣、這個月看什麼")
    changes: list[ChangeLine] = Field(
        default_factory=list, description="② 只寫 changed_dimensions 裡的維度"
    )
    no_change_note: str | None = Field(default=None, description="沒有變化時的一句話")
    order_followup: list[FollowUpLine] = Field(default_factory=list, description="③")
    questions: list[str] = Field(default_factory=list, description="④ 問句，2–4 條")


def build_context(patient_id: str, since: date, until: date | None = None) -> dict[str, Any]:
    """Facts for the writer: profile, baseline, changed dimensions + evidence, incidents, orders."""
    store = get_store()
    until = until or datetime.now(UTC).date()
    profile = store.load_profile(patient_id)
    baseline = store.load_baseline(patient_id)
    obs = store.load_timeline(patient_id, since=since, kinds={"observation"})
    inc = store.load_timeline(patient_id, since=since, kinds={"incident"})
    report = trend_analyzer.analyze(
        patient_id, obs, [e.id for e in inc], since, until, baseline=baseline
    )  # type: ignore[arg-type]
    week = trend_analyzer.analyze(
        patient_id,
        obs,
        [e.id for e in inc],
        max(since, until - timedelta(days=6)),
        until,
        baseline=baseline,
    )  # type: ignore[arg-type]
    changed = {line.dimension: line for line in report.lines if line.is_abnormal}
    for line in week.lines:
        if line.is_abnormal and line.dimension not in changed:
            changed[line.dimension] = line
    evidence: dict[str, list[dict[str, Any]]] = {}
    for o in obs:
        for dim, dv in o.observation.domains.items():
            if dim in changed:
                evidence.setdefault(dim, []).append(
                    {
                        "id": o.id,
                        "date": o.ts.date().isoformat(),
                        "quote": dv.raw_quote,
                        "value": dv.value,
                    }
                )
    for dim in evidence:
        evidence[dim] = evidence[dim][-6:]
    orders = [o for o in store.load_timeline(patient_id, kinds={"order"}) if o.ts.date() <= since]
    age = datetime.now(UTC).year - profile.birth_year
    ctx = {
        "patient_id": patient_id,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "profile": {
            "code_name": profile.code_name,
            "age": age,
            "sex": profile.sex,
            "room": profile.room,
            "conditions": [c.display for c in profile.conditions],
            "medications": [f"{m.name} {m.dose} {m.schedule}" for m in profile.medications],
            "one_liner": profile.one_liner,
        },
        "baseline": {e.dimension: e.description for e in baseline.entries if e.valid_to is None},
        "changed_dimensions": {
            d: {
                "label": DIMENSION_LABELS[d]["zh-TW"],
                "direction": line.direction,
                "magnitude": line.magnitude,
                "window_days": line.window_days,
                "structured": line.summary,
            }
            for d, line in changed.items()
        },
        "cross_dimension_signal": report.cross_dimension_signal,
        "evidence": evidence,
        "incidents": [
            {"id": e.id, "date": e.ts.date().isoformat(), "summary": e.summary} for e in inc
        ],
        "last_orders": [
            {
                "order_id": o.id,
                "date": o.ts.date().isoformat(),
                "text": o.raw_text,
                "items": [i.text for i in o.items],
                "follow_up": o.follow_up.model_dump() if o.follow_up else None,
            }
            for o in orders
        ],
        "observation_count": len(obs),
    }
    ctx["_report"] = report.model_dump(mode="json")
    return ctx


def validate_and_assemble(
    ctx: dict[str, Any], sub: RoundPageSubmission, author: str = "familiarization_writer"
) -> RoundPage:
    """Enforce the page rules on what the subagent wrote; ValueError carries a fixable message."""
    changed = ctx["changed_dimensions"]
    report = TrendReport.model_validate(ctx["_report"])
    errors: list[str] = []
    if not sub.who.strip():
        errors.append("who 不能空白")
    lines: list[TrendLine] = []
    seen: set[str] = set()
    for c in sub.changes:
        if c.dimension not in changed:
            errors.append(
                f"changes 只能寫 changed_dimensions（{list(changed)}），不能寫 {c.dimension}"
            )
            continue
        if c.dimension in seen:
            continue
        seen.add(c.dimension)
        valid_ids = {e["id"] for e in ctx["evidence"].get(c.dimension, [])}
        refs = [r for r in c.evidence_refs if r in valid_ids][:3]
        if not refs:
            refs = [e["id"] for e in ctx["evidence"].get(c.dimension, [])][-3:]
        info = changed[c.dimension]
        text = scrub_clinical_language(c.text.strip())
        if not text:
            errors.append(f"{c.dimension} 的 text 不能空白")
        lines.append(
            TrendLine(
                dimension=c.dimension,
                direction=info["direction"],
                summary=text,
                window_days=info["window_days"],
                magnitude=info["magnitude"],
                evidence_refs=refs,
                is_abnormal=True,
            )
        )
    missing = [d for d in changed if d not in seen]
    if missing:
        errors.append(f"有變化的維度都要寫：缺 {missing}")
    note = None
    if not changed:
        note = (sub.no_change_note or "本期八維度皆與基線一致").strip()
    questions = [scrub_clinical_language(q.strip()) for q in sub.questions if q.strip()]
    questions = [q if q.endswith("？") else q.rstrip("?。") + "？" for q in questions][:4]
    if not questions:
        errors.append("questions 至少 1 條問句")
    for q in questions:
        if any(b.lower() in q.lower() for b in BANNED_DIAGNOSTIC_TERMS):
            errors.append(f"questions 不得含診斷／處置用語：{q}")
    order_ids = {o["order_id"] for o in ctx["last_orders"]}
    fu = [
        OrderFollowUpLine(
            order_id=f.order_id,
            text=f.text.strip(),
            done=f.done,
            effective=f.effective,
            note=f.note,
        )
        for f in sub.order_followup
        if f.order_id in order_ids and f.text.strip()
    ]
    if ctx["last_orders"] and not fu:
        errors.append("③ 要逐條回應 last_orders（order_id 要對）")
    if errors:
        raise ValueError("；".join(errors))
    now = datetime.now(UTC)
    two = [s for s in report.series if s.dimension in [line.dimension for line in lines][:2]]
    baseline_summary = [
        f"{DIMENSION_LABELS[d]['zh-TW']}：{desc}" for d, desc in ctx["baseline"].items()
    ]
    return RoundPage(
        id=new_id("round", now),
        patient_id=ctx["patient_id"],
        generated_at=now,
        generated_from=sorted(
            {r for line in lines for r in line.evidence_refs} | {i["id"] for i in ctx["incidents"]}
        ),
        status="draft",
        author=author,
        provenance=Provenance(source="system_derived", author=author, ts=now),
        audience="doctor",
        who=scrub_clinical_language(sub.who.strip()),
        baseline_summary=baseline_summary,
        changes=lines,
        cross_dimension_signal=ctx.get("cross_dimension_signal") or note,
        order_followup=fu,
        questions=questions,
        chart=two,
        since=date.fromisoformat(ctx["since"]),
        page_limit_ok=(1 + len(baseline_summary) + len(lines) + len(fu) + len(questions))
        <= MAX_LINES,
    )


def draft_from_facts(ctx: dict[str, Any]) -> RoundPageSubmission:
    """TEST DOUBLE (MODEL_PROVIDER=mock): a deterministic submission built from the facts."""
    prof = ctx["profile"]
    who = (
        f"{prof['code_name']}，{prof['age']} 歲，{prof['room']}。"
        f"{'、'.join(prof['conditions'])}。{prof['one_liner']}"
    )
    changes = [
        ChangeLine(
            dimension=d,
            text=(
                f"{info['label']}{'減少' if info['direction'] == 'down' else '增加或出現'}："
                f"{info['structured']}"
            ),
            evidence_refs=[e["id"] for e in ctx["evidence"].get(d, [])][-3:],
        )
        for d, info in ctx["changed_dimensions"].items()
    ]
    fu = [
        FollowUpLine(
            order_id=o["order_id"],
            text=o["items"][0] if o["items"] else o["text"],
            done=(o["follow_up"] or {}).get("done"),
            effective=(o["follow_up"] or {}).get("effective"),
            note=(o["follow_up"] or {}).get("note", ""),
        )
        for o in ctx["last_orders"]
    ]
    qs = [
        f"{info['label']}近期持續變化，請醫師確認是否需要進一步評估？"
        for info in ctx["changed_dimensions"].values()
    ]
    qs = qs or ["本期無異常趨勢，請醫師確認是否維持目前醫囑？"]
    return RoundPageSubmission(
        who=who,
        changes=changes,
        no_change_note="本期八維度皆與基線一致",
        order_followup=fu,
        questions=qs[:4],
    )
