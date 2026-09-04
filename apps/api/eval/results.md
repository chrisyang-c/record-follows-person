# Extraction eval — mock mode

Sentences: 46 (zh-TW 24, id 12, vi 10); gold labels 79, predicted labels 81.

| Metric | Value |
|---|---|
| Hallucination rate (items with ≥1 invented label) | 2/46 = 4.3% |
| Hallucinated labels / predicted labels | 2/81 = 2.5% |
| Omission rate (items with ≥1 missed label) | 0/46 = 0.0% |
| Omitted labels / gold labels | 0/79 = 0.0% |
| Provenance correct (source=ai_extracted ∧ raw_quote ⊂ text) | 46/46 = 100.0% |
| No diagnosis vocabulary in output | 46/46 = 100.0% |
| Leading-sentence traps passed | 5/5 |
| Exact match by language | zh-TW 22/24, id 12/12, vi 10/10 |

## Per-item misses

| id | lang | hallucinated | omitted |
|---|---|---|---|
| 9 | zh-TW | intake | — |
| 10 | zh-TW | intake | — |
