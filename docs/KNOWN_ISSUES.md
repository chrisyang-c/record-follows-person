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
| 14 | OpenAI 帳號的 gpt-4.1 TPM 上限 30k：三位住民的 deep agent 若平行跑會 429。已改成巡診一次跑一位（`max_concurrency: 1`）、工具回給模型的內容精簡（趨勢 series 不進模型上下文）、429 時依供應商建議秒數等待後重試（trace 有 `deep_agent.rate_limited`）。 | 巡診三人約 1–2 分鐘。 | 需要更快可提高帳號額度。 |
| 11 | Demo 只有 zh-TW。`lexicon.py` 仍含印尼／越南語關鍵字、`translate_instruction` 仍在，但介面沒有語言切換、seed 與 eval 全為中文。 | 多語為第二階段。 | schema 的 `lang` / `language_original` 保留，預設 zh-TW。 |
