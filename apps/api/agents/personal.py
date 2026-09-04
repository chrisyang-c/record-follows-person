"""One deep agent per resident (CLAUDE.md §5).

The agent has NO state of its own: its only memory is records/{patient_id}/ (read-only via
FilesystemMiddleware). Any write goes through record.write_timeline (graph node
`timeline_write`), never through the agent. Subagents return structured results only.

With MODEL_PROVIDER=mock (or a missing key) the same graph is built on a fake chat model
so wiring, tool boundaries and interrupt config are testable without network.
and interrupt config are testable without network."""

from __future__ import annotations

from datetime import date
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.middleware import FilesystemMiddleware, SubAgent
from langchain_core.tools import tool

from agents.subagents import familiarization_writer, handoff_packager, trend_analyzer
from core.settings import get_settings
from record.store import get_store

READ_ONLY_TOOLS = ["read_file", "ls", "glob", "grep"]


def _model() -> Any:
    """Every deep agent gets its model from settings.get_model() (ChatOpenAI when
    MODEL_PROVIDER=openai; a fake chat model when mock or the key is missing)."""
    return get_settings().get_model()


# --- tools that wrap the pure subagent implementations (structured in / structured out) ---


def make_tools(patient_id: str) -> list[Any]:
    store = get_store()

    @tool
    def analyze_trends(since: str, until: str) -> dict:
        """Compute 8-dimension trends between two ISO dates. Returns a TrendReport."""
        obs = store.load_timeline(
            patient_id, since=date.fromisoformat(since), kinds={"observation"}
        )
        inc = [
            e.id
            for e in store.load_timeline(
                patient_id, since=date.fromisoformat(since), kinds={"incident"}
            )
        ]
        return trend_analyzer.analyze(
            patient_id,
            obs,
            inc,
            date.fromisoformat(since),
            date.fromisoformat(until),  # type: ignore[arg-type]
        ).model_dump(mode="json")

    @tool
    def render_document_page(doc_type: str, since: str) -> dict:
        """Render a RoundPage (doc_type='round_page') from the record. Human approval required."""
        profile = store.load_profile(patient_id)
        baseline = store.load_baseline(patient_id)
        s = date.fromisoformat(since)
        obs = store.load_timeline(patient_id, since=s, kinds={"observation"})
        inc = [e.id for e in store.load_timeline(patient_id, since=s, kinds={"incident"})]
        report = trend_analyzer.analyze(patient_id, obs, inc, s, date.today())  # type: ignore[arg-type]
        orders = store.load_timeline(patient_id, kinds={"order"})
        page = familiarization_writer.write(profile, baseline, report, orders, s)  # type: ignore[arg-type]
        return page.model_dump(mode="json")

    @tool
    def package_handoff(incident_file_id: str, route: str, confirmed_by: str) -> dict:
        """Package a HandoffPage (phone ISBAR / visit page) from an approved IncidentFile."""
        profile = store.load_profile(patient_id)
        baseline = store.load_baseline(patient_id)
        inc = store.get_document(patient_id, incident_file_id)
        assert inc is not None and inc.doc_type == "incident_file"
        return handoff_packager.package(profile, baseline, inc, route, confirmed_by).model_dump(
            mode="json"
        )  # type: ignore[arg-type]

    return [analyze_trends, render_document_page, package_handoff]


def subagent_specs(tools: list[Any]) -> list[SubAgent]:
    by_name = {t.name: t for t in tools}
    return [
        SubAgent(
            name="trend_analyzer",
            description=(
                "對八維度算 7/30 天與自上次巡診的趨勢，標出跨維度同時變化。只回結構化結果。"
            ),
            system_prompt="你只回傳 analyze_trends 的結果，不寫文章、不判斷、不建議。",
            tools=[by_name["analyze_trends"]],
        ),
        SubAgent(
            name="familiarization_writer",
            description=(
                "產出 RoundPage 四段：這是誰、變了什麼、上次醫囑做了沒、請醫師確認的事。一頁上限。"
            ),
            system_prompt=(
                "呼叫 render_document_page 後只回傳其結構化結果。④ 只能是提問，不得有診斷或處置。"
            ),
            tools=[by_name["render_document_page"]],
        ),
        SubAgent(
            name="handoff_packager",
            description="從同一份紀錄取後送頁／陪診頁切片。",
            system_prompt="呼叫 package_handoff 後只回傳其結構化結果。",
            tools=[by_name["package_handoff"]],
        ),
    ]


SYSTEM_PROMPT = """你是這位住民的專屬 agent。你沒有自己的狀態；
你唯一的記憶是 records/ 目錄裡的紀錄。
你只做兩件事：把東西寫進紀錄（透過流程的 timeline_write，不是你自己），或把紀錄講給某個人聽。
你對 timeline/ 只有讀取權限。任何文件輸出都是草稿，需要人確認。你不下診斷、不建議處置。"""


def build_personal_agent(patient_id: str, model: Any | None = None):
    root = get_settings().records_root / patient_id
    backend = FilesystemBackend(root_dir=str(root))
    tools = make_tools(patient_id)
    return create_deep_agent(
        model=model or _model(),
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        backend=backend,
        middleware=[FilesystemMiddleware(backend=backend, tools=READ_ONLY_TOOLS)],  # 唯讀
        subagents=subagent_specs(tools),
        interrupt_on={"render_document_page": {"allowed_decisions": ["approve", "edit", "reject"]}},
        name=f"personal_agent_{patient_id}",
    )
