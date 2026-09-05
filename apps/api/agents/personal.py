"""One deep agent per resident (CLAUDE.md §5) — and the proof that it runs.

The agent has NO state of its own: its only memory is records/{patient_id}/ (read-only via
FilesystemMiddleware). Writes go through record.write_timeline (graph node `timeline_write`).

`run_task()` is how the graphs use it: the main agent is asked to delegate to ONE named
subagent; the subagent calls its structured tools; the tools store their output in ARTIFACTS
and write trace entries tagged with the run id. The graph node reads the artifact — never the
model's prose. If the subagent does not deliver, `AgentDidNotDeliver` is raised and surfaces
in the UI (no silent fallback). Under MODEL_PROVIDER=mock (pytest/CI only) a scripted double
calls the same tools in order and the trace says `scripted: true`.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.middleware import FilesystemMiddleware, SubAgent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from pydantic import ValidationError
from record_schema import ISBAR

from agents.subagents import familiarization_writer as fw
from agents.subagents import handoff_packager, trend_analyzer
from core.llm import LLMUnavailable
from core.settings import get_settings
from core.trace import recent, tagged, trace
from record.store import get_store

READ_ONLY_TOOLS = ["read_file", "ls", "glob", "grep"]

# (patient_id, tool_name) -> last structured output of that tool in this process
# One deep-agent run at a time (trend_analyzer ×N / familiarization_writer ×N): each run is several
# model calls and parallel runs trip the provider TPM limit (30k). Streams keep flowing meanwhile.
_DEEP_AGENT_LOCK = threading.Lock()
ARTIFACTS: dict[tuple[str, str], dict[str, Any]] = {}
# (patient_id, key) -> inputs a tool needs that are not yet in the record
PENDING: dict[tuple[str, str], Any] = {}


class AgentDidNotDeliver(RuntimeError):
    """The subagent finished without producing its artifact. Surface it; never fall back."""


def _model() -> Any:
    return get_settings().get_model()


# --- tools used by the subagents (structured in / structured out, every call traced) -----


def make_tools(patient_id: str) -> list[Any]:
    store = get_store()

    @tool
    def analyze_trends(since: str, until: str) -> dict:
        """Compute 8-dimension trends between two ISO dates for this resident (TrendReport)."""
        s, u = date.fromisoformat(since), date.fromisoformat(until)
        obs = store.load_timeline(patient_id, since=s, kinds={"observation"})
        inc = [e.id for e in store.load_timeline(patient_id, since=s, kinds={"incident"})]
        report = trend_analyzer.analyze(
            patient_id,
            obs,
            inc,
            s,
            u,
            baseline=store.load_baseline(patient_id),  # type: ignore[arg-type]
        )
        out = report.model_dump(mode="json")
        ARTIFACTS[(patient_id, "analyze_trends")] = out
        trace(
            "subagent.tool",
            subagent="trend_analyzer",
            tool="analyze_trends",
            patient_id=patient_id,
            args={"since": since, "until": until},
            output={
                "lines": [line["summary"] for line in out["lines"]],
                "cross": out["cross_dimension_signal"],
            },
        )
        return out

    @tool
    def get_round_context(since: str) -> dict:
        """Facts for the RoundPage: profile, baseline, changed dimensions + evidence ids, orders."""
        ctx = fw.build_context(patient_id, date.fromisoformat(since))
        PENDING[(patient_id, "round_ctx")] = ctx
        public = {k: v for k, v in ctx.items() if not k.startswith("_")}
        public["evidence"] = {
            d: rows[-4:] for d, rows in ctx["evidence"].items()
        }  # compact for the model
        trace(
            "subagent.tool",
            subagent="familiarization_writer",
            tool="get_round_context",
            patient_id=patient_id,
            args={"since": since},
            output={
                "changed_dimensions": list(ctx["changed_dimensions"]),
                "orders": len(ctx["last_orders"]),
                "incidents": len(ctx["incidents"]),
                "observations": ctx["observation_count"],
            },
        )
        return public

    @tool
    def submit_round_page(
        who: str,
        changes: list[dict[str, Any]],
        questions: list[str],
        order_followup: list[dict[str, Any]] | None = None,
        no_change_note: str | None = None,
    ) -> dict:
        """Submit the RoundPage you wrote. changes: [{dimension, text, evidence_refs}] only for
        changed_dimensions; order_followup: [{order_id, text, done, effective, note}];
        questions: 2–4 問句. Returns {ok} or {error} — fix and submit again."""
        ctx = PENDING.get((patient_id, "round_ctx"))
        if not ctx:
            return {"error": "先呼叫 get_round_context(since)"}
        try:
            sub = fw.RoundPageSubmission(
                who=who,
                changes=[fw.ChangeLine(**c) for c in changes],
                no_change_note=no_change_note,
                order_followup=[fw.FollowUpLine(**f) for f in (order_followup or [])],
                questions=questions,
            )
            page = fw.validate_and_assemble(ctx, sub)
        except (ValueError, ValidationError) as e:
            trace(
                "subagent.tool",
                subagent="familiarization_writer",
                tool="submit_round_page",
                patient_id=patient_id,
                error=str(e)[:300],
            )
            return {"error": str(e)[:600]}
        out = page.model_dump(mode="json")
        ARTIFACTS[(patient_id, "submit_round_page")] = out
        trace(
            "subagent.tool",
            subagent="familiarization_writer",
            tool="submit_round_page",
            patient_id=patient_id,
            args={
                "who": who,
                "changes": [c.get("dimension") for c in changes],
                "questions": questions,
            },
            output={
                "page_id": page.id,
                "changes": len(page.changes),
                "questions": len(page.questions),
            },
        )
        return {
            "ok": True,
            "page_id": page.id,
            "changes": len(page.changes),
            "questions": len(page.questions),
        }

    @tool
    def package_handoff(route: str, confirmed_by: str) -> dict:
        """Package a HandoffPage (phone ISBAR / visit page) for the ISBAR just confirmed."""
        pending = PENDING.get((patient_id, "handoff"))
        if not pending:
            return {"error": "no ISBAR pending for this resident"}
        profile = store.load_profile(patient_id)
        baseline = store.load_baseline(patient_id)
        page = handoff_packager.package(
            profile,
            baseline,
            ISBAR.model_validate(pending["isbar"]),
            pending["generated_from"],
            route,
            confirmed_by,  # type: ignore[arg-type]
        )
        out = page.model_dump(mode="json")
        ARTIFACTS[(patient_id, "package_handoff")] = out
        trace(
            "subagent.tool",
            subagent="handoff_packager",
            tool="package_handoff",
            patient_id=patient_id,
            args={"route": route, "confirmed_by": confirmed_by},
            output={"variant": out["variant"], "what_happened": out["what_happened"]},
        )
        return out

    return [analyze_trends, get_round_context, submit_round_page, package_handoff]


# --- 「問我的紀錄」(VISION §11.2 Retrieve): answers come only from the record -----------------

ADVICE_WORDS = (
    "建議",
    "應該",
    "最好",
    "需要去",
    "可能是",
    "代表",
    "表示",
    "屬於正常",
    "屬於異常",
    "偏高",
    "偏低",
    "太高",
    "太低",
    "危險",
    "沒問題",
)
NOT_FOUND = "紀錄裡沒有這件事。"


def _line_text(e: Any) -> str:
    if e.kind == "observation":
        sb = e.minimal_sbar.s if e.minimal_sbar else ""
        return f"觀察：{e.observation.raw_text}" + (f"（{sb}）" if sb else "")
    if e.kind == "incident":
        return f"事故：{e.summary}"
    if e.kind == "encounter":
        return f"巡診：{e.summary}"
    if e.kind == "order":
        return f"醫囑：{e.raw_text}"
    if e.kind == "life_event":
        return f"{e.title}：{e.summary}（{e.facility}）"
    return ""


def _doc_lines(d: Any) -> list[str]:
    if d.doc_type == "round_page":
        who = getattr(d, "who", "") or ""
        return [f"熟悉頁：{who}"] + [
            f"熟悉頁：{getattr(c, 'text', None) or getattr(c, 'summary', '')}" for c in d.changes
        ]
    if d.doc_type == "incident_file":
        return [f"事件資訊包：{d.caregiver_section.raw_text}"]
    if d.doc_type == "caregiver_notes":
        return [f"注意事項：{it}" for it in d.items]
    return []


_STOP = set(
    "我你他她它們的了嗎呢吧啊有沒是在會不曾以前過做去到跟和與很都還又也就把被讓給對於從"
    "這那些什麼怎麼哪裡誰請問一下"
)


def _bigrams(text: str) -> set[str]:
    t = "".join(ch for ch in text if ch.isalnum())
    return {t[i : i + 2] for i in range(len(t) - 1)}


def _query_grams(query: str) -> set[str]:
    """Bigrams of the content words only: 「我以前有做過心臟手術嗎」→ {心臟, 臟手, 手術}."""
    t = "".join(ch for ch in query if ch.isalnum() and ch not in _STOP)
    return {t[i : i + 2] for i in range(len(t) - 1)}


def retrieve_lines(patient_id: str, query: str, limit: int = 8) -> list[dict[str, Any]]:
    """Keyword retrieval over timeline + documents; each hit is a record line with its id."""
    store = get_store()
    q = _query_grams(query)
    if not q:
        return []
    hits: list[tuple[int, dict[str, Any]]] = []
    for e in store.load_timeline(patient_id):
        text = _line_text(e)
        score = len(q & _bigrams(text + getattr(e, "title", "")))
        if score:
            hits.append(
                (
                    score,
                    {
                        "id": e.id,
                        "date": e.ts.date().isoformat(),
                        "kind": e.kind,
                        "text": text[:160],
                    },
                )
            )
    for d in store.load_documents(patient_id):
        for i, text in enumerate(_doc_lines(d)):
            score = len(q & _bigrams(text))
            if score:
                hits.append(
                    (
                        score,
                        {
                            "id": f"{d.id}#{i}",
                            "date": d.generated_at.date().isoformat(),
                            "kind": d.doc_type,
                            "text": text[:160],
                        },
                    )
                )
    hits.sort(key=lambda h: (-h[0], h[1]["date"]))
    return [h for _s, h in hits[:limit]]


def make_ask_tools(patient_id: str) -> list[Any]:
    @tool
    def retrieve(query: str) -> dict:
        """Search this person's own record (timeline + documents) for lines matching the query.
        Returns {hits:[{id, date, kind, text}]}; only these ids may be cited by submit_answer."""
        hits = retrieve_lines(patient_id, query)
        seen = PENDING.setdefault((patient_id, "ask_hits"), {})
        for h in hits:
            seen[h["id"]] = h
        trace(
            "subagent.tool",
            subagent="personal_agent",
            tool="retrieve",
            patient_id=patient_id,
            args={"query": query},
            output={"hits": [h["id"] for h in hits]},
        )
        return {"hits": hits}

    @tool
    def submit_answer(sentences: list[dict[str, Any]], found: bool = True) -> dict:
        """Submit the answer: sentences=[{text, source_ids}] — every sentence must cite ≥1 id
        returned by retrieve; found=false with no sentences when the record has nothing.
        No advice, no interpretation of values. Returns {ok} or {error}."""
        seen = PENDING.get((patient_id, "ask_hits"), {})
        out_sentences = []
        for sdict in sentences or []:
            text = str(sdict.get("text", "")).strip()
            ids = [i for i in (sdict.get("source_ids") or []) if i in seen]
            if not text:
                continue
            if not ids:
                return {
                    "error": f"「{text[:30]}」沒有引用 retrieve 回來的來源行；"
                    "每句都要有 source_ids，紀錄裡沒有就 found=false"
                }
            if any(w in text for w in ADVICE_WORDS):
                return {
                    "error": f"「{text[:30]}」含建議或解讀"
                    f"（{[w for w in ADVICE_WORDS if w in text]}）；只複述紀錄裡有的事"
                }
            from core.llm import scrub_clinical_language

            out_sentences.append(
                {"text": scrub_clinical_language(text), "sources": [seen[i] for i in ids]}
            )
        if not out_sentences:
            found = False
        out = {
            "found": found,
            "sentences": out_sentences if found else [],
            "fallback": None if found else NOT_FOUND,
        }
        ARTIFACTS[(patient_id, "submit_answer")] = out
        trace(
            "subagent.tool",
            subagent="personal_agent",
            tool="submit_answer",
            patient_id=patient_id,
            output={"found": found, "sentences": len(out_sentences)},
        )
        return {"ok": True, **out}

    return [retrieve, submit_answer]


ASK_PROMPT = """你是這個人自己的紀錄 agent，替本人回答「我的紀錄裡有什麼」。
規則：
1. 先用 retrieve(query) 找紀錄（可以換不同關鍵字多找幾次）。
2. 只回答紀錄裡有的事：每一句都要在 source_ids 引用 retrieve 回來的 id；
   紀錄裡沒有就 submit_answer(sentences=[], found=false)，不要猜。
3. 不給建議、不解讀數值、不下判斷（不寫「建議」「應該」「正常」「偏高」）。
4. 用本人聽得懂的白話，每句附日期。最後一定要呼叫 submit_answer。"""


@lru_cache(maxsize=16)
def _ask_agent(patient_id: str):
    root = get_settings().records_root / patient_id
    backend = FilesystemBackend(root_dir=str(root))
    return create_deep_agent(
        model=_model(),
        tools=make_ask_tools(patient_id),
        system_prompt=ASK_PROMPT,
        backend=backend,
        middleware=[FilesystemMiddleware(backend=backend, tools=READ_ONLY_TOOLS)],
        name=f"personal_agent_ask_{patient_id}",
    )


def ask_record(
    patient_id: str, question: str, who: str | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """「問我的紀錄」：the person's agent retrieves and answers with source lines only."""
    ARTIFACTS.pop((patient_id, "submit_answer"), None)
    PENDING[(patient_id, "ask_hits")] = {}
    s = get_settings()
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    meta: dict[str, Any] = {
        "task": "ask",
        "patient_id": patient_id,
        "run_id": run_id,
        "who": who,
        "provider": s.effective_provider,
        "model": s.MODEL_PINNED if s.llm_enabled else "mock",
        "scripted": False,
        "ai_turns": 0,
    }
    t0 = time.time()
    with _DEEP_AGENT_LOCK, tagged(run_id=run_id, dialog_id=f"ask:{patient_id}"):
        if s.MODEL_PROVIDER == "mock":
            meta["scripted"] = True
            tools = {t.name: t for t in make_ask_tools(patient_id)}
            hits = tools["retrieve"].invoke({"query": question})["hits"]
            tools["submit_answer"].invoke(
                {
                    "sentences": [
                        {"text": f"{h['date']}：{h['text']}", "source_ids": [h["id"]]}
                        for h in hits[:3]
                    ],
                    "found": bool(hits),
                }
            )
        elif not s.llm_enabled:
            raise LLMUnavailable(f"MODEL_PROVIDER={s.MODEL_PROVIDER} 但沒有 API key")
        else:
            result = _ask_agent(patient_id).invoke(
                {"messages": [HumanMessage(content=question)]}, config={"recursion_limit": 30}
            )
            meta["ai_turns"] = sum(
                1 for m in result.get("messages", []) if isinstance(m, AIMessage)
            )
        calls = [e for e in recent(kind="subagent.tool", limit=1000) if e.get("run_id") == run_id]
        meta["tool_counts"] = dict(Counter(e["tool"] for e in calls))
        meta["duration_s"] = round(time.time() - t0, 2)
        artifact = ARTIFACTS.get((patient_id, "submit_answer"))
        if artifact is None:
            trace(
                "deep_agent.run",
                prompt=question,
                error="personal_agent did not submit_answer",
                **meta,
            )
            raise AgentDidNotDeliver(f"personal agent 沒有回答（run {run_id}，見 /trace）")
        trace("deep_agent.run", prompt=question, **meta)
    return artifact, meta


WRITER_PROMPT = """你是 familiarization_writer，替這位住民寫巡診「熟悉頁」（RoundPage）
   給醫師。你要自己寫句子，不是抄結構。
步驟（工具都要真的呼叫；先讀紀錄，讀到的內容在後面每一步都不會變）：
1. get_round_context(since=<since>)：profile、基線、changed_dimensions（有變化的維度）、
   evidence（每個維度的紀錄 id＋日期＋照護者原話）、incidents、last_orders。
2. analyze_trends(since=<since>, until=<今天>)：自上次巡診的趨勢。
3. analyze_trends(since=<今天-6 天>, until=<今天>)：近 7 天的趨勢。
4. submit_round_page(...)。回 error 就依訊息修正後再送一次。
寫法：
① who：一句話的人（誰、幾歲、慢性病、他的樣子），再加一句「這個月請特別看…」。
   不要列基線清單（程式會列）。
② changes：只寫 changed_dimensions 裡的維度，每個維度一句，用照護者原話與日期說明變化（例：
   「8/30 起飯只吃一半，9/3『只吃幾口』」），
   evidence_refs 從 evidence 挑最能支持這句的 1–3 筆 id。正常的維度不要寫。
   changed_dimensions 是空的就不寫 changes，
   no_change_note 寫「本期八維度皆與基線一致」。
③ order_followup：逐條回應 last_orders（order_id 要對）：做了沒（done）、有效嗎（effective，
   依 follow_up 與趨勢），note 一句。
④ questions：2–4 條「請醫師確認」的問句，每條以「？」結尾，只提問、不下診斷、不建議處置、
   不寫檢傷等級。
全部用繁體中文，不用醫療術語堆砌。"""


def subagent_specs(tools: list[Any]) -> list[SubAgent]:
    by_name = {t.name: t for t in tools}
    return [
        SubAgent(
            name="trend_analyzer",
            description=(
                "對八維度算 7/30 天與自上次巡診的趨勢，標出跨維度同時變化。只回結構化結果。"
            ),
            system_prompt=(
                "你只呼叫 analyze_trends(since, until) 一次，然後回覆「完成」。"
                "不寫文章、不判斷、不建議。"
            ),
            tools=[by_name["analyze_trends"]],
        ),
        SubAgent(
            name="familiarization_writer",
            description=(
                "寫 RoundPage 四段：這是誰、變了什麼（只寫有變化的維度）、上次醫囑做了沒、"
                "請醫師確認的事。一頁上限。"
            ),
            system_prompt=WRITER_PROMPT,
            tools=[
                by_name["analyze_trends"],
                by_name["get_round_context"],
                by_name["submit_round_page"],
            ],
        ),
        SubAgent(
            name="handoff_packager",
            description="從同一份紀錄取後送頁／陪診頁切片。",
            system_prompt="你只呼叫 package_handoff(route, confirmed_by) 一次，然後回覆「完成」。",
            tools=[by_name["package_handoff"]],
        ),
    ]


SYSTEM_PROMPT = """你是這位住民的專屬 agent。你沒有自己的狀態；
   你唯一的記憶是 records/ 目錄裡的紀錄。
你只做兩件事：把東西寫進紀錄（透過流程的 timeline_write，不是你自己），或把紀錄講給某個人聽。
你對 timeline/ 只有讀取權限。任何文件輸出都是草稿，需要人確認。你不下診斷、不建議處置。
收到任務時，用 task 工具把工作派給指定的子代理（subagent_type），
   把任務裡的日期與參數原封不動寫進 description；
不要自己算、不要自己讀檔；子代理回覆後只回「完成」。"""


def build_personal_agent(patient_id: str, model: Any | None = None):
    root = get_settings().records_root / patient_id
    backend = FilesystemBackend(root_dir=str(root))
    tools = make_tools(patient_id)
    return create_deep_agent(
        model=model or _model(),
        tools=[],  # the main agent only delegates (task); document tools live on the subagents
        system_prompt=SYSTEM_PROMPT,
        backend=backend,
        middleware=[FilesystemMiddleware(backend=backend, tools=READ_ONLY_TOOLS)],  # 唯讀
        subagents=subagent_specs(tools),
        # CLAUDE.md §5: human approval for direct page rendering by the main agent (standalone use);
        # in the graphs the human gate is ◇head_nurse_edit_list (docs/DECISIONS.md).
        interrupt_on={"render_document_page": {"allowed_decisions": ["approve", "edit", "reject"]}},
        name=f"personal_agent_{patient_id}",
    )


@lru_cache(maxsize=16)
def _agent(patient_id: str):
    return build_personal_agent(patient_id)


TASKS: dict[str, tuple[str, str, str]] = {
    "trend": (
        "trend_analyzer",
        "analyze_trends",
        '請用 task 工具把這件事派給 subagent_type="trend_analyzer"：'
        "分析自 {since} 到 {until} 的八維度趨勢"
        '（子代理要呼叫 analyze_trends(since="{since}", until="{until}")）。'
        "完成後回「完成」。",
    ),
    "round_page": (
        "familiarization_writer",
        "submit_round_page",
        '請用 task 工具把這件事派給 subagent_type="familiarization_writer"：'
        "寫自 {since} 起的 RoundPage（today={today}；子代理要先呼叫 "
        'get_round_context(since="{since}")，再 analyze_trends 兩次，最後 submit_round_page）。'
        "完成後回「完成」。",
    ),
    "handoff": (
        "handoff_packager",
        "package_handoff",
        '請用 task 工具把這件事派給 subagent_type="handoff_packager"：打包後送頁'
        '（子代理要呼叫 package_handoff(route="{route}", confirmed_by="{confirmed_by}")）'
        "。完成後回「完成」。",
    ),
}


def _invoke_with_rate_limit_retry(
    patient_id: str, prompt: str, attempts: int = 4
) -> dict[str, Any]:
    """Provider TPM limits (429) abort the run; wait the time the provider asks for, then retry."""
    import re

    for i in range(attempts):
        try:
            return _agent(patient_id).invoke(
                {"messages": [HumanMessage(content=prompt)]}, config={"recursion_limit": 60}
            )
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if "429" not in msg and "rate limit" not in msg.lower():
                raise
            m = re.search(r"try again in ([\d.]+)\s*(ms|s)", msg)
            wait = float(m.group(1)) / (1000 if m and m.group(2) == "ms" else 1) if m else 20.0
            wait = min(max(wait + 2.0, 5.0), 65.0)
            trace(
                "deep_agent.rate_limited",
                patient_id=patient_id,
                attempt=i + 1,
                wait_s=wait,
                error=msg[:200],
            )
            if i == attempts - 1:
                raise
            time.sleep(wait)
    raise RuntimeError("unreachable")


def _scripted(kind: str, patient_id: str, **kw: Any) -> None:
    """MODEL_PROVIDER=mock test double: call the subagent's tools in the documented order."""
    tools = {t.name: t for t in make_tools(patient_id)}
    if kind == "trend":
        tools["analyze_trends"].invoke({"since": kw["since"], "until": kw["until"]})
    elif kind == "round_page":
        today = kw["today"]
        week = (date.fromisoformat(today) - timedelta(days=6)).isoformat()
        tools["analyze_trends"].invoke({"since": kw["since"], "until": today})
        tools["analyze_trends"].invoke({"since": max(kw["since"], week), "until": today})
        tools["get_round_context"].invoke({"since": kw["since"]})
        draft = fw.draft_from_facts(PENDING[(patient_id, "round_ctx")])
        tools["submit_round_page"].invoke(draft.model_dump(mode="json"))
    else:
        tools["package_handoff"].invoke({"route": kw["route"], "confirmed_by": kw["confirmed_by"]})


def run_task(
    kind: str, patient_id: str, thread_id: str | None = None, **kw: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the personal deep agent for one task; return (artifact, run_meta).

    run_meta: which subagents the model delegated to (from its messages), the subagent's tool
    calls (from the trace, by run id), model turns, duration; `scripted` under mock."""
    subagent, tool_name, template = TASKS[kind]
    ARTIFACTS.pop((patient_id, tool_name), None)
    if kind == "round_page":
        kw.setdefault("today", datetime.now(UTC).date().isoformat())
    prompt = template.format(**kw)
    s = get_settings()
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    meta: dict[str, Any] = {
        "task": kind,
        "patient_id": patient_id,
        "run_id": run_id,
        "expected_subagent": subagent,
        "provider": s.effective_provider,
        "model": s.MODEL_PINNED if s.llm_enabled else "mock",
        "subagents_called": [],
        "main_agent_tool_calls": [],
        "ai_turns": 0,
        "scripted": False,
    }
    t0 = time.time()
    try:
        from langgraph.config import get_stream_writer

        _w = get_stream_writer()
    except Exception:  # noqa: BLE001
        _w = None
    label = {
        "trend": "trend_analyzer 分析八維度",
        "round_page": "familiarization_writer 撰寫四段",
        "handoff": "handoff_packager 準備後送頁",
    }[kind]
    if _w:
        _w(
            {
                "type": "tool_call",
                "name": subagent,
                "patient_id": patient_id,
                "summary": f"{label}（{patient_id}）",
                "plain": label,
            }
        )
    with _DEEP_AGENT_LOCK, tagged(thread_id=thread_id, run_id=run_id):
        if s.MODEL_PROVIDER == "mock":
            meta["scripted"] = True
            _scripted(kind, patient_id, **kw)
        elif not s.llm_enabled:
            raise LLMUnavailable(
                f"MODEL_PROVIDER={s.MODEL_PROVIDER} 但沒有 API key，deep agent 無法執行"
            )
        else:
            result = _invoke_with_rate_limit_retry(patient_id, prompt)
            for m in result.get("messages", []):
                if isinstance(m, AIMessage):
                    meta["ai_turns"] += 1
                    for tc in m.tool_calls or []:
                        meta["main_agent_tool_calls"].append(tc["name"])
                        if tc["name"] == "task":
                            meta["subagents_called"].append(tc["args"].get("subagent_type"))
            meta["final"] = (
                str(result["messages"][-1].content)[:200] if result.get("messages") else ""
            )
        calls = [e for e in recent(kind="subagent.tool", limit=1000) if e.get("run_id") == run_id]
        meta["tool_counts"] = dict(Counter(e["tool"] for e in calls))
        meta["tool_errors"] = [e["error"] for e in calls if e.get("error")]
        meta["duration_s"] = round(time.time() - t0, 2)
        artifact = ARTIFACTS.get((patient_id, tool_name))
        if artifact is None:
            trace(
                "deep_agent.run",
                prompt=prompt,
                error=f"{subagent} did not deliver {tool_name}",
                **meta,
            )
            raise AgentDidNotDeliver(
                f"{subagent} 子代理沒有產出 {tool_name}（run {run_id}，見 /trace）"
            )
        trace("deep_agent.run", prompt=prompt, **meta)
    if _w:
        _w(
            {
                "type": "node_end",
                "name": subagent,
                "patient_id": patient_id,
                "summary": f"{label}（{patient_id}）：{meta['tool_counts']}",
                "plain": f"{label} 完成",
                "ms": int(meta["duration_s"] * 1000),
            }
        )
    return artifact, meta


def agent_note(page_meta: dict[str, Any], trend_meta: dict[str, Any] | None = None) -> str:
    """Footer for the RoundPage: who wrote it and which tools it called how many times."""
    tc = page_meta.get("tool_counts", {})
    scripted = "，scripted test double" if page_meta.get("scripted") else ""
    note = (
        f"由 familiarization_writer 子代理產生（{page_meta.get('model')}{scripted}）："
        f"呼叫 trend_analyzer（analyze_trends）{tc.get('analyze_trends', 0)} 次、"
        f"get_round_context {tc.get('get_round_context', 0)} 次、"
        f"submit_round_page {tc.get('submit_round_page', 0)} 次"
    )
    if trend_meta:
        n = trend_meta.get("tool_counts", {}).get("analyze_trends", 0)
        note += f"；trend_analyzer 子代理另呼叫 analyze_trends {n} 次"
    return note + f"。run {page_meta.get('run_id')}"
