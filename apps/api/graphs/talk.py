"""talk — one conversation turn of the caregiver ↔ intake agent chat, streamed.

Each caregiver message runs this small LangGraph graph; every node emits custom stream events
(node_start / node_end / llm_call / tool_call / red) with a formal summary (for nurses/doctors)
and a plain one (for the caregiver). The API relays them over SSE and the UI renders the
activity bar; the events are persisted in the agent message (meta.activity) and in provenance.

Nodes: load_person_record → record_caregiver_message → intake_agent → baseline_comparator
       → red_flag_rules → notify_nurse (red: start / update Path A) → decide_next → reply
"""

from __future__ import annotations

import operator
import time
from datetime import UTC, datetime
from typing import Annotated, Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from record_schema import DIMENSION_LABELS, Baseline, Observation, Profile, RedFlagResult

from agents.comparator import compare
from core.llm import LLMUnavailable
from core.trace import trace
from ingest.intake_dialog import (
    RED_CLOSING,
    RED_INTRO,
    Turn,
    build_observation,
    evaluate_red,
    plan_question,
    summarize,
)
from record import conversation as conv
from record.store import get_store
from red_flags.rules import render_lines

AFFIRM = {
    "對",
    "對啊",
    "對的",
    "是",
    "是的",
    "沒錯",
    "好",
    "好的",
    "嗯",
    "ok",
    "OK",
    "沒問題",
    "正確",
}
NEGATIVE = ("不對", "不是", "錯", "不太對", "不完全")
URGENT = ("現在來", "馬上", "趕快", "需要護理師", "快來", "緊急")


class TalkState(TypedDict, total=False):
    patient_id: str
    text: str
    role_view: str
    session: dict[str, Any]
    profile: dict[str, Any]
    baseline: dict[str, Any]
    turns: list[dict[str, Any]]
    obs: dict[str, Any]
    asked: list[list[str]]
    reports: list[dict[str, Any]]
    baseline_delta: list[dict[str, Any]]
    red_flags: dict[str, Any]
    red: bool
    thread_id: str | None
    phase: str
    next_question: dict[str, Any] | None
    reply: str
    reply_kind: str
    reply_meta: dict[str, Any]
    system_lines: list[str]
    sent: str | None
    events: list[dict[str, Any]]


class _Step:
    """Context manager emitting node_start / node_end custom events with timing."""

    def __init__(self, name: str, plain: str, summary: str = "") -> None:
        self.name, self.plain, self.summary = name, plain, summary
        self.t0 = time.perf_counter()
        self.w = get_stream_writer()
        self.w({"type": "node_start", "name": name, "plain": plain, "summary": summary or name})

    def done(self, summary: str, plain: str | None = None, **extra: Any) -> dict[str, Any]:
        ev = {
            "type": "node_end",
            "name": self.name,
            "summary": summary,
            "plain": plain or self.plain,
            "ms": int((time.perf_counter() - self.t0) * 1000),
            **extra,
        }
        self.w(ev)
        return ev


def load_person_record(state: TalkState) -> dict[str, Any]:
    pid = state["patient_id"]
    step = _Step("load_person_record", "看他的紀錄")
    store = get_store()
    profile = store.load_profile(pid)
    baseline = store.load_baseline(pid)
    s = conv.open_session(pid)
    ev = step.done(
        f"load_person_record：{profile.code_name}，基線 {len(baseline.entries)} 條，"
        f"session {s.session_id}",
        f"讀取{profile.code_name}的基線",
        output=f"{len(baseline.entries)} 條基線",
    )
    return {
        "profile": profile.model_dump(mode="json"),
        "baseline": baseline.model_dump(mode="json"),
        "session": s.model_dump(),
        "thread_id": s.thread_id,
        "phase": s.phase,
        "events": [ev],
    }


def record_caregiver_message(state: TalkState) -> dict[str, Any]:
    pid = state["patient_id"]
    s = state["session"]
    step = _Step("record_caregiver_message", "記下你說的話")
    conv.append(
        pid,
        "caregiver",
        state["text"].strip(),
        s["session_id"],
        author=Profile.model_validate(state["profile"]).caregiver_code_name,
    )
    turns = conv.session_turns(pid, s["session_id"])
    ev = step.done(
        f"record_caregiver_message：第 {len(turns)} 句（caregiver_said）",
        "記下你說的話",
        output=state["text"].strip()[:60],
    )
    return {"turns": turns, "events": [ev]}


def intake_agent(state: TalkState) -> dict[str, Any]:
    profile = Profile.model_validate(state["profile"])
    baseline = Baseline.model_validate(state["baseline"])
    turns = [Turn.model_validate(t) for t in state["turns"]]
    if state.get("phase") == "confirm":
        # the caregiver is answering「對嗎？」; keep the observation from the previous turns
        turns = turns[:-1] or turns
    step = _Step("intake_agent", "把你說的分成八個面向")
    t0 = time.perf_counter()
    obs, asked, asked_dims, reports = build_observation(turns, profile, baseline)
    dims = "、".join(DIMENSION_LABELS[d]["zh-TW"] for d in obs.domains) or "（還沒抽到）"
    get_stream_writer()(
        {
            "type": "llm_call",
            "name": "extract_observation",
            "summary": f"llm.extract：{len(turns)} 句 → {list(obs.domains)}",
            "plain": "在聽你說的是哪一方面",
            "ms": int((time.perf_counter() - t0) * 1000),
            "output": dims,
        }
    )
    ev = step.done(
        f"intake_agent：八維度已知 {list(obs.domains)}，未知 {obs.unknown}",
        f"聽到：{dims}",
        output=dims,
    )
    return {
        "obs": obs.model_dump(mode="json"),
        "asked": [list(a) for a in asked],
        "reports": [r.model_dump(mode="json") for r in reports],
        "events": [ev],
    }


def baseline_comparator(state: TalkState) -> dict[str, Any]:
    from record_schema import StructuredObservation

    step = _Step("baseline_comparator", "對照他平常的樣子")
    obs = StructuredObservation.model_validate(state["obs"])
    baseline = Baseline.model_validate(state["baseline"])
    since = datetime.now(UTC).date().toordinal() - 14
    recent = [
        e
        for e in get_store().load_timeline(state["patient_id"], kinds={"observation"})
        if e.ts.date().toordinal() >= since
    ]
    deltas = compare(
        obs,
        baseline,
        [Observation.model_validate(o.model_dump()) for o in recent],
        datetime.now(UTC).date(),
    )
    parts = []
    for d in deltas:
        if d.direction in ("down", "up"):
            mag = (
                f" {'-' if d.direction == 'down' else '+'}{d.magnitude:.0%}"
                if d.magnitude is not None
                else ""
            )
            parts.append(f"{DIMENSION_LABELS[d.domain]['zh-TW']}{mag}，持續 {d.days} 天")
    summary = "baseline_comparator：" + ("；".join(parts) if parts else "與基線無明顯差異")
    ev = step.done(summary, "在看跟平常差多少", output="；".join(parts) or "跟平常差不多")
    return {"baseline_delta": [d.model_dump(mode="json") for d in deltas], "events": [ev]}


def red_flag_rules(state: TalkState) -> dict[str, Any]:
    from record_schema import StructuredObservation

    step = _Step("red_flag_rules", "檢查有沒有要馬上叫護理師的事")
    obs = StructuredObservation.model_validate(state["obs"])
    rf = evaluate_red(
        obs, Profile.model_validate(state["profile"]), Baseline.model_validate(state["baseline"])
    )
    if rf.notify_now:
        facts = "；".join(f for h in rf.hits for f in h.facts if h.action == "notify_now")
        ev = step.done(
            f"red_flag_rules：命中 {[h.rule_id for h in rf.hits if h.action == 'notify_now']}"
            f"（{facts}）→ 已通知護理師",
            "紅燈規則命中，已通知護理師",
            red=True,
            output=facts,
        )
        ev["type"] = "red"
    else:
        ev = step.done("red_flag_rules：未命中", "沒有需要馬上叫護理師的事", output="未命中")
    return {"red_flags": rf.model_dump(mode="json"), "red": rf.notify_now, "events": [ev]}


def notify_nurse(state: TalkState) -> dict[str, Any]:
    """Red flag: start Path A once (program notifies the nurse), then push every later answer."""
    from graphs import runner

    pid = state["patient_id"]
    s = conv.SessionState.model_validate(state["session"])
    profile = Profile.model_validate(state["profile"])
    step = _Step("notify_nurse_urgent", "通知護理師")
    lines: list[str] = []
    thread_id = s.thread_id
    if not state.get("red"):
        ev = step.done("notify_nurse_urgent：不需要", "不用叫護理師", output="—")
        return {"events": [ev], "system_lines": []}
    if thread_id is None:
        snap = runner.start(
            "path_a",
            pid,
            {
                "path": "incident",
                "raw_input": {
                    "turns": state["turns"],
                    "language": "zh-TW",
                    "caregiver_id": profile.caregiver_code_name,
                    "dialog_id": s.dialog_id,
                },
            },
        )
        thread_id = snap["thread_id"]
        s.thread_id, s.phase = thread_id, "red"
        conv.save_session(pid, s)
        first_line = "；".join(render_lines(RedFlagResult.model_validate(state["red_flags"]))[:1])
        lines.append("已通知護理師，請留在他身邊。")
        conv.append(
            pid,
            "system",
            lines[-1],
            s.session_id,
            kind="event",
            meta={"thread_id": thread_id, "red": True},
            author="red_flag_rules",
        )
        ev = step.done(
            f"notify_nurse_urgent：Path A {thread_id} 已啟動（{first_line}）",
            "護理師已經收到通知",
            output=thread_id,
            red=True,
        )
    else:
        try:
            runner.update_caregiver(thread_id, state["turns"], [], False)
            ev = step.done(
                f"caregiver_report：回報已寫進 {thread_id} 的 caregiver_section",
                "你剛說的已經傳給護理師",
                output=thread_id,
            )
        except ValueError:
            lines.append("護理師已接手，接下來由護理師記錄。")
            conv.append(pid, "system", lines[-1], s.session_id, kind="event", author="nurse")
            conv.close_session(pid)
            ev = step.done(
                "caregiver_report：護理師已接手（thread 不再 interrupt）",
                "護理師已經接手",
                output="closed",
            )
            return {
                "events": [ev],
                "system_lines": lines,
                "phase": "closed",
                "thread_id": thread_id,
            }
    return {"events": [ev], "system_lines": lines, "thread_id": thread_id, "phase": "red"}


def decide_next(state: TalkState) -> dict[str, Any]:
    from record_schema import StructuredObservation

    pid = state["patient_id"]
    profile = Profile.model_validate(state["profile"])
    baseline = Baseline.model_validate(state["baseline"])
    obs = StructuredObservation.model_validate(state["obs"])
    rf = RedFlagResult.model_validate(state["red_flags"])
    asked = [tuple(a) for a in state.get("asked", [])]
    s = (
        conv.SessionState.model_validate(conv.session(pid).model_dump())
        if conv.session(pid)
        else conv.SessionState.model_validate(state["session"])
    )
    text = state["text"].strip()
    phase = state.get("phase") or s.phase
    if phase == "closed":
        return {"reply": "", "reply_kind": "event", "reply_meta": {}, "events": []}
    step = _Step("decide_next_question", "想下一句要問什麼")
    # ---- confirmation of the summary ----
    if phase == "confirm" and not state.get("red"):
        if (
            text in AFFIRM
            or text.startswith("對")
            or text.startswith("是")
            or text.startswith("好")
        ):
            from graphs import runner

            mode = "path_a" if any(k in text for k in URGENT) else "shift"
            snap = runner.start(
                mode,
                pid,
                {
                    "path": "incident" if mode == "path_a" else "routine",
                    "raw_input": {
                        "turns": state["turns"][:-1],
                        "language": "zh-TW",
                        "caregiver_id": profile.caregiver_code_name,
                        "dialog_id": s.dialog_id,
                        "caregiver_confirmed_meaning": True,
                    },
                },
            )
            line = "已送給護理師，這一班會確認。" if mode == "shift" else "已通知護理師來看。"
            conv.append(
                pid,
                "system",
                line,
                s.session_id,
                kind="event",
                meta={"thread_id": snap["thread_id"]},
                author="intake_agent",
            )
            conv.close_session(pid)
            ev = step.done(
                f"decide_next：照護者確認 → {mode} thread {snap['thread_id']}",
                "送給護理師了",
                output=snap["thread_id"],
            )
            return {
                "reply": "謝謝你。有什麼變化再跟我說。",
                "reply_kind": "closing",
                "reply_meta": {"thread_id": snap["thread_id"]},
                "sent": snap["thread_id"],
                "phase": "closed",
                "events": [ev],
            }
        if any(k in text for k in NEGATIVE):
            s.phase = "intake"
            conv.save_session(pid, s)
            ev = step.done(
                "decide_next：照護者說不對 → 回到 intake", "好，我再聽一次", output="intake"
            )
            return {
                "reply": "好，哪裡不對？你再說一次，我重新記。",
                "reply_kind": "question",
                "reply_meta": {"phase": "routine"},
                "phase": "intake",
                "events": [ev],
            }
        # anything else in confirm phase is treated as an addition (falls through to planning)
        s.phase = "intake"
    # ---- plan the next question (the model decides) ----
    t0 = time.perf_counter()
    nq, budget_left = plan_question(obs, profile, baseline, asked, rf)
    get_stream_writer()(
        {
            "type": "llm_call",
            "name": "next_question",
            "summary": "llm.next_question："
            + (f"問「{nq.text}」 — {nq.reason}" if nq else "ask=false（夠了）"),
            "plain": "在想下一句要問什麼",
            "ms": int((time.perf_counter() - t0) * 1000),
            "output": nq.text if nq else "夠了",
        }
    )
    red = state.get("red", False)
    if nq is not None:
        intro = (
            RED_INTRO
            if (red and not any(t.get("phase") == "red" for t in state["turns"][1:]))
            else None
        )
        reply = (intro + "\n" if intro else "") + nq.text
        s.phase = "red" if red else "intake"
        conv.save_session(pid, s)
        ev = step.done(
            f"decide_next：問「{nq.text}」（{nq.reason}）",
            "決定下一題",
            output=nq.text,
            reason=nq.reason,
        )
        return {
            "reply": reply,
            "reply_kind": "question",
            "next_question": nq.model_dump(),
            "reply_meta": {
                "question": nq.text,  # the bare question (the reply may carry RED_INTRO)
                "dimension": nq.dimension,
                "reason": nq.reason,
                "phase": "red" if red else "routine",
            },
            "phase": s.phase,
            "events": [ev],
        }
    if red:
        s.phase = "red"
        conv.save_session(pid, s)
        ev = step.done("decide_next：紅燈關鍵事實已足夠", "關鍵的事都記下來了", output="closing")
        return {
            "reply": RED_CLOSING,
            "reply_kind": "closing",
            "reply_meta": {"phase": "red"},
            "phase": "red",
            "events": [ev],
        }
    s.phase = "confirm"
    conv.save_session(pid, s)
    summary = summarize(obs, profile.code_name)
    ev = step.done(
        "decide_next：八維度足夠 → 摘要請照護者確認", "整理成一段話請你確認", output=summary
    )
    return {
        "reply": summary,
        "reply_kind": "summary",
        "reply_meta": {"phase": "confirm"},
        "phase": "confirm",
        "events": [ev],
    }


def reply(state: TalkState) -> dict[str, Any]:
    pid = state["patient_id"]
    if not state.get("reply"):
        return {}
    s = conv.session(pid) or conv.SessionState.model_validate(state["session"])
    meta = {**(state.get("reply_meta") or {}), "activity": state.get("events", [])}
    msg = conv.append(
        pid,
        "agent",
        state["reply"],
        s.session_id,
        kind=state.get("reply_kind", "message"),
        meta=meta,
        author="intake_agent",
    )  # type: ignore[arg-type]
    trace(
        "talk.turn",
        patient_id=pid,
        session=s.session_id,
        phase=state.get("phase"),
        reply_kind=state.get("reply_kind"),
        red=state.get("red"),
        reply=state["reply"],
    )
    return {"reply_meta": {**meta, "message_id": msg.id}}


def build_talk_graph() -> StateGraph:
    class S(TalkState, total=False):
        events: Annotated[list[dict[str, Any]], operator.add]  # type: ignore[misc]
        system_lines: Annotated[list[str], operator.add]  # type: ignore[misc]

    g = StateGraph(S)
    for fn in (
        load_person_record,
        record_caregiver_message,
        intake_agent,
        baseline_comparator,
        red_flag_rules,
        notify_nurse,
        decide_next,
        reply,
    ):
        g.add_node(fn.__name__, fn)
    g.add_edge(START, "load_person_record")
    g.add_edge("load_person_record", "record_caregiver_message")
    g.add_edge("record_caregiver_message", "intake_agent")
    g.add_edge("intake_agent", "baseline_comparator")
    g.add_edge("baseline_comparator", "red_flag_rules")
    g.add_edge("red_flag_rules", "notify_nurse")
    g.add_edge("notify_nurse", "decide_next")
    g.add_edge("decide_next", "reply")
    g.add_edge("reply", END)
    return g


_compiled = None


def compiled():
    global _compiled  # noqa: PLW0603
    if _compiled is None:
        _compiled = build_talk_graph().compile()
    return _compiled


def run_turn(patient_id: str, text: str, role_view: str = "caregiver"):
    """Generator: yields ('event', dict) as nodes run, then ('final', state).

    The graph runs in one worker thread (contextvars-safe under StreamingResponse).
    """
    from core.trace import run_in_thread

    yield from run_in_thread(lambda: _run_turn(patient_id, text, role_view))


def _run_turn(patient_id: str, text: str, role_view: str):
    from core.trace import tagged

    s = conv.open_session(patient_id)
    final: dict[str, Any] = {}
    with tagged(dialog_id=s.dialog_id, thread_id=s.thread_id):
        try:
            for mode, chunk in compiled().stream(
                {"patient_id": patient_id, "text": text, "role_view": role_view},
                stream_mode=["custom", "updates"],
            ):
                if mode == "custom":
                    yield "event", chunk
                else:
                    for _node, upd in chunk.items():
                        if isinstance(upd, dict):
                            final.update(
                                {
                                    k: v
                                    for k, v in upd.items()
                                    if k not in ("events", "system_lines")
                                }
                            )
                            if "events" in upd:
                                final.setdefault("events", []).extend(upd["events"])
                            if "system_lines" in upd:
                                final.setdefault("system_lines", []).extend(upd["system_lines"])
        except LLMUnavailable as e:
            conv.append(
                patient_id, "system", f"無法繼續：{e}", s.session_id, kind="error", author="system"
            )
            yield "error", {"detail": str(e)}
            return
    yield "final", final
