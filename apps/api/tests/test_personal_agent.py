from __future__ import annotations

from deepagents.middleware import FilesystemMiddleware

from agents.personal import (
    READ_ONLY_TOOLS,
    build_personal_agent,
    make_tools,
    run_task,
    subagent_specs,
)
from core.trace import recent


def test_personal_agent_builds_in_mock_mode_and_is_read_only(records_root):
    agent = build_personal_agent("P001")
    assert agent is not None and len(set(agent.get_graph().nodes)) > 2
    fm = FilesystemMiddleware(tools=READ_ONLY_TOOLS)
    tool_names = {t.name for t in fm.tools}
    assert tool_names <= {"read_file", "ls", "glob", "grep"}
    assert not ({"write_file", "edit_file", "delete", "execute"} & tool_names)


def test_three_subagents_and_their_structured_tools(records_root):
    tools = make_tools("P001")
    assert {t.name for t in tools} == {
        "analyze_trends",
        "get_round_context",
        "submit_round_page",
        "package_handoff",
    }
    specs = subagent_specs(tools)
    assert [s["name"] for s in specs] == [
        "trend_analyzer",
        "familiarization_writer",
        "handoff_packager",
    ]
    writer = next(s for s in specs if s["name"] == "familiarization_writer")
    assert {t.name for t in writer["tools"]} == {
        "analyze_trends",
        "get_round_context",
        "submit_round_page",
    }
    ctx = next(t for t in tools if t.name == "get_round_context").invoke({"since": "2026-08-20"})
    assert "intake" in ctx["changed_dimensions"] and ctx["evidence"]["intake"]
    # the writer may only write changed dimensions; a wrong submission is rejected with a message
    bad = next(t for t in tools if t.name == "submit_round_page").invoke(
        {
            "who": "王伯",
            "changes": [{"dimension": "skin", "text": "x", "evidence_refs": []}],
            "questions": ["ok？"],
        }
    )
    assert "error" in bad and "changed_dimensions" in bad["error"]


def test_run_task_under_mock_is_a_scripted_double_and_traced(records_root):
    page, meta = run_task("round_page", "P001", thread_id="t-test", since="2026-08-20")
    assert page["doc_type"] == "round_page" and page["status"] == "draft"
    assert all(c["is_abnormal"] for c in page["changes"]) and page["questions"]
    assert meta["scripted"] is True and meta["tool_counts"]["submit_round_page"] == 1
    assert (
        meta["tool_counts"]["analyze_trends"] == 2 and meta["tool_counts"]["get_round_context"] == 1
    )
    runs = [e for e in recent(kind="deep_agent.run") if e.get("run_id") == meta["run_id"]]
    assert runs and runs[0].get("thread_id") == "t-test"
