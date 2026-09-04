# KNOWN_ISSUES

| # | 問題 | 影響 | 狀態／繞法 |
|---|---|---|---|
| 1 | 本機沒有 `OPENAI_API_KEY`（也沒有 `ANTHROPIC_API_KEY`）。`MODEL_PROVIDER=openai` 已設定，但 key 為空時 `settings.get_model()` 退回 mock 模型：抽取走確定性關鍵字（`ingest/lexicon.py`），ISBAR／家屬通知走模板。 | 語意抽取不如 LLM（eval 4.3% hallucination、0% omission 是 mock 的數字）。 | 在 `.env` 填 `OPENAI_API_KEY` 即走 `ChatOpenAI(model=MODEL_PINNED, temperature=0)`（`core/llm.py::ChatModelLLM`：結構化輸出＋raw_quote 子字串守門）；mock 為失敗時的後備。 |
| 2 | 本機沒有 Docker；Postgres 用 Homebrew `postgresql@17`（`make db-local`）。 | `docker compose up -d postgres` 在這台機器不能用；其他機器可用。 | 兩條路都寫在 ACCEPTANCE.md。 |
| 3 | Homebrew `postgresql@17` 與已裝的 `libpq@17` 衝突，`/opt/homebrew/lib/postgresql@17`、`/opt/homebrew/share/postgresql@17` 需手動 symlink 到 Cellar。 | 只影響這台機器的第一次安裝。 | 已做；指令記在 ACCEPTANCE.md。 |
| 4 | `claude plugin add` 指令不存在；`anthropic/frontend-design` 位於官方 marketplace；`vercel-labs/agent-skills` 不是 plugin marketplace。 | §0.3 的三行指令不能照抄。 | 改用 `claude plugin marketplace add` + `claude plugin install`；web-design-guidelines 以檔案 vendor 進 `.claude/skills/`。 |
| 5 | 分支規則「至少一人 review」無法由單一 agent 滿足。 | PR 皆由同一帳號建立並合併。 | PR 內容照 §8 寫（節點／閘門、測試、UI 稽核），供事後審閱。 |
| 6 | 超時升級的 worker 只在 API 進程內（APScheduler）或 `make worker` 跑；deadline 存在 graph state 與 `threads` 表。 | 若 API 沒開，逾時不會升級。 | 影片以旁白帶過（ARCHITECTURE §8）。`/nurse` 有「立即掃描逾時」按鈕可手動觸發。 |
| 7 | Timeline Curator 只做結構（同日事件連結、疑似重複提示），不重寫既有 entry。 | 與設計一致（demo 資料先整理好）。 | — |
| 8 | 影像分析、119／特約通知、LINE 發送皆為顯示不真發（`displayed_only`）。 | Demo 範圍內。 | 設 `LINE_CHANNEL_TOKEN` + `LINE_FAMILY_TO` 即真發。 |
| 9 | Web Speech API 只在 Chrome／Edge 可用；Safari 部分支援。 | 照護者頁面在不支援的瀏覽器會提示改打字。 | — |
| 10 | 中文分句用標點。一句話沒有標點時整句是同一個 clause，多個維度會共用同一段 raw_quote。 | provenance 仍正確（子字串），但 raw_quote 較長。 | LLM 模式會給更精確的片段。 |
| 12 | 真模型時每輪追問 1 次 `llm.next_question` ＋ 每句 1 次 `llm.extract`（已快取），約 2–5 秒／輪；巡診每位住民 2 次 deep agent 派工（familiarization_writer 會呼叫 analyze_trends ×2、get_round_context、submit_round_page，共約 6–10 次模型呼叫），三人約 2–4 分鐘。 | demo 節奏。 | 畫面有「傳送中…／產生中…」。 |
| 13 | deep agent 若未照指示派給 subagent 或 subagent 沒有 submit，節點丟 `AgentDidNotDeliver`，API 回 503，畫面顯示錯誤（不退回模板）。`MODEL_PROVIDER=mock` 只在 pytest／CI 用 scripted test double（trace 標 `scripted: true`）。 | 真模型偶爾需要重送（submit 驗證回 error 後模型會修正再送）。 | 巡診頁可重新「產生」。 |
| 14 | OpenAI 帳號的 gpt-4.1 TPM 上限 30k：三位住民的 deep agent 若平行跑會 429。已改成巡診一次跑一位（`agents/personal.py` 的 `_DEEP_AGENT_LOCK`；原本的 LangGraph `max_concurrency=1` 與 `stream_mode="custom"` 併用會死鎖，已移除）、工具回給模型的內容精簡（趨勢 series 不進模型上下文）、429 時依供應商建議秒數等待後重試（trace 有 `deep_agent.rate_limited`）。 | 巡診三人約 1–2 分鐘。 | 需要更快可提高帳號額度。 |
| 11 | Demo 只有 zh-TW。`lexicon.py` 仍含印尼／越南語關鍵字、`translate_instruction` 仍在，但介面沒有語言切換、seed 與 eval 全為中文。 | 多語為第二階段。 | schema 的 `lang` / `language_original` 保留，預設 zh-TW。 |
| 15 | 對話每一輪只寫進 `conversation.jsonl`＋provenance，不直接寫 timeline（CLAUDE.md §1.2／§4／§11 的核准閘門）。需求原文要「同時寫進 timeline」，見 DECISIONS 2026-09-05。 | 「紀錄」tab 會把兩者合併顯示，護理師確認後才有正式 Observation。 | 若全隊決定放寬 §1，改 `record/conversation.py::append` 一處即可。 |
| 16 | 串流回覆是「先算完再逐字吐」：talk graph 節點跑完後 API 以 3 字／20ms 送 token，不是模型 token 級串流（追問是 structured output，無法邊生成邊顯示）；活動事件則是即時的。 | 使用者看到活動列在動、再看到字打出來。 | 若要真 token 串流，需把追問改成非結構化輸出再解析。 |
| 17 | 同一位住民的紅燈 Path A thread 若重複啟動（測試時常見），護理站會出現多張卡；全站紅燈橫幅只顯示每位住民最新一件並註明「另 N 件」。`make reset` 清空。 | 錄影前先 `make reset`。 | — |
| 18 | 對話 session 不會自動過期：照護者上次沒說「對」就離開，下次進來仍在同一段 intake（追問預算共用）。 | 多次測試後會很快出摘要。 | 說「不對」重新開始；或 `make reset`。 |
| 19 | 角色首頁每位住民各打一次 `/patients/{id}/summary`（照護者）／`/trends/{id}`（護理師、醫師）：N+1。 | 三位住民可接受；十位以上首屏會慢。 | 加一個批次 summary 端點。 |
| 20 | 護理師的病人頁同時有三個 5 秒輪詢（全站紅燈橫幅、護理站、Path A 審核面板），分頁隱藏時不暫停。 | 多開分頁時 API 負載。 | `visibilitychange` 暫停；或改 SSE。 |
| 21 | 10 秒確認的「改一句／退回」在文字為空時按鈕 disabled，沒有就地提示（review-panel 的確認鍵是「不鎖、就地列缺什麼」）。 | 一致性。 | 改成同一種作法。 |
| 22 | SSE 串流（對話、巡診）在客戶端中途斷線時不會取消後端的 graph：worker thread 會跑完（結果照樣寫進 checkpoint／registry），只是沒人收事件。 | 重新整理頁面後從 registry／conversation 讀到結果。 | 需要取消時可在 `core/trace.run_in_thread` 加 cancel flag。 |
| 23 | gpt-4.1 偶爾把文字放進數字欄（`vitals_reported.rr = "呼吸很快"`），以前會讓整句抽取失敗（503）。現在 `_Extraction` 只留數字、其餘丟掉，文字仍在 vitals 維度的 raw_quote。 | eval 第一次跑到這句時中斷，修後重跑。 | — |
