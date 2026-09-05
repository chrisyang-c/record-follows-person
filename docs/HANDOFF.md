# HANDOFF — 交接（2026-09-05）

Repo：https://github.com/chrisyang-c/record-follows-person ・ 2026-09-05 起直接 commit 到 `main` 並 push（不開分支／PR，見 CLAUDE.md §0.1）。
先讀：docs/OVERVIEW.md（全貌）→ CLAUDE.md → docs/ARCHITECTURE.md → docs/ACCEPTANCE.md（驗收與指令）→ docs/DECISIONS.md（為什麼）→ docs/KNOWN_ISSUES.md。

> **這份文件只管「目前進度與下一步」。** 為什麼這樣決定 → `DECISIONS.md`；
> 之後要做什麼、依什麼順序、明確不做什麼 → `ROADMAP.md`；
> 已知問題與繞法 → `KNOWN_ISSUES.md`。完整分工表在 CLAUDE.md §0.2。

---

## 已完成（工作區整併，2026-09-05）

**這個 repo 現在是唯一的正式專案。** 只取得它就能開發、啟動、測試，不依賴工作區其他資料夾。

| 項目 | 結果 |
|---|---|
| 整合清單 | `docs/CONSOLIDATION.md` —— 每份來源內容的去向（來源 → 用途 → 目的位置 → 採用狀態 → 驗收方式） |
| 外部提案 | `docs/proposals/00-architecture.md`，頁首標明**未採納**、與本 repo 是兩條路；逐項取捨在 CONSOLIDATION §3 |
| 分期計畫 | `docs/ROADMAP.md` —— Epic 排序、Done 條件、**明確不做**清單 |
| 文件分工 | CLAUDE.md §0.2 新增分工表；§0.3 的 `claude plugin add` 與 §0.4 的 docker 已改為可用指令 |
| PR 矛盾 | §0.1 說不開 PR，但 §1／§5／§8 還在講 PR —— 四處已改為 commit |
| Windows 入口 | `scripts/dev.ps1`。日常指令不碰 `records\` 或資料庫；`init`／`reset`／`seed`／`clean-records` 會列出將刪除什麼並要求輸入 `yes`（CI 用 `-Force`） |
| 個人生理值正常帶 | `apps/api/baseline/` ＋ RF13（`c0a6802`）；`propose_vitals_usual` 依 ARCHITECTURE §11 移除（`6c12cd2`） |

**採用 `health-ref` 的限制**：它沒有 LICENSE（`chenni416/Healthcare`），本 repo 是 Apache-2.0。
依 CLAUDE.md §0.5 **只能借想法，不能複製程式碼**。詳見 CONSOLIDATION §2。

### 下一步（依序）

1. **CONSOLIDATION §4 的 `purpose` 欄位** —— `CareCircleMember` 與 `AccessLogEntry` 缺 VISION §16 的 WHY。目的位置與驗收方式已寫好，未執行。
2. **ROADMAP E1**：找 1–3 位護理師連續用一週。後面每個 Epic 的優先序都會被這週的結果重排。
3. ROADMAP E2 Retrieval（KNOWN_ISSUES #29 的向量檢索）。

### 整併期間發現、尚未處理的

- `c0a6802` 推上 main 時 **CI 應該是紅的**：`ruff format --check`（ci.yml L33）會抓到 5 個檔案格式不符。已於本輪修正，但這說明「不等 CI」的規則需要本機先跑 `.\scripts\dev.ps1 check`。
- `health-ref` 有 18 檔 / 5,528 行未提交，且 `backend/venv` 有 4,101 個檔案被 commit 進該 repo —— 屬該 repo 擁有者處理。
- `claude_healthcare` 已依指示刪除，除 baseline 引擎外約 13,500 行不可回復（CONSOLIDATION §2.2）。
## 已完成（參考 health-ref 的互動，2026-09-05 深夜）

使用者指示參考隊友的 `../health-ref`（§0.5）：3D 分身進 01（`components/twin/avatar-model.tsx`、`avatar-view.tsx`，模型 `public/models/my_avatar.glb`＋LICENSE.txt）、沙盤模擬、穿戴每日指標（schema `WearableDaily`、seed 14 天、`/twin/{id}.wearable`）、今天的身體四卡＋複合圖、「唸給我聽」（`ask-box.tsx`）、本人自記（/me，寫進對話串）、回答聚焦維度。不借的三項與理由見 DECISIONS。KNOWN_ISSUES #37–#38。

## 已完成（登入與 01 住民選擇，2026-09-05 深夜）

`/login`（角色 → 身份 → 住民 → 病人密碼；示範密碼＝出生年）、`POST /login`（`tests/test_login.py` ×4）、`/` 直接轉 `/login`、頂欄「切換」。工作人員進 01 先選住民（`/twin?pid=`），修掉護理師進 01 一直 Loading 的問題。限制見 KNOWN_ISSUES #35。

## 已完成（OMNI-TWIN 殼，2026-09-05 深夜）

依 docs/UIUX_OMNI_TWIN.md §9 九步各一個 commit（`git log --grep 'ui(omni-'`）：深色 tokens 預設＋白色列印、殼（頂欄／rail／麵包屑／底部 tab）、四艙進殼、元件系統、Clinical Queue 重排（#21 修）、01 人體圖與 `GET /twin/{id}`、/me 八小卡、手機版面、列印與對比稽核。細節：ACCEPTANCE「OMNI-TWIN 殼」、UI_AUDIT 同名段、DECISIONS 末兩行、KNOWN_ISSUES #33–#34。**規格 §7 動畫只有四種、§10 不可違反已併入 CLAUDE.md §1.9。**

## 已完成（Personal Health Twin，2026-09-05 晚）

六塊各一個 commit（`89cb46d`→`48206d6`→`e044c2c`→`6a7a26e`→`903d584`→本輪）：Health ID＋Care Circle＋access log；本人 App `/me`（LifeEvent、問我的紀錄）；通道 4 `/sim/fall`＋RF11／RF12；照護者四鍵；事件資訊包／README／VIDEO 十幕／CLAUDE §1.8；介面對齊 VISION §28（截圖 `pnpm screenshot:twin`）。細節見 ACCEPTANCE「Personal Health Twin」、DECISIONS 2026-09-05 末五行、KNOWN_ISSUES #28–#32。
先讀 docs/VISION_personal_health_twin.md（願景）再讀 ARCHITECTURE（實作範圍以 ARCHITECTURE／HANDOFF 為準）。

**未做（第二階段，README 已標）**：Health Graph、真實穿戴裝置、醫院 EHR／FHIR 對接；omni-twin-3.v0.build 的 UI 想法需登入才看得到（#32），待使用者提供截圖或原始碼。

## 已完成（前一輪，2026-09-05）

| 項目 | 在哪裡 | 證據 |
|---|---|---|
| 模型切換 `MODEL_PINNED=gpt-5.6-luna`：`settings.get_model()` → `ChatOpenAI(model, temperature=0, reasoning_effort="none")`；intake、personal agent、三個 subagent 都經它 | `apps/api/core/settings.py` | `tests/test_model_and_usage.py`；ACCEPTANCE「模型換成 gpt-5.6-luna」 |
| Prompt caching 訊息結構：一則 system（任務指令 + `record_prefix`：profile／基線／近 14 天 timeline，一天內不變）+ 一則 human（本輪）。實測此模型只快取 system 內前綴 | `apps/api/core/llm.py`（`_system_with_record`、`record_prefix`） | 對話第 2 輪起 extract 94%、next_question 82% 命中 |
| 每次模型呼叫寫 `llm.usage`（tokens、cached、cache_write、估算 USD）；eval 報告加成本表 | `apps/api/core/usage.py`、`eval/run.py` | `apps/api/eval/results.md`；`GET /debug/trace/{thread_id}` |
| 追問規則：planner 驗證模型決定；已知維度只有仍有缺口（`known_gaps`）且 gap／reason 指出缺口時可追問一次；重複／無效 → 帶原因重問一次，第二次無效 → ask=false 摘要卡（不 503）；503 只留給 LLM 失敗 | `apps/api/ingest/intake_dialog.py::_plan`、`graphs/talk.py`、`record/conversation.py` | `tests/test_talk_graph.py`、`test_intake_dialog.py` |
| writer 子代理先 `get_round_context` 再 `analyze_trends`（timeline 讀取固定在最前面） | `apps/api/agents/personal.py` | 巡診 thread `ALL:round:2026-09-04:8`，30 次呼叫 $0.012 |
| Eval 重跑（luna）：hallucination 8.7%、omission 4.3%、provenance 100% | `apps/api/eval/results.md` | ACCEPTANCE 表（對照 gpt-4.1：4.3% / 2.2%） |
| PR #9 病人頁 IA／talk 串流／活動列、#10 docs、#11 本輪 | GitHub | CI api + web 綠 |

## 待做（依序）

1. ~~extract 與 next_question 改 `reasoning_effort="low"` 重跑 eval~~ **已做（2026-09-05）**：`INTAKE_REASONING_EFFORT`（預設 low → Responses API）、ACCEPTANCE Eval 表三欄、KNOWN_ISSUES #26。結論：low 在這兩個 prompt 上 reasoning tokens 為 0，成本不變，hallucination 8.7%→6.5%（gpt-4.1 仍 4.3%）。**定案**：luna + intake low（README 評測段三欄表）。
2. ~~對話 session 過期（KNOWN_ISSUES #18）~~ **已做（2026-09-05）**：`SESSION_EXPIRY_H`＝4 小時或跨台灣日期自動關閉；順手把抽取快取持久化到 `records/{id}/extract_cache.json`（每輪只抽新的一句）。
3. ~~角色首頁批次 summary 端點（#19）、輪詢在分頁隱藏時暫停（#20）~~ **已做（2026-09-05）**：`GET /home/{role}`、`usePolling`。
4. ~~10 秒確認「改一句／退回」改成不鎖鍵、就地提示（#21）~~ **已做（OMNI-TWIN 第 5 步）**。
4b. ~~omni-twin-3.v0.build 的 UI 對齊~~ **已做**：使用者提供截圖與規格（docs/UIUX_OMNI_TWIN.md），已依九步遷移。剩：RoundPage 白底列印實跑一次（#33）。
4c. 身份表兩處同步（#28）改成只讀 `records/_identities.json`（API `/whoami`）。
5. SSE 客戶端斷線取消後端 graph（#22，`core/trace.run_in_thread` 加 cancel flag）。
6. 若全隊同意改 CLAUDE.md §1：對話每輪直接寫 timeline（#15，改 `record/conversation.py::append` 一處）。
7. 影片：`make reset` 後照 docs/VIDEO.md 錄；紅燈用李阿公第二個例子。

## 已知問題

全表在 docs/KNOWN_ISSUES.md（#1–#38）。最影響 demo 的：
- #17 測試留下的紅燈 thread 會疊卡 → 錄影前 `make reset`。
- #18 已修（4 小時／跨日自動過期）；同一天 4 小時內連續測試仍共用一段 → 說「不對」重來或 `make reset`。
- #26 已修：已知維度有缺口可追問一次（gap 驗證）、第二次無效改摘要卡、503 只留給 LLM 失敗。
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
