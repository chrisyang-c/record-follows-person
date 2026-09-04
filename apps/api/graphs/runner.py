"""Start / resume / inspect graph threads. thread_id = f"{patient_id}:{graph}:{date}" (+ suffix)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from langgraph.types import Command

from graphs import registry
from graphs.checkpointer import get_checkpointer
from graphs.path_a import build_path_a
from graphs.path_b import build_round_graph, build_shift_graph

log = logging.getLogger(__name__)

BUILDERS = {"path_a": build_path_a, "shift": build_shift_graph, "round": build_round_graph}

REQUIRED_RESUME_FIELDS: dict[str, list[str]] = {
    "nurse_review": ["action", "nurse_id"],
    "nurse_onsite_assessment": [
        "nurse_id",
        "onsite_assessment",
        "nurse_assessment",
        "nurse_recommendation",
    ],
    "nurse_route_choice": ["route", "nurse_id"],
    "nurse_approve_notification": ["action", "nurse_id"],
    "nurse_10s_confirm": ["action", "nurse_id"],
    "head_nurse_edit_list": ["head_nurse"],
    "doctor_round": ["orders", "nurse_id"],
    "nurse_confirm_baseline": ["action", "nurse_id"],
}


@lru_cache
def compiled(graph: str):
    return BUILDERS[graph]().compile(checkpointer=get_checkpointer())


def _config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def graph_of(thread_id: str) -> str:
    return thread_id.split(":")[1]


def new_thread_id(graph: str, patient_id: str, on: datetime | None = None) -> str:
    on = on or datetime.now(UTC)
    base = f"{patient_id}:{graph}:{on.date().isoformat()}"
    tid, n = base, 1
    while registry.get(tid) is not None:
        n += 1
        tid = f"{base}:{n}"
    return tid


def snapshot(thread_id: str) -> dict[str, Any]:
    graph = graph_of(thread_id)
    st = compiled(graph).get_state(_config(thread_id))
    interrupts = [i for t in st.tasks for i in t.interrupts]
    values = dict(st.values or {})
    status = "done" if not st.next else ("interrupted" if interrupts else "running")
    interrupt_payload = interrupts[0].value if interrupts else None
    deadline = values.get("deadline")
    dl = datetime.fromisoformat(deadline) if isinstance(deadline, str) else None
    registry.upsert(
        thread_id,
        graph=graph,
        patient_id=values.get("patient_id", "ALL"),
        status=status,
        interrupt_type=(interrupt_payload or {}).get("type") if interrupt_payload else None,
        deadline=dl,
        escalation_level=values.get("escalation_level", 0),
    )
    return {
        "thread_id": thread_id,
        "graph": graph,
        "status": status,
        "next": list(st.next),
        "interrupt": interrupt_payload,
        "values": values,
    }


def start(graph: str, patient_id: str, input_values: dict[str, Any]) -> dict[str, Any]:
    tid = new_thread_id(graph, patient_id)
    registry.upsert(tid, graph=graph, patient_id=patient_id, status="running")
    compiled(graph).invoke(
        {**input_values, "patient_id": patient_id, "thread_id": tid}, _config(tid)
    )
    return snapshot(tid)


def validate_resume(interrupt_type: str | None, payload: dict[str, Any]) -> None:
    if not interrupt_type:
        raise ValueError("thread is not waiting for input")
    missing = [f for f in REQUIRED_RESUME_FIELDS.get(interrupt_type, []) if not payload.get(f)]
    if payload.get("action") in ("return", "escalate", "skip", "reject") and interrupt_type in (
        "nurse_review",
        "nurse_approve_notification",
        "nurse_10s_confirm",
        "nurse_confirm_baseline",
    ):
        missing = [m for m in missing if m in ("action", "nurse_id")]
    if interrupt_type == "nurse_review" and payload.get("action") in ("accept", "edit"):
        for f in ("onsite_assessment", "nurse_assessment", "nurse_recommendation"):
            if not payload.get(f):
                missing.append(f)
    if missing:
        raise ValueError(f"{interrupt_type} resume is missing: {', '.join(missing)}")


def resume(thread_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    snap = snapshot(thread_id)
    itype = (snap["interrupt"] or {}).get("type") if snap["interrupt"] else None
    validate_resume(itype, payload)
    compiled(graph_of(thread_id)).invoke(Command(resume=payload), _config(thread_id))
    return snapshot(thread_id)


def reset_for_tests() -> None:
    compiled.cache_clear()
    registry.reset_for_tests()
