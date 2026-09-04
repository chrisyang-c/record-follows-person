# KNOWN_ISSUES

| # | 問題 | 影響 | 狀態／繞法 |
|---|---|---|---|
| 1 | 本機沒有 `OPENAI_API_KEY`（也沒有 `ANTHROPIC_API_KEY`）。`MODEL_PROVIDER=openai` 已設定，但 key 為空時 `settings.get_model()` 退回 mock 模型：抽取走確定性關鍵字（`ingest/lexicon.py`），ISBAR／家屬通知走模板。 | 語意抽取不如 LLM（eval 4.3% hallucination、0% omission 是 mock 的數字）；印尼／越南語翻譯只有摘要。 | 在 `.env` 填 `OPENAI_API_KEY` 即走 `ChatOpenAI(model=MODEL_PINNED, temperature=0)`（`core/llm.py::ChatModelLLM`：結構化輸出＋raw_quote 子字串守門）；mock 為失敗時的後備。 |
| 2 | 本機沒有 Docker；Postgres 用 Homebrew `postgresql@17`（`make db-local`）。 | `docker compose up -d postgres` 在這台機器不能用；其他機器可用。 | 兩條路都寫在 ACCEPTANCE.md。 |
| 3 | Homebrew `postgresql@17` 與已裝的 `libpq@17` 衝突，`/opt/homebrew/lib/postgresql@17`、`/opt/homebrew/share/postgresql@17` 需手動 symlink 到 Cellar。 | 只影響這台機器的第一次安裝。 | 已做；指令記在 ACCEPTANCE.md。 |
| 4 | `claude plugin add` 指令不存在；`anthropic/frontend-design` 位於官方 marketplace；`vercel-labs/agent-skills` 不是 plugin marketplace。 | §0.3 的三行指令不能照抄。 | 改用 `claude plugin marketplace add` + `claude plugin install`；web-design-guidelines 以檔案 vendor 進 `.claude/skills/`。 |
| 5 | 分支規則「至少一人 review」無法由單一 agent 滿足。 | PR 皆由同一帳號建立並合併。 | PR 內容照 §8 寫（節點／閘門、測試、UI 稽核），供事後審閱。 |
| 6 | 超時升級的 worker 只在 API 進程內（APScheduler）或 `make worker` 跑；deadline 存在 graph state 與 `threads` 表。 | 若 API 沒開，逾時不會升級。 | 影片以旁白帶過（ARCHITECTURE §8）。`/nurse` 有「立即掃描逾時」按鈕可手動觸發。 |
| 7 | Timeline Curator 只做結構（同日事件連結、疑似重複提示），不重寫既有 entry。 | 與設計一致（demo 資料先整理好）。 | — |
| 8 | 影像分析、119／特約通知、LINE 發送皆為顯示不真發（`displayed_only`）。 | Demo 範圍內。 | 設 `LINE_CHANNEL_TOKEN` + `LINE_FAMILY_TO` 即真發。 |
| 9 | Web Speech API 只在 Chrome／Edge 可用；Safari 部分支援。 | 照護者頁面在不支援的瀏覽器會提示改打字。 | — |
| 10 | 中文分句用標點；印尼／越南語用逗號與連接詞。一句話沒有標點時整句是同一個 clause，多個維度會共用同一段 raw_quote。 | provenance 仍正確（子字串），但 raw_quote 較長。 | LLM 模式會給更精確的片段。 |
