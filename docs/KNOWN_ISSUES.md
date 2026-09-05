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
| 18 | ~~對話 session 不會自動過期~~ **已修（2026-09-05）**：`open_session` 在 session 超過 `SESSION_EXPIRY_H`（預設 4）小時或跨台灣日期時自動關閉（`closed_reason=expired`），對話串加一行系統事件「上一段對話已自動結束（超過 4 小時／跨日）」，並開新的一段。 | 同一天 4 小時內連續測試仍共用同一段。 | 說「不對」重新開始；或 `make reset`。`tests/test_session_expiry.py`。 |
| 19 | ~~角色首頁 N+1~~ **已修（2026-09-05）**：`GET /home/{role}` 一次回全部住民＋該角色卡片需要的資料（照護者：今天記了沒／注意事項數／session；護理師：異常趨勢句＋前兩個異常維度的曲線；醫師：RoundPage 首句／狀態）。三個角色首頁各只打一次（護理站另有 `/nurse/inbox` 輪詢）。 | 十位以上住民首屏仍要算 N 次趨勢，但在同一個請求裡。 | `tests/test_home.py`。 |
| 20 | ~~輪詢在分頁隱藏時不暫停~~ **已修（2026-09-05）**：`lib/api.ts::usePolling(reload, ms, enabled)` 統一四處輪詢（護理站 inbox、全站紅燈橫幅、trace 頁、Path A 審核面板）：`document.hidden` 時停，回前景先 reload 一次再繼續。 | 同一分頁仍是 5 秒輪詢，未改 SSE。 | `lib/polling.test.tsx`。 |
| 21 | ~~10 秒確認「改一句／退回」鎖鍵~~ **已修（2026-09-05，OMNI-TWIN 第 5 步）**：三鍵永遠可按，改一句／退回就地展開輸入，確認鍵依是否有改寫送 accept／edit。 | — | `components/nurse/ten-second-confirm.tsx` |
| 22 | SSE 串流（對話、巡診）在客戶端中途斷線時不會取消後端的 graph：worker thread 會跑完（結果照樣寫進 checkpoint／registry），只是沒人收事件。 | 重新整理頁面後從 registry／conversation 讀到結果。 | 需要取消時可在 `core/trace.run_in_thread` 加 cancel flag。 |
| 23 | gpt-4.1 偶爾把文字放進數字欄（`vitals_reported.rr = "呼吸很快"`），以前會讓整句抽取失敗（503）。現在 `_Extraction` 只留數字、其餘丟掉，文字仍在 vitals 維度的 raw_quote。 | eval 第一次跑到這句時中斷，修後重跑。 | — |
| 24 | 成本是估算：價格寫死在 settings（gpt-5.6-luna 2026-07-30 降價後牌價：input 0.20、cached 0.02、cache write 0.25、output 1.20 USD/1M），依 usage 的 prompt／cached／cache_write／completion tokens 計算；未含 Batch 折扣或帳號協議價。 | ACCEPTANCE 的「每次呼叫成本」以此為準。 | 價格改了改 .env 的 PRICE_*。 |
| 25 | 快取命中不保證：第一次呼叫（或路由到沒有快取的機器）會是 cache write；一天內 timeline 有新寫入（護理師確認）時紀錄區塊改變、下一次呼叫重新寫入。 | 偶爾一輪成本較高。 | — |
| 26 | ~~luna 逐字重問／連續兩次選已知維度 → 503~~ **已修（2026-09-05 下午）**：`intake_dialog.known_gaps` 算出每個已知維度的缺口（value／direction 未填、原話裡有該維度關鍵字但不在 raw_quote），交給模型「已知但仍有缺口（可追問一次）」；planner 選已知維度時 `gap`／`reason` 必須指出其中一個缺口、同一維度只放行一次；第二次仍無效 → ask=false 出摘要卡（trace `intake.plan_gave_up`），不再 503。503 只留給 LLM 真的失敗，照護者端顯示「系統暫時無法回覆，請直接告訴護理師」。順手修 `_apply_answer` 把追問回答整句覆寫成已知維度 raw_quote 的舊 bug。 | 真模型實測：「早餐沒吃完，說肚子脹」第一題就補問脹的程度；第二輪想再問進食被擋後改問疼痛。 | `tests/test_planner_gaps.py` ×7。 |
| 27 | 抽取快取以「句子＋住民＋模型＋effort＋當日」為 key（`records/{id}/extract_cache.json`）：同一天同住民說同一句不會重抽；基線在當天內被護理師更新時，舊快取仍沿用。 | 只影響當天。 | 改 `ingest/intake_dialog.py::_extract_cache_key` 加入 baseline 版本即可。 |
| 28 | 身份是 demo 靜態表：web 的 `lib/role.ts::IDENTITIES` 與 seed 的 `records/_identities.json` 要手動保持一致；cookie 只存 `me`，沒有登入。 | 新增身份要改兩處。 | 第二階段接真正的身份提供者。 |
| 29 | 「問我的紀錄」檢索是關鍵字 bigram（去停用詞），不是向量檢索；同義詞（例：「心臟開刀」vs「心臟手術」）可能找不到而回「紀錄裡沒有這件事」。 | 回答保守（寧可說沒有），不會捏造。 | 第二階段換 embedding；答案仍須引用既有行。 |
| 30 | 感測事件的硬條件門檻寫死在 `red_flags/rules.py`（靜止 60 秒、SpO₂ 92）；`/sim/fall` 為模擬，沒有真實穿戴裝置。 | Demo 用 `{"still_seconds":90}` 觸發硬條件。 | **硬條件維持不變**（它們回答的是「對任何人危不危險」）；2026-09-05 另加 RF13：從 timeline 已量測的 vitals 算出每位住民自己的正常帶，偏離自己的範圍時 `observe`。裝置本身仍是第二階段。 |
| 37 | 生理值正常帶只涵蓋 `Vitals` 六個欄位（體溫、收縮壓、舒張壓、心率、呼吸、血氧），八維度中的其他七個（進食、排泄、活動、認知、睡眠、皮膚、疼痛）沒有數值序列可算，仍只有護理師寫的 `BaselineEntry` 文字描述。 | RF13 只對 vitals 生效。 | 需要那七個維度也有可比較的量，才談得上算帶；目前 `DimensionValue.value` 多半是文字。 |
| 38 | ~~Windows 上 `uv run pytest` 有 25 個 UnicodeDecodeError~~ **已修（2026-09-05）**：`record/store.py` 的 `read_text()` 沒指定編碼，Windows 預設 cp950 而檔案是 UTF-8。 | 只影響非 UTF-8 預設編碼的平台（macOS/Linux 不受影響）。 | 補 `encoding="utf-8"`；133 個測試在 Windows 上全過。 |
| 31 | `make seed` 會清掉 records（含 conversation、sensor_events、care_circle 的變更），但 DB 的舊 thread 仍在 → 紅燈橫幅可能疊卡（#17）。 | 錄影前 `make reset`。 | — |
| 32 | omni-twin-3.v0.build 需登入才看得到預覽與 chat（Preview setup failed／read-only），本輪未能讀取其 UI 想法。 | 尚未併入。 | 使用者匯出截圖或原始碼後再對齊。 |
| 33 | 列印白底驗證用的是醫師 docs tab（事件資訊包）；RoundPage 需先跑巡診流程（約 2.5 分鐘）才會出現，本輪 `make seed` 後沒有已發布的 RoundPage。RoundPage 卡片本身以 `data-theme="white"` 呈現，列印時整頁切白色 tokens。 | 截圖 `print-1280-white.png` 是事件資訊包。 | 錄影前跑 `/nurse/round` 發布後再印。 |
| 34 | 頂欄的地點·天氣是示意假資料（規格 §3.1 允許）；「孿生同步中」燈只代表頁面在輪詢，不代表裝置連線。 | 觀感。 | 第二階段接真資料。 |
| 35 | 登入是 demo 等級：`POST /login` 驗證病人密碼（hash）並把身份加進 Care Circle，但 cookie `me` 仍由 `/role?set=` 寫入，直接打該網址可跳過密碼（Care Circle 仍擋住未授權的 tab）。示範密碼＝出生年。 | 只影響 demo 安全性。 | 第二階段：session token 由 API 簽發、`/role` 只接受 token。 |
| 36 | 01 的解剖 SVG 約 900 KB（一次載入、瀏覽器快取）；器官對維度的對應是示意（如「皮膚」熱點固定在上臂、「疼痛」浮動在髖部），不是臨床定位。 | 首次載入多約 0.3 秒。 | 第二階段可換 3D 模型或依疼痛部位移動熱點。 |
| 39 | `make test` 只跑 `ruff check`，不跑 `ruff format --check`；但 CI（ci.yml L33）兩個都跑。本機 `make test` 過不代表 CI 會綠。 | commit `c0a6802` 推上 main 時 CI 應為紅（5 個檔案格式不符），已於同日修正。 | 本機改用 `.\scripts\dev.ps1 check`（lint 含 format + pytest + codegen 一致性），與 CI 同一組檢查。 |
| 37 | 3D 分身模型 9.2 MB 進 git（`apps/web/public/models/my_avatar.glb`），首次載入約 1–3 秒；沒有 Idle 動畫（模型不含 animations），姿態切換無效果；ARKit blendshape 名稱以模型實際為準，缺的表情會被略過。 | 分身頁首屏較慢。 | 第二階段：Draco 壓縮、加動畫。 |
| 38 | 「唸給我聽」用瀏覽器 speechSynthesis，中文語音依作業系統而定；無語音時按鈕無反應。 | 只影響本人區。 | — |
