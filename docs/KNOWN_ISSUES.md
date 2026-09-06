# KNOWN_ISSUES

| # | 問題 | 影響 | 狀態／繞法 |
|---|---|---|---|
| 1 | 沒有模型 key 或使用 `MODEL_PROVIDER=mock` 時部分流程用確定性抽取；需要真模型的對話另有停止／錯誤邊界。 | mock 通過不證明真模型品質。 | 不記錄本機是否有 key；`check` 固定 mock，歷史真模型評測與本輪回歸分開報告。 |
| 2 | 早期 macOS 環境未裝 Docker，使用 Homebrew PostgreSQL；不是 repo 的共同限制。 | 啟動方式依機器而異。 | 2026-09-06 Windows 已以 Docker PostgreSQL 17 完成隔離 runtime 驗證，見 VALIDATION。 |
| 3 | Homebrew `postgresql@17` 與已裝的 `libpq@17` 衝突，`/opt/homebrew/lib/postgresql@17`、`/opt/homebrew/share/postgresql@17` 需手動 symlink 到 Cellar。 | 只影響這台機器的第一次安裝。 | 已做；指令記在 ACCEPTANCE.md。 |
| 4 | `claude plugin add` 指令不存在；`anthropic/frontend-design` 位於官方 marketplace；`vercel-labs/agent-skills` 不是 plugin marketplace。 | §0.3 的三行指令不能照抄。 | 改用 `claude plugin marketplace add` + `claude plugin install`；web-design-guidelines 以檔案 vendor 進 `.claude/skills/`。 |
| 5 | 舊的 PR／至少一人 review 規則已被直接 main 工作流取代。 | 歷史紀錄，不代表現在必須另開 PR。 | 目前以 CLAUDE §0.1 及當次使用者授權為準；完整交付回報測試與 CI。 |
| 6 | 超時升級依賴 API 內或獨立 APScheduler worker，deadline 存於 graph state／threads。 | 沒有任何 worker 運行就不會掃描；不具完整 durable queue／DLQ。 | 目前已有實作，不再寫成純旁白；完整追蹤交付與分散式排程見 REVIEW §6。 |
| 7 | Timeline Curator 只做結構（同日事件連結、疑似重複提示），不重寫既有 entry。 | 與設計一致（demo 資料先整理好）。 | — |
| 8 | 影像分析、119／特約通知、LINE 發送皆為顯示不真發（`displayed_only`）。 | Demo 範圍內。 | 設 `LINE_CHANNEL_TOKEN` + `LINE_FAMILY_TO` 即真發。 |
| 9 | Web Speech API 只在 Chrome／Edge 可用；Safari 部分支援。 | 照護者頁面在不支援的瀏覽器會提示改打字。 | — |
| 10 | 中文分句用標點。一句話沒有標點時整句是同一個 clause，多個維度會共用同一段 raw_quote。 | provenance 仍正確（子字串），但 raw_quote 較長。 | LLM 模式會給更精確的片段。 |
| 11 | Demo 只有 zh-TW。`lexicon.py` 仍含印尼／越南語關鍵字、`translate_instruction` 仍在，但介面沒有語言切換、seed 與 eval 全為中文。 | 多語為第二階段。 | schema 的 `lang` / `language_original` 保留，預設 zh-TW。 |
| 12 | 真模型時每輪追問 1 次 `llm.next_question` ＋ 每句 1 次 `llm.extract`（已快取），約 2–5 秒／輪；巡診每位住民 2 次 deep agent 派工（familiarization_writer 會呼叫 analyze_trends ×2、get_round_context、submit_round_page，共約 6–10 次模型呼叫），三人約 2–4 分鐘。 | demo 節奏。 | 畫面有「傳送中…／產生中…」。 |
| 13 | deep agent 若未照指示派給 subagent 或 subagent 沒有 submit，節點丟 `AgentDidNotDeliver`，API 回 503，畫面顯示錯誤（不退回模板）。`MODEL_PROVIDER=mock` 只在 pytest／CI 用 scripted test double（trace 標 `scripted: true`）。 | 真模型偶爾需要重送（submit 驗證回 error 後模型會修正再送）。 | 巡診頁可重新「產生」。 |
| 14 | OpenAI 帳號的 gpt-4.1 TPM 上限 30k：三位住民的 deep agent 若平行跑會 429。已改成巡診一次跑一位（`agents/personal.py` 的 `_DEEP_AGENT_LOCK`；原本的 LangGraph `max_concurrency=1` 與 `stream_mode="custom"` 併用會死鎖，已移除）、工具回給模型的內容精簡（趨勢 series 不進模型上下文）、429 時依供應商建議秒數等待後重試（trace 有 `deep_agent.rate_limited`）。 | 巡診三人約 1–2 分鐘。 | 需要更快可提高帳號額度。 |
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
| 28 | 身份仍是 demo 靜態表；web IDENTITIES 與 seed identities 需同步。現在已有 `/login`，但 cookie 不是可信 session。 | 新身份要改兩處；登入頁存在不代表 API 受保護。 | M1 先統一後端 session／病人關係／授權，見 #35、#43。 |
| 29 | 「問我的紀錄」檢索是關鍵字 bigram（去停用詞），不是向量檢索；同義詞（例：「心臟開刀」vs「心臟手術」）可能找不到而回「紀錄裡沒有這件事」。 | 回答保守（寧可說沒有），不會捏造。 | 第二階段換 embedding；答案仍須引用既有行。 |
| 30 | 感測事件的硬條件門檻寫死在 `red_flags/rules.py`（靜止 60 秒、SpO₂ 92）；`/sim/fall` 為模擬，沒有真實穿戴裝置。 | Demo 用 `{"still_seconds":90}` 觸發硬條件。 | **硬條件維持不變**（它們回答的是「對任何人危不危險」）；2026-09-05 另加 RF13：從 timeline 已量測的 vitals 算出每位住民自己的正常帶，偏離自己的範圍時 `observe`。裝置本身仍是第二階段。 |
| 31 | `make seed` 會清掉 records（含 conversation、sensor_events、care_circle 的變更），但 DB 的舊 thread 仍在 → 紅燈橫幅可能疊卡（#17）。 | 錄影前 `make reset`。 | — |
| 32 | omni-twin-3.v0.build 需登入才看得到預覽與 chat（Preview setup failed／read-only），本輪未能讀取其 UI 想法。 | 尚未併入。 | 使用者匯出截圖或原始碼後再對齊。 |
| 33 | 列印白底驗證用的是醫師 docs tab（事件資訊包）；RoundPage 需先跑巡診流程（約 2.5 分鐘）才會出現，本輪 `make seed` 後沒有已發布的 RoundPage。RoundPage 卡片本身以 `data-theme="white"` 呈現，列印時整頁切白色 tokens。 | 截圖 `print-1280-white.png` 是事件資訊包。 | 錄影前跑 `/nurse/round` 發布後再印。 |
| 34 | 頂欄的地點·天氣是示意假資料（規格 §3.1 允許）；「孿生同步中」燈只代表頁面在輪詢，不代表裝置連線。 | 觀感。 | 第二階段接真資料。 |
| 35 | `/role?set=` 可設定 demo 身份；登入與請求 headers 沒有完整可信身分鏈。 | 不只 UI 繞過；部分 API 缺授權或使用預設 nurse，可能直接跨病人讀寫。 | **未修，禁止接真實資料或公開暴露**；以 REVIEW §1–3 的 HTTP 負向矩陣修復，不只封鎖網頁路徑。 |
| 36 | 01 的解剖 SVG 約 900 KB（一次載入、瀏覽器快取）；器官對維度的對應是示意（如「皮膚」熱點固定在上臂、「疼痛」浮動在髖部），不是臨床定位。 | 首次載入多約 0.3 秒。 | 第二階段可換 3D 模型或依疼痛部位移動熱點。 |
| 37 | 生理值正常帶只涵蓋 `Vitals` 六個欄位（體溫、收縮壓、舒張壓、心率、呼吸、血氧），八維度中的其他七個（進食、排泄、活動、認知、睡眠、皮膚、疼痛）沒有數值序列可算，仍只有護理師寫的 `BaselineEntry` 文字描述。 | RF13 只對 vitals 生效。 | 需要那七個維度也有可比較的量，才談得上算帶；目前 `DimensionValue.value` 多半是文字。 |
| 38 | ~~Windows 上 `uv run pytest` 有 25 個 UnicodeDecodeError~~ **已修（2026-09-05）**：`record/store.py` 的 `read_text()` 沒指定編碼，Windows 預設 cp950 而檔案是 UTF-8。 | 只影響非 UTF-8 預設編碼的平台（macOS/Linux 不受影響）。 | 補 `encoding="utf-8"`；133 個測試在 Windows 上全過。 |
| 39 | 舊 `make test` 缺 format；舊 Windows gate 可略過前端或吞失敗，codegen 比對會先改檔。 | 先前測試通過不代表完整 gate；c0a6802／6c12cd2 的 CI failure 已查證。 | **已修 2026-09-06**：完整 check 不吞失敗、明確 API-only、唯讀 codegen、建置後 typecheck；新增 12 個腳本測試。 |
| 40 | 3D 分身模型 9.2 MB 進 git（`apps/web/public/models/my_avatar.glb`），首次載入約 1–3 秒；沒有 Idle 動畫（模型不含 animations），姿態切換無效果；ARKit blendshape 名稱以模型實際為準，缺的表情會被略過。 | 分身頁首屏較慢。 | 第二階段：Draco 壓縮、加動畫。 |
| 41 | 「唸給我聽」用瀏覽器 speechSynthesis，中文語音依作業系統而定；無語音時按鈕無反應。 | 只影響本人區。 | — |
| 42 | RF13「偏離他平常」在 01 與護理站只以文字顯示，需要 ≥12 筆、≥5 天量測才會建立；seed 的三位住民都有 28 筆所以會出現，真實新住民前幾天不會有。 | 新住民 01 的生命徵象面板只顯示護理師寫的基線。 | 設計如此（隊友 c0a6802 的 established 門檻）。 |
| 43 | API 的身份 fallback、summary 回應未按 scope 投影、grant/revoke 以全域角色判斷。 | 人工確認者可偽造／跨病人資料風險。 | **P0 未修**，證據與 Done 見 [PROJECT_REVIEW](PROJECT_REVIEW.md) §1–3。 |
| 44 | 檔案式紀錄缺多檔交易／完整版本更正；Postgres 不可用可降級記憶體。 | checkpoint、病歷與 provenance 不能視為同一個交易系統。 | M3 儲存契約＋故障／重送／還原測試；本輪只驗證 DB 可用時跨重啟保留流程。 |
| 45 | `0ee23aa` 已補 purpose 欄位與非空檢查，但沒有 per-request purpose 的政策判斷與完整拒絕稽核。 | 只新增 purpose 字串不足以落實政策。 | M2：allowed purposes、request purpose、policy decision、舊資料遷移。 |
| 46 | Windows mock eval stdout 曾因 cp950 無法印出特殊符號。 | 完整 check 正確以非零退出，未誤報成功。 | **已修 2026-09-06**：check_eval 設 UTF-8；輸出與 records 使用臨時目錄，保留歷史報告。 |
| 47 | `dev.ps1 init/reset` 的本機建庫目標仍固定 localhost／record_follows_person，而 migrate／seed 使用應用設定。 | 自訂 DATABASE_URL／RECORDS_ROOT 時，顯示目標與實際受影響資料可能不同；本輪未執行這些破壞性指令。 | 不用 init/reset 管自訂或非示範環境；後續統一解析、顯示並驗證精確 DB／records 目標。日常啟動不需 reset。 |
| 48 | 合成 wearable 原始固定日期會過期，fresh clone 的近 14 天測試因此只回 13 筆。 | 測試成敗隨執行日期變動，不是 API 應把歷史資料永遠當成 current。 | **已修 2026-09-06**：測試與 runtime smoke 明確傳 seed end_date；新增跨年度視窗、原件不變、過期 wearable 不回 current 的 3 個案例。預設 seed 歷史日期保留。 |
| 49 | `next/font/google` 建置時需連線 Google Fonts；本輪 fresh clone 曾因字型 CDN 連線失敗而 build 退出。 | repo 不依賴旁邊資料夾，但尚不是完全離線建置；安裝套件也需 registry。 | 保留錯誤，不把失敗略過；恢復網路後重跑。若需隔離環境部署，另做附適用授權的本地字型打包，不以假字型掩蓋失敗。 |
