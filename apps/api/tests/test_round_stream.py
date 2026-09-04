"""runner.start_stream: round prep streams node/subagent events, then the interrupt snapshot."""

from __future__ import annotations

from graphs import runner


def test_round_start_stream_yields_events_then_snapshot(records_root):
    kinds, done = [], None
    for kind, data in runner.start_stream("round", "ALL", {"round_date": "2026-09-05"}):
        kinds.append((kind, data.get("name") or data.get("type")))
        if kind == "done":
            done = data
    assert done is not None and done["status"] == "interrupted"
    assert done["interrupt"]["type"] == "head_nurse_edit_list"
    names = [n for k, n in kinds if k == "event"]
    assert "roster_agent" in names
    assert any(n in ("trend_analyzer", "familiarization_writer") for n in names)
