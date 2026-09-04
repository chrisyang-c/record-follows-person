# Extraction eval — mock mode

Sentences: 46 (zh-TW 24, id 12, vi 10); gold labels 79, predicted labels 80.

| Metric | Value |
|---|---|
| Hallucination rate (items with ≥1 invented label) | 2/46 = 4.3% |
| Hallucinated labels / predicted labels | 2/80 = 2.5% |
| Omission rate (items with ≥1 missed label) | 1/46 = 2.2% |
| Omitted labels / gold labels | 1/79 = 1.3% |
| Provenance correct (source=ai_extracted ∧ raw_quote ⊂ text) | 46/46 = 100.0% |
| No diagnosis vocabulary in output | 46/46 = 100.0% |
| Leading-sentence traps passed | 5/5 |
| Exact match by language | zh-TW 21/24, id 12/12, vi 10/10 |

## Per-item misses

| id | lang | hallucinated | omitted |
|---|---|---|---|
| 4 | zh-TW | — | cognition |
| 9 | zh-TW | intake | — |
| 10 | zh-TW | intake | — |
