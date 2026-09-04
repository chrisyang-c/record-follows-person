# DECISIONS — 決策紀錄

格式：日期｜決定｜理由｜誰。改變核心原則（CLAUDE.md §1）需全隊同意。

## 已讀紀錄（§0.2）
- 已讀，2026-09-04，Claude（agent，代 chrisyang-c 執行）：CLAUDE.md、docs/ARCHITECTURE.md、docs/langgraph_path_a_incident.mermaid、docs/langgraph_path_b_routine_round.mermaid、docs/一份能跟著人走的紀錄_摘要與願景.md

## 我對這份設計的理解（2026-09-04，Claude）
1. **主體是 PersonRecord，不是流程。** 每位住民一個目錄 `records/{patient_id}/`，內含 profile / baseline / timeline / documents / provenance。所有 agent 都無狀態，只做「寫進紀錄」或「把紀錄講給某人聽」。
2. **兩張 mermaid 圖是節點名的唯一來源。** Path A（急症）14 個節點 + 3 個 interrupt（nurse_review、nurse_route_choice、nurse_approve_notification）；Path B 分 SHIFT（每班）與 ROUND（巡診）兩個子圖，各 1–2 個 interrupt（nurse_10s_confirm；head_nurse_edit_list、nurse_confirm_baseline）。graph 函式名 = mermaid 節點名。
3. **三道閘門是硬規則，用程式守，不靠 prompt。** (a) `timeline_write` 只收 `status="approved"` 且有 `confirmed_by`；(b) `red_flags/rules.py` 純程式、無 LLM；(c) baseline 只在 `nurse_confirm_baseline` 通過後由 `baseline_write` 寫入。
4. **AI 與人的產物在資料層就分開。** ISBAR 的 A/R 分成 `ai_change_vs_baseline` / `ai_questions_for_nurse`（AI 可寫）與 `nurse_assessment` / `nurse_recommendation`（只有護理師寫）。AI 欄位在 UI 用虛線＋淡藍；人確認用實線＋綠勾。
5. **provenance 是每行的屬性，不是文件的屬性。** 每個 DimensionValue、每筆 timeline entry、每份 document 的每一段都帶 `source/author/confirmed_by/ts/language_original`，只增不改。
6. **Demo 範圍依 ARCHITECTURE §8：** 真做 Intake、Comparator、紅燈、ISBAR 預填＋確認、Incident Compiler、Familiarization Writer、Order Ingest；假做影像分析、Timeline Curator（seed 已整理）、119／特約通知（畫面提示）、超時升級（程式有做，影片旁白帶過）、家屬通知（顯示不真發）、baseline 更新（顯示提案）。
7. **八維度是所有通道的共同座標。** 任何來源進來都要落到 `intake / elimination / function / cognition / sleep / skin / pain / vitals` 八格，另有 `seems_different` 旗標與 4 個事件快捷（fall / medication_issue / choking / behavior）。

## 環境與實作決定
| 日期 | 決定 | 理由 | 誰 |
|---|---|---|---|
| 2026-09-04 | LLM 呼叫全部集中在 `apps/api/llm.py`；`LLM_MODE=mock` 時走確定性規則抽取（關鍵字→八維度），`LLM_MODE=anthropic` 時走 Claude。本機沒有 `ANTHROPIC_API_KEY`，預設 mock。 | 這台機器環境中沒有 API key；紅燈、閘門、圖流程、UI、eval 都不依賴 LLM，先把可驗收的部分做完。真 LLM 路徑只差填 key。 | Claude |
| 2026-09-04 | Postgres 用 Homebrew `postgresql@17` 本機跑（`make db-local`），同時保留 `docker-compose.yml` 給有 Docker 的人。 | 這台機器沒有 Docker；Docker Desktop 需要 GUI 與管理員權限，無法非互動安裝。 | Claude |
| 2026-09-04 | checkpointer：有 `DATABASE_URL` 且連得上就用 `PostgresSaver`；pytest 圖測用 `InMemorySaver`（同一組 graph 程式碼）。 | 圖測要在 CI 沒 Postgres 時也能跑；生產／demo 路徑仍是 PostgresSaver。 | Claude |
| 2026-09-04 | 超時升級：interrupt 前把 `deadline` 寫進 state；APScheduler worker 每 30 秒掃逾期 thread，注入 `Command(resume={"action":"escalate"})`。圖測用縮短的 deadline 直接驗證。 | 依 CLAUDE.md §4。 | Claude |
| 2026-09-04 | `claude plugin add` 指令不存在；改用 `claude plugin marketplace add` + `claude plugin install`。`anthropic/frontend-design` 實際位於官方 marketplace（`frontend-design@claude-plugins-official`）；`vercel-labs/agent-skills` 不是 plugin marketplace，改 clone 後把 `skills/web-design-guidelines` 放進 `.claude/skills/`。 | 照 §0.3 精神安裝，指令依現況修正。 | Claude |
| 2026-09-04 | `design.md` 由 ui-ux-pro-max 的架構產出後，tokens 段落整段以 CLAUDE.md §7 覆寫；禁止 glassmorphism / neumorphism / 漸層。 | §0.3、§11。 | Claude |
| 2026-09-04 | Python 3.12 由 uv 管理；`deepagents / langgraph / langchain` 鎖精確版本於 `apps/api/pyproject.toml`。 | §5、§8。 | Claude |
| 2026-09-04 | 照護者「看一眼是不是這個意思」：紅燈不做、其他做（ARCHITECTURE §11 建議）。實作為 `caregiver_section_writer` 輸出後在照護者端顯示「是這個意思嗎」確認卡，不擋流程。 | 採納設計稿建議。 | Claude |
| 2026-09-04 | RoundPage 趨勢圖：放一張，八維度中變化最大的兩個（ARCHITECTURE §11 建議）。 | 一頁上限。 | Claude |
| 2026-09-04 | Path A 追蹤只問一次，時間由護理師在 `schedule_follow_up` 設定（預設 4 小時）。 | ARCHITECTURE §11。 | Claude |
