"""familiarization_writer subagent — RoundPage in four fixed sections, one page max.

① who + baseline ② what changed since last round (abnormal first, each line → timeline id)
③ were last orders done / effective ④ questions for the doctor (question form only).
Structured input → structured RoundPage; the LLM (when enabled) only polishes wording."""

from __future__ import annotations

from datetime import UTC, date, datetime

from record_schema import (
    DIMENSION_LABELS,
    Baseline,
    Order,
    OrderFollowUpLine,
    Profile,
    Provenance,
    RoundPage,
    TrendReport,
)

from agents.subagents.trend_analyzer import top_two_series
from core.ids import new_id
from core.llm import scrub_clinical_language

MAX_LINES = 22  # one A4 page at 16px ≈ 22 content lines


def write(
    profile: Profile,
    baseline: Baseline,
    report: TrendReport,
    last_orders: list[Order],
    since: date,
    author: str = "familiarization_writer",
) -> RoundPage:
    now = datetime.now(UTC)
    age = now.year - profile.birth_year
    conds = "、".join(c.display for c in profile.conditions) or "無登錄慢性病"
    sex = "男" if profile.sex == "M" else "女"
    who = (
        f"{profile.code_name}，{age} 歲{sex}，{profile.room}。{conds}。{profile.one_liner}".strip()
    )
    baseline_summary = [
        f"{DIMENSION_LABELS[e.dimension]['zh-TW']}：{e.description}"
        for e in baseline.entries
        if e.valid_to is None
    ][:8]

    changes = [line for line in report.lines if line.direction != "unknown"]
    changes.sort(key=lambda line: (not line.is_abnormal, -(line.magnitude or 0)))

    order_lines: list[OrderFollowUpLine] = []
    for o in last_orders:
        for item in o.items:
            fu = o.follow_up
            done = fu.done if fu else None
            note = fu.note if fu else ""
            effective = None
            if item.target_dimension:  # per-item: judge by that dimension's own trend
                t = next(
                    (line for line in report.lines if line.dimension == item.target_dimension), None
                )
                if t is not None and t.direction != "unknown":
                    effective = not t.is_abnormal
                    note = f"依趨勢：{t.summary}" + (f"；{fu.note}" if fu and fu.note else "")
            if effective is None and fu is not None:  # fall back to the order-level follow-up
                effective = fu.effective
            order_lines.append(
                OrderFollowUpLine(
                    order_id=o.id, text=item.text, done=done, effective=effective, note=note
                )
            )

    questions: list[str] = []
    for line in changes:
        if not line.is_abnormal:
            continue
        label = DIMENSION_LABELS[line.dimension]["zh-TW"]
        questions.append(
            f"{label}近 {line.window_days} 天持續變化（{line.summary}），"
            "請醫師確認是否需要進一步評估？"
        )
    if report.cross_dimension_signal:
        questions.append(f"{report.cross_dimension_signal}，請醫師確認是否有共同原因需要釐清？")
    for ol in order_lines:
        if ol.effective is False:
            questions.append(f"上次醫囑「{ol.text}」已執行但趨勢未改善，請醫師確認是否調整？")
    if report.incident_ids:
        questions.append(
            f"期間有 {len(report.incident_ids)} 件事故（{'、'.join(report.incident_ids[:3])}），"
            "請醫師確認後續追蹤？"
        )
    if not questions:
        questions.append("本月無異常趨勢，請醫師確認是否維持目前醫囑？")
    questions = [scrub_clinical_language(q) for q in questions[:5]]

    total = 1 + len(baseline_summary) + len(changes) + len(order_lines) + len(questions)
    page_limit_ok = total <= MAX_LINES
    if not page_limit_ok:
        changes = changes[
            : max(4, MAX_LINES - 1 - len(baseline_summary) - len(order_lines) - len(questions))
        ]
        page_limit_ok = True

    return RoundPage(
        id=new_id("round", now),
        patient_id=profile.patient_id,
        generated_at=now,
        generated_from=sorted(
            {r for line in changes for r in line.evidence_refs} | set(report.incident_ids)
        ),
        status="draft",
        author=author,
        provenance=Provenance(source="system_derived", author=author, ts=now),
        audience="doctor",
        who=who,
        baseline_summary=baseline_summary,
        changes=changes,
        cross_dimension_signal=report.cross_dimension_signal,
        order_followup=order_lines,
        questions=questions,
        chart=top_two_series(report),
        since=since,
        page_limit_ok=page_limit_ok,
    )
