"""handoff_packager subagent — different slices of the same record for different handoffs.

phone_isbar: the nurse reads it over the phone to the contract hospital / home-acute team.
visit_page:  accompanies the person to an outpatient visit."""

from __future__ import annotations

from datetime import UTC, datetime

from record_schema import (
    DIMENSION_LABELS,
    ISBAR,
    Baseline,
    HandoffPage,
    Profile,
    Provenance,
    RouteDecision,
)

from core.ids import new_id


def _usual(baseline: Baseline) -> list[str]:
    return [
        f"{DIMENSION_LABELS[e.dimension]['zh-TW']}：{e.description}"
        for e in baseline.entries
        if e.valid_to is None
    ]


def _isbar_text(isbar: ISBAR) -> str:
    return (
        f"I：{isbar.identity}\nS：{isbar.situation}\nB：{isbar.background}\n"
        f"A（護理師）：{isbar.nurse_assessment or '—'}\n"
        f"A（AI，與基線比）：{isbar.ai_change_vs_baseline}\n"
        f"R（護理師）：{isbar.nurse_recommendation or '—'}\n"
        f"R（AI，請確認）：{'；'.join(isbar.ai_questions_for_nurse)}"
    )


def package(
    profile: Profile,
    baseline: Baseline,
    isbar: ISBAR,
    generated_from: list[str],
    route: RouteDecision,
    confirmed_by: str,
) -> HandoffPage:
    now = datetime.now(UTC)
    variant = "visit_page" if route == "accompany_visit" else "phone_isbar"
    what = isbar.situation
    return HandoffPage(
        id=new_id("handoff", now),
        patient_id=profile.patient_id,
        generated_at=now,
        generated_from=list(generated_from),
        status="approved",
        author="handoff_packager",
        confirmed_by=confirmed_by,
        provenance=Provenance(
            source="nurse_confirmed", author="handoff_packager", confirmed_by=confirmed_by, ts=now
        ),
        audience="er" if variant == "phone_isbar" else "doctor",
        variant=variant,
        what_happened=what,
        usual_state=_usual(baseline),
        medications=[f"{m.name} {m.dose} {m.schedule}" for m in profile.medications],
        dnr=profile.dnr,
        contacts=[f"{c.relation} {c.name} {c.phone}" for c in profile.emergency_contacts],
        isbar_text=_isbar_text(isbar),
    )
