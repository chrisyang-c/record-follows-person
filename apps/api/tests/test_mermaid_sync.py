"""Mermaid node ids are the single source of graph node names (CLAUDE.md §0.2, §8, §11)."""

from __future__ import annotations

import re
from pathlib import Path

from graphs.path_a import build_path_a
from graphs.path_b import build_round_graph, build_shift_graph

DOCS = Path(__file__).resolve().parents[3] / "docs"
_NODE = re.compile(r"\b(\w+)(?:\[\(|\[|\{\{\"|\{)\s*◇?\s*([a-z_0-9]+)")


def mermaid_names(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return {m.group(2) for m in _NODE.finditer(text) if m.group(2) not in ("START", "END")}


def graph_names(builder) -> set[str]:
    return {n for n in builder().compile().get_graph().nodes if n not in ("__start__", "__end__")}


def test_path_a_nodes_match_mermaid():
    assert mermaid_names(DOCS / "langgraph_path_a_incident.mermaid") == graph_names(build_path_a)


def test_path_b_nodes_match_mermaid():
    names = mermaid_names(DOCS / "langgraph_path_b_routine_round.mermaid")
    assert names == graph_names(build_shift_graph) | graph_names(build_round_graph)
