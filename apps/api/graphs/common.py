"""Nodes and helpers shared by Path A and Path B. Node function names == mermaid node ids."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

from record_schema import (
    Baseline,
    FollowupQA,
    Observation,
    Profile,
    RedFlagResult,
    StructuredObservation,
)

from agents.comparator import compare
from core.settings import get_settings
from record.store import UnapprovedWriteError, get_store
from red_flags.rules import RedFlagInput, evaluate, render_lines

log = logging.getLogger(__name__)


class RawInput(TypedDict, total=False):
    text: str
    language: str
    media_refs: list[str]
    followup_answers: list[dict[str, Any]]
    turns: list[dict[str, Any]]  # multi-turn dialog: [{text, dimension, quick}]
    seems_different: bool
    incidents: list[str]
    caregiver_id: str
    shift: str


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def deadline_iso(seconds: int | None = None) -> str:
    s = seconds if seconds is not None else get_settings().NURSE_REVIEW_TIMEOUT_S
    return (datetime.now(UTC) + timedelta(seconds=s)).isoformat()


# --- shared nodes ---------------------------------------------------------------------------


def load_person_record(state: dict[str, Any]) -> dict[str, Any]:
    store = get_store()
    pid = state["patient_id"]
    profile = store.load_profile(pid)
    baseline = store.load_baseline(pid)
    since = datetime.now(UTC) - timedelta(days=14)
    recent = store.load_timeline(pid, since=since)
    recent_obs = [e for e in recent if e.kind == "observation"]
    recent_lines: list[str] = []
    for e in recent[-6:]:
        if e.kind == "observation":
            sb = e.minimal_sbar.s if e.minimal_sbar else e.observation.raw_text
            recent_lines.append(f"{e.ts.date()} {sb[:60]}")
        elif e.kind == "incident":
            recent_lines.append(f"{e.ts.date()} 事故：{e.summary[:40]}")
        elif e.kind == "order":
            recent_lines.append(f"{e.ts.date()} 醫囑：{e.raw_text[:40]}")
    return {
        "profile": profile.model_dump(mode="json"),
        "baseline": baseline.model_dump(mode="json"),
        "recent_lines": recent_lines,
        "recent_observations": [o.model_dump(mode="json") for o in recent_obs],
        "status": "loaded",
        "updated_at": now_iso(),
    }


def intake_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Multi-turn intake: replays the caregiver dialog (first sentence + up to MAX_TURNS answers).

    A nurse 退回 adds the caregiver's addendum as one more free-text turn. State records
    asked_dimensions and turn_count so the nurse can see what was asked."""
    from ingest.intake_dialog import Turn, run_dialog

    raw: RawInput = state["raw_input"]
    profile = Profile.model_validate(state["profile"])
    baseline = Baseline.model_validate(state["baseline"])
    turns = [Turn.model_validate(x) for x in raw.get("turns") or []]
    if not turns:
        turns = [Turn(text=raw.get("text", ""))]
        for a in raw.get("followup_answers", []):
            fa = FollowupQA.model_validate(a)
            if fa.answer and not fa.answered_unknown:
                turns.append(Turn(text=fa.answer))
    for extra in state.get("caregiver_addenda") or []:
        turns.append(Turn(text=extra))
    result = run_dialog(
        turns,
        profile,
        baseline,
        seems_different=bool(raw.get("seems_different")),
        incidents=list(raw.get("incidents") or []),
    )
    obs = result.observation
    if raw.get("media_refs"):
        obs.followups.append(
            FollowupQA(
                question="影像摘要（固定 mock）",
                answer="影像已附上，摘要由護理師確認",
                lang="zh-TW",
            )
        )
    return {
        "structured_observation": obs.model_dump(mode="json"),
        "asked_dimensions": result.asked_dimensions,
        "turn_count": result.turn_count,
        "status": "intake_done",
        "updated_at": now_iso(),
    }


def baseline_comparator(state: dict[str, Any]) -> dict[str, Any]:
    obs = StructuredObservation.model_validate(state["structured_observation"])
    baseline = Baseline.model_validate(state["baseline"])
    recent = [Observation.model_validate(o) for o in state.get("recent_observations", [])]
    deltas = compare(obs, baseline, recent, datetime.now(UTC).date())
    return {"baseline_delta": [d.model_dump(mode="json") for d in deltas], "updated_at": now_iso()}


def red_flag_rules(state: dict[str, Any]) -> dict[str, Any]:
    """Pure code (delegates to red_flags/rules.py). No LLM."""
    obs = StructuredObservation.model_validate(state["structured_observation"])
    profile = Profile.model_validate(state["profile"])
    baseline = Baseline.model_validate(state["baseline"])
    result = evaluate(
        RedFlagInput(
            observation=obs,
            vitals=None,
            baseline_vitals=baseline.vitals_usual,
            on_anticoagulant=profile.on_anticoagulant,
        )
    )
    return {"red_flags": result.model_dump(mode="json"), "updated_at": now_iso()}


def red_flag_hit(state: dict[str, Any]) -> bool:
    return bool(RedFlagResult.model_validate(state["red_flags"]).notify_now)


def notify_nurse_urgent(state: dict[str, Any]) -> dict[str, Any]:
    result = RedFlagResult.model_validate(state["red_flags"])
    profile = Profile.model_validate(state["profile"])
    content = f"【紅燈】{profile.code_name}（{profile.room}）\n" + "\n".join(render_lines(result))
    note = {
        "to": "nurse",
        "channel": "screen",
        "content": content,
        "status": "displayed_only",
        "sent_at": now_iso(),
    }
    return {
        "notifications": [note],
        "status": "red_flag",
        "deadline": deadline_iso(min(300, get_settings().NURSE_REVIEW_TIMEOUT_S)),
        "updated_at": now_iso(),
    }


def guarded_timeline_write(patient_id: str, payload: Any) -> str:
    """The graph-side gate before record.write_timeline (which asserts again)."""
    status = (
        getattr(payload, "status", None) if not isinstance(payload, dict) else payload.get("status")
    )
    confirmed_by = (
        getattr(payload, "confirmed_by", None)
        if not isinstance(payload, dict)
        else payload.get("confirmed_by")
    )
    assert status == "approved" and confirmed_by, (
        "timeline_write: payload must be approved and confirmed"
    )
    if status != "approved" or not confirmed_by:
        raise UnapprovedWriteError("timeline_write rejected an unapproved payload")
    return get_store().write_timeline(patient_id, payload)
