"""Render GET /debug/trace/{thread_id} as Markdown for docs/ACCEPTANCE.md / docs/TRACE.md.

uv run python -m eval.trace_md <thread_id> [--api http://localhost:8000] [--max 12]
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request


def _j(v, n=220):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s if len(s) <= n else s[: n - 1] + "…"


def _row(*cells: str) -> str:
    return "| " + " | ".join(str(c).replace("|", "／").replace("\n", " ") for c in cells) + " |"


def render(data: dict, max_rows: int = 12) -> str:
    c = data["counts"]
    out = [
        f"### thread `{data['thread_id']}`（{data['graph']}，{data['status']}）",
        "",
        f"LLM 呼叫 {c['llm_calls']} 次、deep agent 派工 {c['agent_runs']} 次、"
        f"subagent 工具呼叫 {c['subagent_tool_calls']} 次"
        + (f"；dialog `{data['dialog_id']}`" if data.get("dialog_id") else ""),
    ]
    if data["turns"]:
        out += [
            "",
            _row("#", "時間", "prompt 摘要", "模型輸出（問什麼）", "reason", "耗時"),
            "|---|---|---|---|---|---|",
        ]
        for i, t in enumerate(data["turns"][:max_rows], 1):
            o = t.get("output") or {}
            q = o.get("question") or ("ask=false" if o.get("ask") is False else "")
            reason = t.get("reason") or t.get("error") or ""
            out.append(
                _row(
                    i,
                    t["ts"][11:19],
                    _j(t["prompt_summary"], 160),
                    _j(q, 80),
                    _j(reason, 120),
                    f"{t.get('duration_ms', '')} ms",
                )
            )
    other = [x for x in data["llm_calls"] if x["kind"] != "llm.next_question"]
    if other:
        out += ["", _row("時間", "呼叫", "輸入摘要", "輸出摘要", "耗時"), "|---|---|---|---|---|"]
        for x in other[:max_rows]:
            outp = x.get("output") or x.get("error") or ""
            out.append(
                _row(
                    x["ts"][11:19],
                    f"`{x['kind']}`",
                    _j(x["prompt_summary"], 120),
                    _j(outp, 160),
                    f"{x.get('duration_ms', '')} ms",
                )
            )
    if data["agent_runs"]:
        out += [
            "",
            _row(
                "時間",
                "派工",
                "住民",
                "主 agent 派給",
                "subagent 工具呼叫",
                "模型回合",
                "耗時",
                "run",
            ),
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in data["agent_runs"][:max_rows]:
            subs = ", ".join(r.get("subagents_called") or [])
            out.append(
                _row(
                    r["ts"][11:19],
                    r.get("task"),
                    r.get("patient_id"),
                    subs,
                    _j(r.get("tool_counts") or {}, 120),
                    r.get("ai_turns"),
                    f"{r.get('duration_s')} s",
                    f"`{r.get('run_id')}`",
                )
            )
    if data["subagent_tool_calls"]:
        out += ["", _row("時間", "subagent → 工具", "參數", "輸出摘要"), "|---|---|---|---|"]
        for x in data["subagent_tool_calls"][: max_rows * 2]:
            outp = x.get("output") or x.get("error") or ""
            out.append(
                _row(
                    x["ts"][11:19],
                    f"{x.get('subagent')} → `{x.get('tool')}`",
                    _j(x.get("args") or {}, 90),
                    _j(outp, 160),
                )
            )
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("thread_id")
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--max", type=int, default=12)
    a = ap.parse_args()
    url = f"{a.api}/debug/trace/{urllib.parse.quote(a.thread_id, safe='')}"
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.load(r)
    print(render(data, a.max))


if __name__ == "__main__":
    main()
