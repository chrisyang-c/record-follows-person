# HANDOFF — 交接（2026-09-05）

Repo：https://github.com/chrisyang-c/record-follows-person ・ 2026-09-05 起直接 commit 到 `main` 並 push（不開分支／PR，見 CLAUDE.md §0.1）。
先讀：CLAUDE.md → docs/ARCHITECTURE.md → docs/ACCEPTANCE.md（驗收與指令）→ docs/DECISIONS.md（為什麼）→ docs/KNOWN_ISSUES.md。

## 已完成（最近一輪，2026-09-05）

| 項目 | 在哪裡 | 證據 |
|---|---|---|
| 模型切換 `MODEL_PINNED=gpt-5.6-luna`：`settings.get_model()` → `ChatOpenAI(model, temperature=0, reasoning_effort="none")`；intake、personal agent、三個 subagent 都經它 | `apps/api/core/settings.py` | `tests/test_model_and_usage.py`；ACCEPTANCE「模型換成 gpt-5.6-luna」 |
| Prompt caching 訊息結構：一則 system（任務指令 + `record_prefix`：profile／基線／近 14 天 timeline，一天內不變）+ 一則 human（本輪）。實測此模型只快取 system 內前綴 | `apps/api/core/llm.py`（`_system_with_record`、`record_prefix`） | 對話第 2 輪起 extract 94%、next_question 82% 命中 |
| 每次模型呼叫寫 `llm.usage`（tokens、cached、cache_write、估算 USD）；eval 報告加成本表 | `apps/api/core/usage.py`、`eval/run.py` | `apps/api/eval/results.md`；`GET /debug/trace/{thread_id}` |
| 重複題修正：planner 驗證模型決定（重複問題／已知維度 → 帶原因重問一次，第二次無效 → 503），接受維度中文名；答案配對「純問題」而非含紅燈 intro 的回覆 | `apps/api/ingest/intake_dialog.py::_plan`、`graphs/talk.py`、`record/conversation.py` | `tests/test_talk_graph.py`、`test_intake_dialog.py` |
| writer 子代理先 `get_round_context` 再 `analyze_trends`（timeline 讀取固定在最前面） | `apps/api/agents/personal.py` | 巡診 thread `ALL:round:2026-09-04:8`，30 次呼叫 $0.012 |
| Eval 重跑（luna）：hallucination 8.7%、omission 4.3%、provenance 100% | `apps/api/eval/results.md` | ACCEPTANCE 表（對照 gpt-4.1：4.3% / 2.2%） |
| PR #9 病人頁 IA／talk 串流／活動列、#10 docs、#11 本輪 | GitHub | CI api + web 綠 |

## 待做（依序）

1. ~~extract 與 next_question 改 `reasoning_effort="low"` 重跑 eval~~ **已做（2026-09-05）**：`INTAKE_REASONING_EFFORT`（預設 low → Responses API）、ACCEPTANCE Eval 表三欄、KNOWN_ISSUES #26。結論：low 在這兩個 prompt 上 reasoning tokens 為 0，成本不變，hallucination 8.7%→6.5%（gpt-4.1 仍 4.3%）。**定案**：luna + intake low（README 評測段三欄表）。
2. ~~對話 session 過期（KNOWN_ISSUES #18）~~ **已做（2026-09-05）**：`SESSION_EXPIRY_H`＝4 小時或跨台灣日期自動關閉；順手把抽取快取持久化到 `records/{id}/extract_cache.json`（每輪只抽新的一句）。
3. 角色首頁批次 summary 端點（#19）、輪詢在分頁隱藏時暫停或改 SSE（#20）。
4. 10 秒確認「改一句／退回」改成不鎖鍵、就地提示（#21）。
5. SSE 客戶端斷線取消後端 graph（#22，`core/trace.run_in_thread` 加 cancel flag）。
6. 若全隊同意改 CLAUDE.md §1：對話每輪直接寫 timeline（#15，改 `record/conversation.py::append` 一處）。
7. 影片：`make reset` 後照 docs/VIDEO.md 錄；紅燈用李阿公第二個例子。

## 已知問題

全表在 docs/KNOWN_ISSUES.md（#1–#26）。最影響 demo 的：
- #17 測試留下的紅燈 thread 會疊卡 → 錄影前 `make reset`。
- #18 已修（4 小時／跨日自動過期）；同一天 4 小時內連續測試仍共用一段 → 說「不對」重來或 `make reset`。
- **#26 仍會 503**：luna low 偶爾連續兩次選已知維度（約每 6 輪 1 次），畫面顯示「無法繼續」，重送同一句就過；要不要放寬規則待決定。
- #24／#25 成本是牌價估算、快取第一次必寫入；#26 見上。
- #14 TPM 限流：deep agent 一次一位（`_DEEP_AGENT_LOCK`），三人巡診約 2.5 分鐘。
- 測試偶發：`test_red_flag_starts_path_a_and_keeps_talking` 在 PR #11 CI 失敗一次（答案配對到含 intro 的回覆），已修（a29c551）。

## 目前 .env 變數（值不進 repo；範本見 .env.example）

| 變數 | 目前 | 用途 |
|---|---|---|
| `MODEL_PROVIDER` | openai | 模型工廠分支（openai／anthropic／mock，mock 只給 pytest） |
| `MODEL_PINNED` | gpt-5.6-luna | 釘住的模型；gpt-5.x 自動加 `reasoning_effort="none"` |
| `INTAKE_REASONING_EFFORT` | low（定案） | intake 兩個呼叫的 reasoning_effort；非 `none` 時改走 Responses API；`none` 回到與其他呼叫相同 |
| `OPENAI_API_KEY` | 已填 | 唯一在用的 key |
| `ANTHROPIC_API_KEY` | 有欄位、未使用 | 只在 `MODEL_PROVIDER=anthropic` 時用 |
| `DATABASE_URL` | 本機 brew postgres（record_follows_person） | PostgresSaver + thread registry |
| `LINE_CHANNEL_TOKEN`、`LINE_FAMILY_TO` | 空 | 空 → 家屬通知只顯示不發（`displayed_only`） |
| `RECORDS_ROOT` | records/ | PersonRecord 目錄 |
| `NURSE_REVIEW_TIMEOUT_S`、`WORKER_SCAN_INTERVAL_S` | 預設 | 超時升級 worker |
| `SESSION_EXPIRY_H` | 未設（預設 4） | 對話 session 自動過期（#18 已修） |
| `NEXT_PUBLIC_API_URL` | http://localhost:8000 | 前端打 API |
| `PRICE_INPUT_PER_M` 等四個 | 未設（用 settings 預設 0.20／0.02／0.25／1.20） | 只影響成本估算 |

## 環境備忘

沒有 Docker（`make db-local`／`make reset` 用 Homebrew postgresql@17）；編輯 `apps/api/*.py` 時若有 SSE 連線在跑，`fastapi dev` 會卡在 reload，先斷客戶端再重啟；LangGraph `max_concurrency` 不能和 `stream_mode="custom"` 併用（死鎖，已改 lock）。
