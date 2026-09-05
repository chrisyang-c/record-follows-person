# CLAUDE.md — 一份能跟著人走的紀錄

> 每個人有一份跟著他走的紀錄，和一個替這份紀錄說話的 agent。今天，它先學會聽照顧他的人說話。

BUILDMODE 2026 × SITCON ・ Healthcare AI 賽道 ・ 4 人團隊 ・ 目標：≤2 分鐘影片 + 可重現的 GitHub repo。

---

## 0. 開工順序（第一次進 repo 時，依序做完再寫任何程式）

### 0.1 建立 repo 與遠端
```bash
# 若尚未 init
git init -b main
gh auth status || gh auth login
gh repo create record-follows-person --public --source=. --remote=origin --description "每個人有一份跟著他走的紀錄，和一個替這份紀錄說話的 agent"
git add . && git commit -m "chore: bootstrap" && git push -u origin main
```
- 若 repo 已存在：`git remote -v` 確認 origin，`git pull --rebase origin main`。
- 分支規則（2026-09-05 起）：不開分支、不開 PR、不等 CI；所有變更直接 commit 到 `main` 並 push。
- 每次 commit 前只跑受影響那一側的測試：api 改動 `cd apps/api && uv run pytest -q`；web 改動 `cd apps/web && pnpm typecheck && pnpm test`。過了就推。

### 0.2 先讀這些檔案（不讀完不准動架構）
```
docs/langgraph_path_a_incident.mermaid       # Path A 急症圖，節點名與 interrupt 點是規格
docs/langgraph_path_b_routine_round.mermaid  # Path B 日常＋巡診圖
docs/ARCHITECTURE.md                          # 唯一設計稿：層級、通道、agent、節點細節、state、demo 範圍、未決事項
docs/一份能跟著人走的紀錄_摘要與願景.md       # 對外敘事與制度出處（README 引用）
docs/VISION_personal_health_twin.md           # 願景文件（Personal Health Twin）；實作範圍以 ARCHITECTURE.md 與 HANDOFF.md 為準
docs/UIUX_OMNI_TWIN.md                        # UI/UX 規格：OMNI-TWIN 深色殼 × 臨床安全核心（取代 §7 白色單一主題）
```
讀完後在 `docs/DECISIONS.md` 追加一行「已讀，日期，姓名」。Mermaid 圖是 LangGraph 節點名稱的唯一來源；改圖要先改檔再改程式。

### 0.3 安裝 skills（UI 穩定性三件組，順序固定）
```bash
claude plugin add nextlevelbuilder/ui-ux-pro-max-skill   # 產 design.md，之後所有畫面從它長
claude plugin add anthropic/frontend-design               # 防 AI 通用審美
# 稽核：vercel-labs/agent-skills → skills/web-design-guidelines，依其 README 安裝
```
規則：ui-ux-pro-max 產出的 design.md 必須以本檔 §7 的 tokens 覆寫（禁止它自選 glassmorphism / neumorphism）；每個畫面完成後跑 web-design-guidelines 稽核一次並把結果貼進 PR。

### 0.4 環境
```bash
cp .env.example .env            # 填 ANTHROPIC_API_KEY, DATABASE_URL, LINE_CHANNEL_TOKEN
docker compose up -d postgres
make seed                       # 3 住民 × 14 天 + 1 急症，建 /records/{patient_id}
cd apps/api && uv sync && uv run fastapi dev
cd apps/web && pnpm i && pnpm dev
```

### 0.5 外部參考
- 隔壁目錄 `../health-ref`（Healthcare-ref）是別人的專案，**唯讀**。平常不要讀它、不要借它的東西。
- 只有使用者明確說「參考 health-ref 做 X」時，才去讀對應的那一部分；只借想法，或 MIT／Apache／CC0 授權下的程式碼，借用的檔案頂端註明出處（專案名、路徑、授權）。
- 沒有明確指示時，Claude Code 不得 `ls`、`grep`、`cat` 該目錄，也不得把它的內容寫進本 repo。

---

## 1. 核心原則（違反即 PR 退回）

1. **紀錄是唯一資產，agent 沒有自己的狀態。** 所有 agent 只做兩件事：寫進紀錄，或把紀錄講給某個人聽。狀態全在 PersonRecord。
2. **AI 只起草，人才定稿。** 照護者端產出的一切都是 `status="draft"`；只有護理師在 interrupt 節點確認後才變 `approved`，才能寫 timeline、才能送出。
3. **SBAR/ISBAR 的 A 與 R 由護理師撰寫。** AI 的 A 只寫「與基線比的變化」，R 只寫「請確認事項」（提問式）。不出現診斷詞、不出現治療建議、不出現檢傷等級數字。
4. **紅燈是純程式。** `apps/api/red_flags/rules.py` 不得呼叫 LLM。命中即推播護理師並跳過起草。
5. **每一行有來源。** provenance 不可移除、不可改寫。
6. **baseline 只在確認時更新。** 系統只能產「提案」，`nurse_confirm_baseline` 通過才寫入。
7. **合成資料，去識別化後才進 LLM。** repo 內不得有任何真實個資。
8. **任何信心值、機率、分數不得出現在照護者與醫師介面。** 感測事件的原始值（加速度、靜止秒數、心率、SpO₂）只給護理師；照護者與醫師端只看到「可能跌倒」、驗證結果與觀察到的事實。
9. **兩種語氣，一條界線（docs/UIUX_OMNI_TWIN.md §10）。** 分數、百分比、生理年齡、活力值、建議語句只允許在 01 活體數位孿生與 /me 的 wellness 區；05 艙內家屬、護理師、醫師頁面不出現任何分數、機率、信心值、建議。紅燈橫幅不可關閉，只可由護理師標「已處理」。RoundPage 與事件資訊包列印版白底。四鍵是全系統唯一的按鈕式回覆。

---

## 2. Repo 佈局
```
apps/api/                 FastAPI + LangGraph + deepagents
  graphs/path_a.py        節點名 = docs/langgraph_path_a_incident.mermaid
  graphs/path_b.py        節點名 = docs/langgraph_path_b_routine_round.mermaid
  agents/personal.py      create_deep_agent：每位住民一個實例
  agents/subagents/       trend_analyzer.py, familiarization_writer.py, handoff_packager.py
  red_flags/rules.py      純程式紅燈規則 + tests
  record/                 PersonRecord 讀寫層（唯一寫入入口：record.write_timeline）
  ingest/                 通道 Ingest：caregiver_speech.py, doctor_order.py, discharge_pdf.py(mock), vitals.py(hardcoded)
  eval/                   抽取評測腳本與合成語句集
apps/web/                 Next.js App Router + Tailwind + shadcn/ui
  app/page.tsx            角色入口（三顆大按鈕 → /role?set= 寫 cookie）；app/about 舊首頁
  app/caregiver, nurse, doctor   角色首頁（照護者：住民卡；護理師：紅燈→等我確認→今日總覽；醫師：巡診名單）
  app/p/[id]              病人頁 = 單一入口，?tab=who|timeline|docs|talk；proxy.ts 依 cookie 角色限制 tab
  app/nurse/round         巡診準備（串流顯示 roster_agent → trend_analyzer → familiarization_writer）
  components/patient/     四個 tab + activity-bar（Agent 活動列，資料來自 LangGraph 串流事件）
packages/schema/          共用 Pydantic + TypeScript 型別（單一來源，兩邊 codegen）
data/seed/                合成住民 JSON + seed 腳本
records/                  執行期建立，每位住民一個目錄（gitignore）
docs/                     本檔 §0.2 所列文件 + DECISIONS.md + 影片腳本
```

---

## 3. 資料模型：PersonRecord

```
PersonRecord
├── profile      慢病、過敏、DNR、緊急聯絡人、特約醫療機構、目前所在
├── baseline     八維度的「平常」，每筆 valid_from / valid_to / set_by
├── timeline     只增不改：Observation | Incident | Encounter | Order
├── documents    RoundPage | HandoffPage | VisitPage | IncidentFile，帶 generated_from
└── provenance   每行：source, author, confirmed_by, ts, language_original
```

**八維度（所有通道、基線、趨勢共用；定義依 INTERACT Stop and Watch 的觀察範圍校準，措辭為本專案自訂）**

| key | 名稱 | 涵蓋內容（照服員看得到、不需儀器） |
|---|---|---|
| `intake` | 進食與飲水 | 吃多少、喝多少、體重變化、嗆咳 |
| `elimination` | 排泄 | 排便頻率與性狀、尿量、尿色、失禁變化 |
| `function` | 活動與日常功能 | 走路、轉位、如廁需要的協助程度；參與活動；整體需要更多幫助 |
| `cognition` | 意識、認知、情緒、溝通 | 混亂、嗜睡、躁動、講話變少、認人變差 |
| `sleep` | 睡眠 | 夜間覺醒、日夜顛倒、白天嗜睡 |
| `skin` | 皮膚與傷口 | 顏色、壓傷、破皮、水腫 |
| `pain` | 疼痛 | 新出現或加重、部位、影響活動 |
| `vitals` | 生命徵象與呼吸症狀 | 護理師量測值（體溫、血壓、心率、SpO₂）＋照服員可報的咳嗽、喘、痰、發燒感 |

**跨維度旗標**：`seems_different: bool` ——「跟平常不一樣」。照服員可直接按，不強迫歸類；這是最早的訊號，Intake 不得要求他解釋才接受。

**事件快捷（進 timeline.Incident，不是維度）**：`fall` 跌倒｜`medication_issue` 拒藥／吐藥／漏藥｜`choking` 嗆咳｜`behavior` 攻擊或遊走

**維度變更規則**：改 key 名或增刪維度，需同時改 `packages/schema`、seed 資料、Trend Analyzer、RoundPage 模板，並在 `docs/DECISIONS.md` 記錄。README 註明「觀察架構參考 INTERACT Stop and Watch（Florida Atlantic University），項目措辭與分類為本專案自訂，未複製原工具」。

**provenance enum**
`caregiver_said | ai_extracted | nurse_assessed | nurse_confirmed | doctor_ordered | system_derived`

**FHIR-lite 命名對照**（欄位命名依此，不做 FHIR server）
Patient / Condition / AllergyIntolerance / Observation / MedicationStatement / Encounter / ServiceRequest / Provenance / DocumentReference

**每維度 Pydantic**
```python
class DimensionValue(BaseModel):
    value: str | float | None
    raw_quote: str            # 照護者原話片段
    provenance: Provenance
    confidence: float
    lang: str                 # 預設 "zh-TW"；"id" | "vi" 為第二階段（demo 只用中文）
```

---

## 4. LangGraph：兩張圖

節點名稱以 `docs/*.mermaid` 為準。這裡只列閘門與硬規則。

**Path A（急症）**
`load_person_record → intake_agent（多輪：追問到八維度足夠，上限 4 題；state 有 asked_dimensions、turn_count）→ baseline_comparator → red_flag_rules`
→ 命中：`notify_nurse_urgent → nurse_onsite_assessment`
→ 未命中：`caregiver_section_writer → sbar_draft → push_to_nurse → ◇nurse_review`
`◇nurse_review`：接受／修改 → `nurse_onsite_assessment → sbar_final`；退回 → `intake_agent`；超時 → `escalate`（第二護理師／護理長）→ 回 `◇nurse_review`
`sbar_final → ◇nurse_route_choice`（特約醫療機構／在宅急症模式 B／陪同就醫／轉觀察）
→ `handoff_packager → incident_compiler → timeline_write → family_notification_draft → ◇nurse_approve_notification → send_line → schedule_follow_up → END`

**Path B（日常）**
每班：`intake_agent → baseline_comparator → red_flag_rules → minimal_sbar_draft → ◇nurse_10s_confirm → timeline_write → timeline_curator`
巡診前：`roster_agent → trend_analyzer×N → familiarization_writer×N → ◇head_nurse_edit_list → publish_round_pages → doctor_round → order_ingest → order_to_caregiver_notes + baseline_update_proposal → ◇nurse_confirm_baseline → baseline_write → timeline_write`

**硬規則**
- `timeline_write` 開頭：`assert payload.status == "approved" and payload.confirmed_by`，否則拋 `UnapprovedWriteError`。
- 所有 `◇` 節點用 `interrupt()`，前端以 `Command(resume={...})` 回覆。
- checkpointer：`PostgresSaver`，`thread_id = f"{patient_id}:{graph}:{date}"`；`saver.setup()` 只在 migration 執行。
- 超時：interrupt 前寫 `deadline` 進 state；背景 worker（APScheduler）掃逾期 thread，注入 `Command(resume={"action": "escalate"})`。
- 紅燈路徑不經 `sbar_draft`，直接 `notify_nurse_urgent`；對話不結束：照護者後續回答經 `POST /threads/{id}/caregiver-report` 以 `update_state` 寫回 interrupt 中的 thread（`caregiver_reports`、`caregiver_section`、`red_flags` 重算）。
- 所有 LLM 呼叫、追問決定（含 reason）、deep agent 派工與 subagent 工具呼叫都寫 trace（`core/trace.py`，`GET /trace`、`GET /debug/trace/{thread_id}`，`records/_trace/*.jsonl`）；ACCEPTANCE 需附實際 trace。
- RoundPage 由 `familiarization_writer` subagent 寫：①②③④ 的句子由模型依 timeline 與 baseline 生成（`get_round_context` → `submit_round_page`，程式只驗證規則），② 只列有變化的維度、每句附可點的「N 筆紀錄」連結（不露 obs id），沒變化寫「本期八維度皆與基線一致」，圖表只畫有變化的兩個維度，頁底 footer 寫由哪個 subagent 產生、呼叫了什麼幾次。
- 大檔（音檔、圖片、PDF）不進 state，只放物件儲存的 reference。
- Prompt caching：每次呼叫的訊息順序固定為「system prompt（不變）＋ 住民紀錄區塊 `core/llm.py::record_prefix`（profile＋基線＋近 14 天 timeline，一天內不變，併在同一則 system 裡：實測此模型只快取 system 內的前綴）→ 本輪狀態（唯一的 human）」；system 與紀錄區塊裡不放時間戳或每輪變動的內容。subagent 先 `get_round_context` 再算趨勢，讓 timeline 讀取固定在對話最前面。每次呼叫的 token 與估算成本寫 trace（`llm.usage`）。

---

## 5. deepagents：每位住民的專屬 agent

```python
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.middleware import FilesystemMiddleware

agent = create_deep_agent(
    model=settings.get_model(),                       # ChatOpenAI(model=MODEL_PINNED=gpt-5.6-luna, temperature=0, reasoning_effort="none")，見 .env.example
    backend=FilesystemBackend(root_dir=f"records/{patient_id}"),
    middleware=[FilesystemMiddleware(tools=["read_file", "ls", "glob", "grep"])],  # 唯讀
    subagents=[trend_analyzer, familiarization_writer, handoff_packager],
    interrupt_on={"render_document_page": {"allowed_decisions": ["approve", "edit", "reject"]}},
)
```
- agent 對 `timeline/` **只讀**；任何寫入走 §4 的 `timeline_write`。
- subagent 各自 context 隔離，只回結構化結果，總管不看它們的過程。
- `pyproject.toml` 鎖 `deepagents`、`langgraph`、`langchain` 精確版本（alpha 中，API 會變）。升級要開 PR 並跑全部測試。
- deepagents 採「信任模型」設計，邊界在工具層，不靠 prompt 自律。

**RoundPage 固定四段**（`familiarization_writer` 輸出）
① 這是誰 + 基線 ② 自上次巡診變了什麼（異常優先，趨勢圖，每行連回 timeline）③ 上次醫囑做了沒、有效嗎 ④ 請醫師確認的事（提問式）。一頁上限。

---

## 6. 紅燈規則（`red_flags/rules.py`）

純程式。每條規則物件含 `id, description, condition(), action, requires_validation=True`。初版（全部標「需護理師／醫師驗證，非診斷，非檢傷分級」）：
- 意識改變、新發生混亂或嗜睡 → 立即通知
- 體溫 ≥38.5°C 或 <35°C → 立即通知
- 呼吸 <8 或 ≥25／分；SpO₂ <92% 或較基線降 ≥3% → 立即通知
- 收縮壓 <90 或 >220；心率 <40 或 >130 → 立即通知
- 跌倒且頭部撞擊或使用抗凝血劑 → 立即通知
- 發燒＋心跳快＋意識改變同時出現 → 立即通知
- 進食量驟降、24h 未排尿 → 記錄觀察（不立即）

輸出只呈現「觀察到的事實 + 建議聯絡護理師」，**不輸出等級或分數**。每條規則有單元測試（命中／未命中／邊界值）。

---

## 7. UI：OMNI-TWIN 殼 × 臨床安全核心（2026-09-05 起）

**規格以 `docs/UIUX_OMNI_TWIN.md` 為準**（殼可以科幻，鏈不能）：深色預設（§6 tokens：`--bg #0B0F14`、`--surface #121822`、`--accent #35E0C8`、`--accent-2 #A78BFA`…），白色主題 `[data-theme="white"]` 保留給 RoundPage、事件資訊包列印版與醫師頁切換；發光只給 01 熱點與同步燈；動畫只有四種且 `prefers-reduced-motion` 全關；紅燈橫幅不可關閉。下面的白色 tokens 是 `[data-theme="white"]` 的內容，仍是列印版的唯一來源。

**白色主題 Tokens（`[data-theme="white"]`；覆寫 ui-ux-pro-max 的 design.md）**
```
--bg: #FFFFFF        --surface: #F7F9FC     --line: #E3E8EF
--ink: #0F1B2D       --ink-2: #5B6B7F
--primary: #1F6FEB   --ok: #1FA971          --warn: #D98A00   --danger: #D64545
--ai-fill: #EAF2FF   (AI 草稿底色，配虛線框)
字體：中文 Noto Sans TC；拉丁與數字 Inter；等寬 JetBrains Mono
間距：8pt grid；卡片圓角 12px；陰影 0 1px 2px rgba(15,27,45,.06)
```
**資訊架構（2026-09-05 改版）**：`/` 選角色（cookie）→ 角色首頁 → 病人頁 `/p/{id}?tab=`。病人頁是唯一入口：`who` 這是誰（profile＋基線＋有變化的維度）、`timeline` 紀錄（含對話每一輪與 Agent 活動，可依維度篩選）、`docs` 文件（護理師：等我確認的 Path A 審核／10 秒確認 → RoundPage 展開＋列印 A4 → 事故檔 → 注意事項；醫師：RoundPage；照護者：注意事項）、`talk` 對話（照護者；護理師可看）。預設 tab：照護者 talk；護理師有紅燈／草稿 → docs、否則 timeline；醫師 docs。頂欄只有「角色 · 住民姓名」。護理師每一頁都壓在紅燈橫幅之下（含「照護者目前回報」）。每則 agent 回覆下有 Agent 活動列：收合「花了 2.3 秒，4 步」，展開列出每個節點／LLM／subagent 呼叫與摘要（＝/debug/trace 內容）；照護者看白話、護理師／醫師看正式；紅燈那一步紅色。

**三個角色**
- 照護者手機：LINE 式聊天引導（氣泡＋底部輸入列：麥克風＋文字），最少文字；先講一句，之後每一題都由 intake_agent（LLM）決定：每輪把「八維度目前狀態、profile、baseline、已問過的題、事件／紅燈事實、剩餘預算」交給模型，模型回傳問什麼、怎麼問與 reason（存 trace）。沒有寫死的問題清單與順序、沒有快速回覆按鈕，只有語音與文字輸入；追問到八維度足夠，上限 4 題（紅燈分岔 6 題）；已提到的維度原則上不再問，只有該維度仍有缺口（子欄位未填、或原話裡有尚未抽到的線索）時可追問一次，planner 的 reason／gap 必須指出缺口，驗證通過才放行。模型連續兩次給無效決定 → 視為 ask=false，出「我理解的是…」摘要卡讓照護者確認或補充，對話繼續開著。禁止靜默 fallback：只有 LLM 真的掛掉（沒有 key 或呼叫失敗）才回 503，照護者端顯示「系統暫時無法回覆，請直接告訴護理師」並停止，不准退回規則版。紅燈不結束對話、只分岔：程式立即通知護理師，對話由 intake_agent 接手問規則必問題（怎麼跌、哪裡痛、能不能站、清不清醒、有沒有流血），答案即時寫進 caregiver_section、護理師端同步「照護者目前回報」；照護者端只顯示「已通知護理師，請留在他身邊」，規則說明只給護理師看。非紅燈結束出「我理解的是這樣」摘要卡（照護者口吻）。390px 手機優先，按鈕 ≥56px。（demo 只用 zh-TW；多語為第二階段）
- 護理師平板／桌面：紅燈橫幅置頂（全站）→ 等我確認（住民、S、A；確認／修改／退回）→ 今日總覽（異常優先＋趨勢小圖）；ISBAR 編輯器中 AI 欄位用虛線框＋「AI 草稿，請確認」；A/R 欄空白待填；確認鍵 ≥56px。
- 醫師唯讀：巡診名單一列一人 →「看一頁」→ 病人頁 docs tab 的 RoundPage，可列印 A4（print CSS 只印那一張）。

**無障礙**：正文對比 ≥4.5:1；tap target ≥44px（照護者 ≥56px）；夜班深色變體 `#0F1B2D`，紅燈維持高對比。
**AI 與人的樣式必須不同**：AI 草稿＝虛線＋淡藍；人確認＝實線＋綠勾。
**禁止**：通用 AI 漸層、紫色光暈、neon、玻璃擬態、emoji 當臨床狀態、深色為預設。

---

## 8. 程式慣例
- Python 3.12、uv、ruff（line-length 100）、pytest；型別完整，Pydantic v2。
- TypeScript strict、pnpm、Next.js App Router、Tailwind + shadcn/ui；不用 localStorage 存任何紀錄。
- packages/schema 是唯一型別來源；改 schema 要同時跑 `make codegen`。
- 命名：graph 節點函式名 = mermaid 節點名；agent 檔名 = agent 名。
- 每個 PR：說明改了哪個節點／哪個閘門、跑過哪些測試、UI 稽核結果。

---

## 9. 測試與評測
- 單元：`red_flags/`（每條規則三案例）、`record/`（provenance 不可缺、`timeline_write` 拒絕未核准）。
- 圖測：Path A 走完全程含一次退回、一次超時升級；Path B 每班流程與巡診流程各一次。
- 評測：`apps/api/eval/run.py` 對 30–50 條合成照護者語句（zh-TW，含模糊與誘導句；多語語句集為第二階段）算 hallucination rate、omission rate、provenance 正確率；CI 跑，結果寫進 README。

---

## 10. 安全
- 不 commit secrets；`.env.example` 列所有變數；pre-commit 掃 secrets。
- 只用合成資料；`data/seed/` 的姓名為代號。
- 呼叫 LLM 前經 `deidentify()` 去識別化；provenance 保留原文在本地。

---

## 11. Claude Code 不可做
- 不得在 `timeline_write` 以外寫 timeline。
- 不得讓 AI 產出 A/R 的診斷或處置語言。
- 不得移除、改寫 provenance。
- 不得未經 `◇nurse_confirm_baseline` 改 baseline。
- 不得改 mermaid 節點名而不同步改程式（反之亦然）。
- 不得讓 ui-ux-pro-max 自選風格覆蓋 §7 tokens。
- 不得在紅燈規則裡呼叫 LLM。

---

## 12. Demo 完成定義
- `make seed` 後 3 住民 × 14 天資料存在，其中 1 位第 12 天有急症。
- Path A：照護者說一句 → 紅燈或草稿 → 護理師審核（含一次退回）→ 定稿 → 路徑選擇 → 事故檔 → 家屬通知。
- Path B：每班確認 → 巡診前名單 → RoundPage 三人各一頁 → 列印 A4 正常 → 醫囑 → 照服員三件事（中文版）。
- **Demo 語言只用 zh-TW。** 介面沒有語言切換與翻譯步驟；`lang` 與 provenance 的 `language_original` 欄位保留、預設 `"zh-TW"`；多語（id／vi）為第二階段。
- 影片腳本（docs/VIDEO.md）：開場一個人的名字與一份紀錄 10 秒 → Path B 每班 20 秒 → Path A 急症 40 秒 → RoundPage 30 秒 → 拉遠看七條通道 15 秒 → 收尾句 5 秒。
- README 含：一句話定位、問題與制度出處（頁碼）、架構圖（兩張 mermaid）、快速開始、資料模型與 provenance、紅燈規則聲明（非診斷）、評測結果、限制與 mock 清單、LICENSE（Apache-2.0）。

---

## 13. 四人分工（依序，前兩項先行）
1. **schema + seed + docker-compose + record 寫入層**（含 `timeline_write` 守門）
2. **Path B 圖 + PostgresSaver + interrupt + 超時 worker**
3. **deepagents 個人 agent + 三個 subagent + RoundPage + print CSS**
4. **照護者手機介面（語音）+ 護理師 10 秒確認 + ISBAR 編輯器**
5. 合流：Path A + LINE 通知 + eval + README + 影片

---

## 14. 決策紀錄
所有架構決定寫進 `docs/DECISIONS.md`，格式：日期｜決定｜理由｜誰。改變核心原則（§1）需全隊同意。
