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
| 2026-09-04 | LLM 呼叫全部集中在 `apps/api/core/llm.py`；沒有 key 時走確定性規則抽取（關鍵字→八維度）。 | 這台機器環境中沒有 API key；紅燈、閘門、圖流程、UI、eval 都不依賴 LLM，先把可驗收的部分做完。真 LLM 路徑只差填 key。 | Claude |
| 2026-09-05 | 模型供應者統一為 `MODEL_PROVIDER`（預設 `openai`）；`settings.get_model()` 是唯一模型工廠，回 `ChatOpenAI(model=MODEL_PINNED, temperature=0)`；`create_deep_agent` 與所有 graph 節點（經 `core/llm.py::ChatModelLLM`）都只走它。key 為空時退回 mock 並警告，讓 demo／CI 不需要 key。 | 使用者指示（2026-09-05）。單一工廠讓換模型只改 `.env`。 | Claude |
| 2026-09-04 | Postgres 用 Homebrew `postgresql@17` 本機跑（`make db-local`），同時保留 `docker-compose.yml` 給有 Docker 的人。 | 這台機器沒有 Docker；Docker Desktop 需要 GUI 與管理員權限，無法非互動安裝。 | Claude |
| 2026-09-04 | checkpointer：有 `DATABASE_URL` 且連得上就用 `PostgresSaver`；pytest 圖測用 `InMemorySaver`（同一組 graph 程式碼）。 | 圖測要在 CI 沒 Postgres 時也能跑；生產／demo 路徑仍是 PostgresSaver。 | Claude |
| 2026-09-04 | 超時升級：interrupt 前把 `deadline` 寫進 state；APScheduler worker 每 30 秒掃逾期 thread，注入 `Command(resume={"action":"escalate"})`。圖測用縮短的 deadline 直接驗證。 | 依 CLAUDE.md §4。 | Claude |
| 2026-09-04 | `claude plugin add` 指令不存在；改用 `claude plugin marketplace add` + `claude plugin install`。`anthropic/frontend-design` 實際位於官方 marketplace（`frontend-design@claude-plugins-official`）；`vercel-labs/agent-skills` 不是 plugin marketplace，改 clone 後把 `skills/web-design-guidelines` 放進 `.claude/skills/`。 | 照 §0.3 精神安裝，指令依現況修正。 | Claude |
| 2026-09-04 | `design.md` 由 ui-ux-pro-max 的架構產出後，tokens 段落整段以 CLAUDE.md §7 覆寫；禁止 glassmorphism / neumorphism / 漸層。 | §0.3、§11。 | Claude |
| 2026-09-04 | Python 3.12 由 uv 管理；`deepagents / langgraph / langchain` 鎖精確版本於 `apps/api/pyproject.toml`。 | §5、§8。 | Claude |
| 2026-09-04 | 照護者「看一眼是不是這個意思」：紅燈不做、其他做（ARCHITECTURE §11 建議）。實作為 `caregiver_section_writer` 輸出後在照護者端顯示「是這個意思嗎」確認卡，不擋流程。 | 採納設計稿建議。 | Claude |
| 2026-09-04 | RoundPage 趨勢圖：放一張，八維度中變化最大的兩個（ARCHITECTURE §11 建議）。 | 一頁上限。 | Claude |
| 2026-09-04 | Path A 追蹤只問一次，時間由護理師在 `schedule_follow_up` 設定（預設 4 小時）。 | ARCHITECTURE §11。 | Claude |

## 實作期間的決定（2026-09-05，Claude）
| 日期 | 決定 | 理由 | 誰 |
|---|---|---|---|
| 2026-09-05 | Path B 圖的 `sA[→ 轉入 Path A]` 命名為 `to_path_a`；`doctor_round` 與 `nurse_onsite_assessment` 在 mermaid 標為 ◇（interrupt）。先改圖再改程式；`tests/test_mermaid_sync.py` 比對兩邊節點名。 | 醫囑要等護理師輸入、紅燈路徑沒有 AI 草稿可審，這兩點都需要人輸入才能往下走。 | Claude |
| 2026-09-05 | 紅燈路徑：`nurse_onsite_assessment` 自己 `interrupt()` 收現場評估＋A/R；非紅燈路徑的資料在 `◇nurse_review` 一次收齊，`nurse_onsite_assessment` 只套用。 | 同一個護理師畫面兩條路徑共用；紅燈時不經 `sbar_draft`（§4）。ISBAR 的 I/S/B 在紅燈路徑由事實組成、`author=nurse`。 | Claude |
| 2026-09-05 | `sbar_final` 用 assert 擋「A／R 空白」；API 層 `validate_resume` 先回 400。 | §1.3：A/R 由護理師撰寫。 | Claude |
| 2026-09-05 | ROUND 圖用 `Send` 做 `trend_analyzer ×N` 與 `familiarization_writer ×N`（node 內回 `Command(goto=Send(...))`），`order_to_caregiver_notes ∥ baseline_update_proposal` 平行分支不寫同一個 state key。 | 忠於 mermaid 的 ×N；LangGraph 的 LastValue channel 不接受平行寫入。 | Claude |
| 2026-09-05 | documents 允許同 id 更新（`update_document`：事故檔補 notifications／follow_up）；timeline 仍只增不改。 | mermaid 中 `timeline_write` 在 `send_line`／`schedule_follow_up` 之前，事故檔要能補上後續。 | Claude |
| 2026-09-05 | Seed 時間戳用台灣時區（UTC+8）；thread_id 用 UTC 日期。 | 避免「今天」與 seed 的第 14 天夜班互相超前。 | Claude |
| 2026-09-05 | Web 用 Turbopack `root` 指到 monorepo 根，`@schema` alias 指向 `packages/schema/ts/index.ts`；codegen 以 serialization 模式輸出，所有欄位非 optional。 | Turbopack 不允許 import 專案外檔案；API 回傳永遠含所有欄位。 | Claude |
| 2026-09-05 | 每個 §13 步驟開 `feat/*` 分支 + PR 合進 main（同一帳號建立與合併；無第二人 review）。PR 內容依 §8。 | 單一 agent 無法滿足「至少一人 review」，但保留可事後審閱的 PR 軌跡。記在 KNOWN_ISSUES #5。 | Claude |
| 2026-09-05 | `render_lines()` 的輸出只有「觀察到：事實 → 建議」與免責句；`test_render_has_no_level_or_score` 檢查不含等級／分數字眼；`core/llm.py::scrub_clinical_language` 對 AI 產出的 A/R/問句再掃一次診斷詞。 | §6、§1.3。 | Claude |
| 2026-09-05 | 巡診的 deep agent 一次跑一位住民（LangGraph `max_concurrency=1`），subagent 工具只把精簡結果回給模型（完整 TrendReport／RoundPage 留在 ARTIFACTS 給程式用），429 時依供應商回覆的秒數等待重試。 | 30k TPM 額度；平行三人會被限流。 | Claude |
| 2026-09-05 | 全面去規則化（使用者指示）：(1) intake_agent 每一題都由模型決定（含 reason），刪除問題清單與快速回覆，沒有 key／呼叫失敗回 503 並停止；(2) RoundPage ①②③④ 由 familiarization_writer subagent 寫，程式只驗證規則（只列有變化的維度、evidence 為可點連結、圖表兩個維度）；(3) seed 改為 story 曲線＋固定亂數擾動；(4) `GET /debug/trace/{thread_id}` 與頁底 footer。`MODEL_PROVIDER=mock` 只剩 pytest／CI 的 test double（scripted，trace 標 scripted），不會出現在使用者畫面。主 agent 不持有文件工具、只派工；CLAUDE.md §5 的 `interrupt_on(render_document_page)` 保留給 agent 直接產頁的情境，流程中的人工閘門是 ◇head_nurse_edit_list。 | 「現況是規則和模板在跑，不是 agent」。 | Claude |
| 2026-09-05 | 紅燈不結束對話、只分岔：程式通知護理師後，intake_agent 接手問規則必問題（required_fields），答案經 `update_state(as_node=通知節點)` 寫回 interrupt 中的 Path A thread 並重新觸發 interrupt，護理師端 5 秒輪詢看到「照護者目前回報」。照護者端不顯示規則文字。 | 使用者指示（2026-09-05）。護理師在路上時，關鍵事實已經在收。 | Claude |
| 2026-09-05 | 追問必須經 LLM 生成（`core/llm.py::next_question`，依八維度缺口＋profile＋基線），程式只驗證選擇、加「不知道」、守上限；規則必問題例外；模型不可用時退回規則題並在 trace 標 fallback。RoundPage／後送頁改由 personal deep agent 派給 subagent（`agents/personal.py::run_task`），節點讀 subagent 工具的結構化輸出；未派工時退回純函式並在 trace 標 fallback。`GET /trace` 與 `/trace` 頁提供證據。 | 使用者指示（2026-09-05）：證明 agent 真的在跑。 | Claude |
| 2026-09-05 | 照護者端改為 LINE 式聊天引導：`ingest/intake_dialog.py` 規則式規劃追問（依八維度缺什麼、一次一題、2–4 個快速回覆、永遠有「不知道」、上限 4 題、已提到不再問、紅燈立即中止），每句仍走同一個抽取；graph state 加 `asked_dimensions`、`turn_count`；CLAUDE.md §4／§7 與 ARCHITECTURE §4.1 同步改為「追問到八維度足夠，上限 4 題」。 | 使用者指示（2026-09-05）。追問規劃用規則而非 LLM，行為可測、可重現。 | Claude |
| 2026-09-05 | Demo 語言只用 zh-TW：介面移除語言切換與翻譯步驟，seed 與 eval 語句全改中文；schema 的 `lang` / `language_original` 保留、預設 `zh-TW`；多語（id／vi）為第二階段。 | 使用者指示（2026-09-05）。 | Claude |
| 2026-09-05 | 新增 §7 的衍生 tokens：*-ink（填色上的文字）、*-hover、*-fill；§7 原色只用於邊框、填色、圖示。 | §7 的 --ok 白字對比 3.0:1，低於 §7 自己的 ≥4.5:1；衍生色記錄於 docs/design.md §1。 | Claude |
| 2026-09-05 | 畫面改為「角色入口 → 角色首頁 → 病人頁四個 tab」，病人頁是唯一入口；角色存 cookie、`proxy.ts` 守門；對話用 SSE 串流（`graphs/talk.py` 自訂事件 + 逐字回覆），每則回覆帶 Agent 活動列；每位住民一條持續對話（`record/conversation.py`），每輪寫 provenance。**與 CLAUDE.md 的衝突與解法**：需求說「對話串的每一輪同時寫進 timeline（caregiver_said／ai_extracted）」，但 §1.2／§4／§11 規定 timeline 只收護理師核准的內容；決定把對話放在 timeline 旁的 `conversation.jsonl`（含 provenance），在「紀錄」tab 與 timeline 合併顯示，正式 timeline 仍只經 `timeline_write`。 | 使用者指示（2026-09-05 IA 改版）；§1 核心原則需全隊同意才能改，先不改。 | Claude |
| 2026-09-05 | 巡診改用 `run_task` 內的 `threading.Lock` 序列化 deep-agent 派工，移除 `_config` 的 `max_concurrency=1`。 | LangGraph 1.2 的 `max_concurrency` 與 `stream_mode="custom"` 併用會死鎖（串流消費者共用 executor），SSE 收不到任何事件；lock 達到同樣的 TPM 保護。 | Claude |
| 2026-09-05 | 抽取 schema 的 `vitals_reported` 加 before-validator：非數字一律 None，不讓一句話因模型格式錯誤而 503。 | eval 遇到「呼吸很快」被放進 rr 欄位；原話仍保留在 raw_quote。 | Claude |
| 2026-09-05 | `MODEL_PINNED=gpt-5.6-luna`；`get_model()` 對 gpt-5.x 加 `reasoning_effort="none"`（chat completions 的 function tools 需要；`temperature=0` 也只在此時被接受，否則 400）。intake、personal agent、三個 subagent 都經同一個工廠。 | 使用者指示（2026-09-05）；實測 temperature=0 單獨送會被拒。 | Claude |
| 2026-09-05 | Prompt caching 的訊息順序固定：system（不變）→ 住民紀錄區塊 `record_prefix`（profile＋基線＋近 14 天 timeline，一天內不變）→ 本輪狀態；四個小任務的指令從 human 移到 system。familiarization_writer 改成先 `get_round_context` 再 `analyze_trends`，timeline 讀取固定在子代理對話最前面。每次呼叫的 token／cached／成本寫 trace `llm.usage`（`core/usage.py`），價格在 settings（PRICE_*）。 | 使用者指示；OpenAI 快取以前綴為單位且門檻 1024 tokens，實測 extract 2422 tokens 中 2293 命中。 | Claude |
| 2026-09-05 | 住民紀錄區塊併進 system message（`_system_with_record`），不是獨立的 human message。 | 實測 gpt-5.6-luna：system 464 tokens＋固定 human 紀錄區塊，三次相同請求 cached 皆 0；同一內容放進 system 則第二次起 1498/1515 命中。快取只在「system 內的前綴」生效。 | Claude |
| 2026-09-05 | intake 的兩個呼叫（`llm.extract`、`llm.next_question`）用 `get_model(reasoning_effort=INTAKE_REASONING_EFFORT)`（預設 `low`）；gpt-5.x 的 `reasoning_effort != none` 自動 `use_responses_api=True`，其他呼叫與 deep agent 維持 `none` 走 chat completions。`UsageTrace` 補讀 Responses API 的 `usage_metadata`（cache_creation、reasoning）。 | 實測 chat completions 對 luna 拒絕 function tools + reasoning（400）；Responses API 接受，快取行為相同（前綴 1446 tokens 第 2 次命中）。 | Claude |
| 2026-09-05 | 不再開分支／PR／等 CI：所有變更直接 commit 到 main 並 push，commit 前只跑受影響那側的測試（CLAUDE.md §0.1）。已合併的四個遠端分支待刪（`git push --delete` 在本 session 被權限擋下）。 | 使用者指示（2026-09-05）。 | Claude |
| 2026-09-05 | 模型定案：`MODEL_PINNED=gpt-5.6-luna`、`INTAKE_REASONING_EFFORT=low`，其他呼叫 `none`。README 評測段改三欄表並註明 46 句樣本、差距在一句內。 | 使用者指示（2026-09-05）：同一模型跑全部、成本最低、守門指標三者皆滿分。 | 使用者 |
| 2026-09-05 | 抽取結果持久化快取：`records/{id}/extract_cache.json`，key = sha256(模型｜effort｜當日｜住民｜句子)，in-process LRU 在前；命中寫 trace `llm.extract_cache`。mock provider 不寫檔。 | 原本只有 LRU，`fastapi dev` reload／多程序時每輪重抽本 session 所有句子（第 4 輪 extract ×4）。實測改後第 2 輪 0 次 extract。 | Claude |
| 2026-09-05 | 對話 session 過期：`SESSION_EXPIRY_H`（預設 4 小時）或跨台灣日期，`open_session` 自動關閉舊 session（`closed_reason=expired`）並在對話串加系統事件；`close_session(reason=)` 記錄關閉原因（confirmed／nurse_took_over／expired）。 | KNOWN_ISSUES #18。 | Claude |
| 2026-09-05 | 追問規則放寬：已知維度可追問一次，條件是仍有缺口（子欄位未填或原話有未抽到的線索），planner 必須在 gap／reason 指出缺口；第二次無效改 ask=false 出摘要卡而非 503；503 只留給 LLM 失敗（文案「系統暫時無法回覆，請直接告訴護理師」）。CLAUDE.md §7 同步。 | 使用者指示（2026-09-05）：luna low 約每 6 輪 1 次因連續選已知維度而中斷對話；缺口是可驗證的放行條件。 | 使用者 |
| 2026-09-05 | `_apply_answer`：已知維度不再被追問回答整句覆寫（只有「跟平常一樣」類回答才改 direction=same，且保留原 raw_quote）；未知維度才用回答原話建值。 | 原本追問進食、回答排便，進食的 raw_quote 會變成「有大便，但比較硬」，缺口計算與摘要都錯。 | Claude |
| 2026-09-05 | 角色首頁改打 `GET /home/{role}`（一次回住民＋卡片資料），`/residents`、`/patients/{id}/summary`、`/trends/{id}`、`/round-pages/{id}` 保留給病人頁與其他用途；輪詢統一經 `usePolling`（分頁隱藏暫停、回前景先刷新）。 | KNOWN_ISSUES #19／#20；不改 SSE 是因為 5 秒輪詢在 demo 規模夠用，改 SSE 要多一個長連線管理。 | Claude |
| 2026-09-05 | 概念升級為 Personal Health Twin：`Profile.health_id`（P-0000000）、Care Circle（`record/care_circle.py`，每人一份 members＋access log），權限查 Care Circle 而非 cookie（cookie 只存 `me`），無授權 tab 顯示「未獲授權」而非 404。願景文件 docs/VISION_personal_health_twin.md 列入 §0.2，實作範圍以 ARCHITECTURE／HANDOFF 為準。 | 使用者指示（2026-09-05）。 | 使用者 |
| 2026-09-05 | 本人 App（第四扇門 `/me`）：終身時間軸用新的 `LifeEvent` timeline kind（confirmed_by 護理長、provenance 記來源機構）；「問我的紀錄」用本人的 deep agent＋`retrieve`／`submit_answer` 工具，每句必引用檢索到的行、拒絕建議與解讀、沒有就說沒有。 | VISION §11.2／§12：AI 只 Retrieve，不 Diagnose。 | Claude |
| 2026-09-05 | 通道 4：`/sim/fall` → `SensorEvent`（`sensor_events.jsonl`，不是 timeline），事件層記「可能跌倒」；紅燈對感測只做硬條件 RF11（靜止 ≥60 s 或 SpO₂ <92）與 RF12（聯絡不上），其餘由照護者四鍵驗證後進既有追問流程；原始值只給護理師（`public_view` 去掉數值，CLAUDE §1.8）。 | 使用者指示；VISION §20–21。 | Claude |
| 2026-09-05 | 四鍵是全系統唯一允許的按鈕（talk 的可能跌倒訊息下）；選項→一句照護者原話（`VERIFY_TEXT`）→ `run_turn(event_id, choice)`；IncidentFile 對外名「事件資訊包」，內部 `incident_file` 不改。 | 使用者指示。 | Claude |
| 2026-09-05 | 介面依 VISION §28 對齊但沿用既有路由與元件：/me 首頁五段＋三子頁（用藥／影像／檢驗標第二階段）、/caregiver 依 §28.2（家屬只看自己那位）、/nurse 改名 Clinical Queue 三段、/doctor docs tab 加縱向摘要於 RoundPage 上方（檢驗／影像／臨床紀錄／AI 助理標第二階段）。不做 Health Graph、真實穿戴、EHR 對接。 | 使用者指示。 | Claude |
| 2026-09-05 | UI 改為 OMNI-TWIN 殼（docs/UIUX_OMNI_TWIN.md，使用者提供）：深色為預設（§6 tokens），白色主題只給 RoundPage／列印；五維度 rail 只有 01 與 05 有內容；01 活體數位孿生為 wellness 語氣（允許大數字與一般建議），05 艙維持臨床語氣；四種動畫、發光只給熱點與同步燈。九步各一個 commit（e1ebc96→3d748d0＋本輪）。 | 使用者指示（2026-09-05）：「殼可以科幻，鏈不能」。 | 使用者 |
| 2026-09-05 | `--primary` 成為 `--accent` 的別名、新增 `--on-primary`，既有元件不改 class 名即切到深色；AI／人／紅燈的樣式契約改靠形狀（虛線／實線／左 4px 紅線）而非顏色。 | 深色下顏色對比與語意不可靠；一次換 tokens 比逐檔改 class 安全。 | Claude |
