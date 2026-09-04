# Extraction eval — openai:gpt-5.6-luna mode

Sentences: 46 (zh-TW 46, id 0, vi 0); gold labels 79, predicted labels 81.

| Metric | Value |
|---|---|
| Hallucination rate (items with ≥1 invented label) | 4/46 = 8.7% |
| Hallucinated labels / predicted labels | 4/81 = 4.9% |
| Omission rate (items with ≥1 missed label) | 2/46 = 4.3% |
| Omitted labels / gold labels | 2/79 = 2.5% |
| Provenance correct (source=ai_extracted ∧ raw_quote ⊂ text) | 46/46 = 100.0% |
| No diagnosis vocabulary in output | 46/46 = 100.0% |
| Leading-sentence traps passed | 5/5 |
| Exact match by language | zh-TW 41/46 |

## Per-item misses

| id | lang | hallucinated | omitted |
|---|---|---|---|
| 11 | zh-TW | cognition | — |
| 17 | zh-TW | pain | — |
| 19 | zh-TW | pain | vitals |
| 33 | zh-TW | — | no_urine_24h |
| 42 | zh-TW | cognition | — |

## Token usage & estimated cost (this run, from `llm.usage` trace rows)

Model `openai:gpt-5.6-luna`; prices USD/1M: input 0.2, cached_input 0.02, cache_write 0.25, output 1.2; cost = fresh input × input + cached × cached_input + cache-write × cache_write + output × output.

| caller | calls | avg prompt | avg cached | cache hit | avg output | avg cost/call | total |
|---|---|---|---|---|---|---|---|
| all | 46 | 1448 | 1236 | 85% | 152 | $0.00025 | $0.0117 |
| llm.extract | 46 | 1448 | 1236 | 85% | 152 | $0.00025 | $0.0117 |
