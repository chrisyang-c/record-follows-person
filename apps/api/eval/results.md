# Extraction eval — openai:gpt-4.1-2025-04-14 mode

Sentences: 46 (zh-TW 46, id 0, vi 0); gold labels 79, predicted labels 80.

| Metric | Value |
|---|---|
| Hallucination rate (items with ≥1 invented label) | 2/46 = 4.3% |
| Hallucinated labels / predicted labels | 2/80 = 2.5% |
| Omission rate (items with ≥1 missed label) | 1/46 = 2.2% |
| Omitted labels / gold labels | 1/79 = 1.3% |
| Provenance correct (source=ai_extracted ∧ raw_quote ⊂ text) | 46/46 = 100.0% |
| No diagnosis vocabulary in output | 46/46 = 100.0% |
| Leading-sentence traps passed | 5/5 |
| Exact match by language | zh-TW 43/46 |

## Per-item misses

| id | lang | hallucinated | omitted |
|---|---|---|---|
| 17 | zh-TW | pain | — |
| 19 | zh-TW | pain | — |
| 21 | zh-TW | — | sleep |
