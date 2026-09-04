from __future__ import annotations

from deepagents.middleware import FilesystemMiddleware

from agents.personal import READ_ONLY_TOOLS, build_personal_agent, make_tools, subagent_specs


def test_personal_agent_builds_in_mock_mode_and_is_read_only(records_root):
    agent = build_personal_agent("P001")
    assert agent is not None
    names = set(agent.get_graph().nodes)
    assert "model" in names or "model_request" in names or len(names) > 2
    fm = FilesystemMiddleware(tools=READ_ONLY_TOOLS)
    tool_names = {t.name for t in fm.tools}
    assert tool_names <= {"read_file", "ls", "glob", "grep"}
    assert not ({"write_file", "edit_file", "delete", "execute"} & tool_names)


def test_subagents_are_three_and_structured(records_root):
    specs = subagent_specs(make_tools("P001"))
    assert [s["name"] for s in specs] == [
        "trend_analyzer",
        "familiarization_writer",
        "handoff_packager",
    ]
    tools = make_tools("P001")
    report = next(t for t in tools if t.name == "analyze_trends").invoke(
        {"since": "2026-08-20", "until": "2026-09-05"}
    )
    assert report["patient_id"] == "P001" and report["lines"]
    page = next(t for t in tools if t.name == "render_document_page").invoke(
        {"doc_type": "round_page", "since": "2026-08-20"}
    )
    assert (
        page["doc_type"] == "round_page"
        and page["status"] == "draft"
        and len(page["questions"]) >= 1
    )
