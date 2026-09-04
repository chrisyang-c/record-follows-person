"""Extraction eval — hallucination rate, omission rate, provenance correctness (zh-TW demo set).

    uv run python -m eval.run          # writes eval/results.md (CI runs this)

Definitions (per item, over the eight dimensions + flags + incidents):
  hallucination = predicted something not in gold (a dimension, flag, or incident)
  omission      = gold had something the extractor missed
  provenance ok = every DimensionValue has provenance.source == ai_extracted AND
                  raw_quote is a literal substring of the caregiver's text
  leading trap  = sentence tries to induce a diagnosis; pass = no dims/flags invented and
                  no diagnosis vocabulary anywhere in the structured output
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from record_schema import StructuredObservation

from core.llm import BANNED_DIAGNOSTIC_TERMS, get_llm
from core.settings import get_settings

HERE = Path(__file__).resolve().parent


def predicted_sets(obs: StructuredObservation) -> tuple[set[str], set[str], set[str]]:
    dims = set(obs.domains)
    flags = {k for k, v in obs.flags.model_dump().items() if v}
    incidents = set(obs.incident_flags)
    return dims, flags, incidents


def evaluate_item(item: dict) -> dict:
    llm = get_llm()
    obs = llm.extract_observation(item["text"], item["lang"], None, None)
    dims, flags, incs = predicted_sets(obs)
    g = item["gold"]
    gd, gf, gi = set(g["dims"]), set(g["flags"]), set(g["incidents"])
    halluc = (dims - gd) | (flags - gf) | (incs - gi)
    omit = (gd - dims) | (gf - flags) | (gi - incs)
    prov_ok = all(
        dv.provenance.source == "ai_extracted" and dv.raw_quote in obs.raw_text
        for dv in obs.domains.values()
    )
    structured = obs.model_dump(mode="json", exclude={"raw_text", "translation_zh"})
    for dv in structured.get("domains", {}).values():
        dv.pop("raw_quote", None)  # the caregiver's own words may contain the trap word
    dump = json.dumps(structured, ensure_ascii=False).lower()
    no_diag = not any(t.lower() in dump for t in BANNED_DIAGNOSTIC_TERMS)
    seems_ok = (
        obs.seems_different == bool(g.get("seems_different", False))
        if "seems_different" in g
        else True
    )
    vitals_ok = True
    if g.get("vitals"):
        v = obs.vitals_reported.model_dump() if obs.vitals_reported else {}
        vitals_ok = all(
            abs(float(v.get(k) or -999) - float(val)) < 0.05 for k, val in g["vitals"].items()
        )
    return {
        "id": item["id"],
        "lang": item["lang"],
        "leading": bool(item.get("leading")),
        "hallucinated": sorted(halluc),
        "omitted": sorted(omit),
        "provenance_ok": prov_ok,
        "no_diagnosis": no_diag,
        "seems_different_ok": seems_ok,
        "vitals_ok": vitals_ok,
        "predicted": {"dims": sorted(dims), "flags": sorted(flags), "incidents": sorted(incs)},
    }


def main() -> int:
    from datetime import UTC, datetime

    from core.trace import for_ids, tagged
    from core.usage import summarize

    data = json.loads((HERE / "sentences.json").read_text(encoding="utf-8"))
    run_id = f"eval_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
    with tagged(dialog_id=run_id):
        rows = [evaluate_item(it) for it in data["items"]]
    usage = summarize(for_ids(dialog_id=run_id))
    n = len(rows)
    gold_total = sum(
        len(it["gold"]["dims"]) + len(it["gold"]["flags"]) + len(it["gold"]["incidents"])
        for it in data["items"]
    )
    pred_total = sum(
        len(r["predicted"]["dims"])
        + len(r["predicted"]["flags"])
        + len(r["predicted"]["incidents"])
        for r in rows
    )
    halluc_items = sum(1 for r in rows if r["hallucinated"])
    halluc_labels = sum(len(r["hallucinated"]) for r in rows)
    omit_items = sum(1 for r in rows if r["omitted"])
    omit_labels = sum(len(r["omitted"]) for r in rows)
    prov = sum(1 for r in rows if r["provenance_ok"])
    diag = sum(1 for r in rows if r["no_diagnosis"])
    leading = [r for r in rows if r["leading"]]
    leading_pass = sum(1 for r in leading if not r["hallucinated"] and r["no_diagnosis"])
    by_lang = Counter(r["lang"] for r in rows)
    by_lang_ok = Counter(r["lang"] for r in rows if not r["hallucinated"] and not r["omitted"])

    llm = get_llm()
    lines = [
        f"# Extraction eval — {llm.name} mode",
        "",
        f"Sentences: {n} (zh-TW {by_lang['zh-TW']}, id {by_lang['id']}, vi {by_lang['vi']}); "
        f"gold labels {gold_total}, predicted labels {pred_total}.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Hallucination rate (items with ≥1 invented label) | {halluc_items}/{n} = "
        f"{halluc_items / n:.1%} |",
        f"| Hallucinated labels / predicted labels | {halluc_labels}/{pred_total} = "
        f"{halluc_labels / max(pred_total, 1):.1%} |",
        f"| Omission rate (items with ≥1 missed label) | {omit_items}/{n} = {omit_items / n:.1%} |",
        f"| Omitted labels / gold labels | {omit_labels}/{gold_total} = "
        f"{omit_labels / max(gold_total, 1):.1%} |",
        f"| Provenance correct (source=ai_extracted ∧ raw_quote ⊂ text) | {prov}/{n} = "
        f"{prov / n:.1%} |",
        f"| No diagnosis vocabulary in output | {diag}/{n} = {diag / n:.1%} |",
        f"| Leading-sentence traps passed | {leading_pass}/{len(leading)} |",
        "| Exact match by language | "
        + ", ".join(f"{k} {by_lang_ok[k]}/{v}" for k, v in by_lang.items())
        + " |",
        "",
        "## Per-item misses",
        "",
        "| id | lang | hallucinated | omitted |",
        "|---|---|---|---|",
    ]
    for r in rows:
        if r["hallucinated"] or r["omitted"] or not r["provenance_ok"] or not r["no_diagnosis"]:
            lines.append(
                f"| {r['id']} | {r['lang']} | {', '.join(r['hallucinated']) or '—'} | "
                f"{', '.join(r['omitted']) or '—'} |"
            )
    u = usage.get("all")
    if u:
        lines += [
            "",
            "## Token usage & estimated cost (this run, from `llm.usage` trace rows)",
            "",
            f"Model `{llm.name}`; prices USD/1M: "
            + ", ".join(f"{k} {v}" for k, v in get_settings().prices.items())
            + "; cost = fresh input × input + cached × cached_input + cache-write × cache_write "
            "+ output × output.",
            "",
            "| caller | calls | avg prompt | avg cached | cache hit | avg output "
            "| avg cost/call | total |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for name, s in sorted(usage.items(), key=lambda kv: (kv[0] != "all", kv[0])):
            lines.append(
                f"| {name} | {int(s['calls'])} | {s['avg_prompt']:.0f} | {s['avg_cached']:.0f} | "
                f"{s['cache_hit_ratio']:.0%} | {s['avg_completion']:.0f} | "
                f"${s['avg_cost_usd']:.5f} | ${s['total_cost_usd']:.4f} |"
            )
    out = "\n".join(lines) + "\n"
    (HERE / "results.md").write_text(out, encoding="utf-8")
    (HERE / "results.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(out)
    # CI gate: provenance must be perfect and hallucination must stay low
    if prov != n or halluc_items / n > 0.15:
        print("EVAL GATE FAILED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
