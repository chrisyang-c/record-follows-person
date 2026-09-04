# ARCHITECTURE — 一份能跟著人走的紀錄

> 每個人有一份跟著他走的紀錄，和一個替這份紀錄說話的 agent。今天，它先學會聽照顧他的人說話。

本文件是唯一的系統設計稿。維度定義以 `CLAUDE.md §3` 為準；LangGraph 節點名稱以 `docs/langgraph_path_a_incident.mermaid`、`docs/langgraph_path_b_routine_round.mermaid` 為準。

---

## 0. 層級

```
病人（一個人）
 └── 他的紀錄（Person Record）              ← 系統的核心資產
      ├── 從很多地方進來                     ← 輸入通道（照護者／護理師只是其中一條）
      └── 由他的專屬 Agent 替他說話          ← 對很多人說（醫師、護理師、照護者、家屬、急診、他自己）
```

照護者與護理師那條路徑，在這個架構裡是**通道 1**，是第一個接上的資料來源，也是 demo 要做的。但產品不是那條路徑，產品是這個人的紀錄和替他說話的 agent。

### 三個設計決定

**決定一：紀錄是主體，agent 是紀錄的手腳。**
所有 agent 都只做兩件事：把東西寫進紀錄，或把紀錄裡的東西講給某個人聽。沒有 agent 擁有自己的狀態，狀態全在紀錄裡。這樣換模型、換 agent、換場域，紀錄不動。

**決定二：照護者的話和護理師的判斷永遠分開存。**
一份事件檔有兩個區塊：照護者區塊（原話＋AI 結構化，不改口吻）、護理師區塊（現場評估＋ISBAR）。ISBAR 的作者是護理師，AI 只預填。先有護理師的現場評估，才有摘要；AI 草稿在審核前不算存在。

**決定三：每一行都有來源標記。**
`source: caregiver_said | ai_extracted | nurse_assessed | nurse_confirmed | doctor_ordered | system_derived`。醫師看到的每一句話都知道是誰說的、誰確認的。這是「醫師採信」的技術基礎，也是責任邊界。

---

## 1. 中心：Person Record

它不是「機構的紀錄系統」，是**這個人的**。機構、醫院、家屬都只是往裡面寫、從裡面讀。

```
PersonRecord（一人一份，跟著人走）
├── profile      誰：慢性病、過敏、DNR、聯絡人、特約醫療機構、目前所在（機構／家／醫院）
├── baseline     他的「平常」：八個觀察維度的常態，只在專業人員確認時更新
├── timeline     發生過什麼：只增不改，每筆帶來源
├── documents    替他產出的頁：對誰說、什麼時候說、從哪些 timeline 生成
└── provenance   每一行誰說的、誰確認的、原語言
```

八個維度貫穿所有來源：進食與飲水｜排泄｜活動與日常功能｜意識認知情緒溝通｜睡眠｜皮膚與傷口｜疼痛｜生命徵象與呼吸症狀（定義以 CLAUDE.md §3 為準，另有跨維度旗標「跟平常不一樣」與事件快捷：跌倒、用藥問題、嗆咳、行為）。任何來源進來都要落到這八格，才能互相比對。

---

### 1.1 對話串（conversation）與 timeline 的關係

每位住民一條持續的對話（`records/{pid}/conversation.jsonl`），每一輪（照護者原話 `caregiver_said`、agent 的追問／摘要 `ai_extracted`、系統事件 `system_derived`）在寫入時同時寫一行 provenance，並在病人頁「紀錄」tab 與 timeline 一起顯示。**但它不是 timeline**：CLAUDE.md §1.2／§4／§11 規定 timeline 只能經 `timeline_write` 寫入 `status="approved"` 且有 `confirmed_by` 的內容，所以對話串放在 timeline 旁邊、以 provenance 連結，護理師確認後才由 Path A／B 的 `timeline_write` 產生正式的 Observation／Incident。Agent 活動列（每輪的節點／LLM／subagent 事件）存在 agent 訊息的 `meta.activity`，同一份內容也是 `GET /debug/trace/{thread_id}` 的來源。

## 2. 輸入通道：他的紀錄從哪裡來

| 通道 | 來源 | 進來的形式 | 誰確認 | 狀態 |
|---|---|---|---|---|
| 1 | 照服員每班觀察 | 口語一句，任何語言 | 護理師 | **demo 真做** |
| 1 | 護理師現場評估與 ISBAR | 結構化欄位＋文字 | 護理師本人 | **demo 真做** |
| 2 | 醫師醫囑（巡診／門診） | 護理師輸入或拍照 | 護理師 | demo 真做（輸入端簡化） |
| 3 | 出院摘要 | PDF／照片 | 護理師 | demo 用假資料示意 |
| 4 | 生命徵象量測 | 血壓計、血糖機、體重 | 自動，異常時護理師看 | demo 寫死 |
| 5 | 家屬觀察與補充 | 口語或文字 | 護理師（僅供參考標記） | 第二階段 |
| 6 | 健保雲端藥歷／健康存摺 | 授權匯入 | 系統 | 第二階段 |
| 7 | 感測器（離床、跌倒偵測） | 事件流 | 自動 | 第三階段 |

每條通道各有一個 **Ingest 子 agent**，工作只有一個：把來源的格式翻成八維度＋provenance，寫進 timeline。它們不判斷、不寫文章。所有 agent／LLM 呼叫都留 trace（`core/trace.py`）。

---

## 3. 中樞：這個人的專屬 Agent

一個人一個 agent 實例，狀態全在他的 PersonRecord 裡。它做四件事，對象不同：

**它記得（Curate）**
Timeline Curator 整理、Baseline Comparator 比對、Trend Analyzer 找變化。這是它的「記憶整理」，背景跑，沒有人看。

**它判斷要不要叫人（Triage）**
規則層紅燈直接叫護理師；其他分 urgent／routine。它只建議，人決定，決定寫回紀錄。

**它替他說話（Speak）——同一份紀錄，對不同人講不同版本**

| 對誰 | 它說什麼 | 文件 |
|---|---|---|
| 巡診醫師 | 「這是誰、這個月變了什麼、你上次說的做了怎樣、請確認什麼」 | RoundPage 熟悉頁 |
| 急診醫師 | 「發生什麼、他平常怎樣、吃什麼藥、DNR、找誰」 | HandoffPage 後送頁 |
| 門診醫師 | 「這次來看什麼、相關近況、用藥」 | VisitPage 陪診頁 |
| 護理師 | ISBAR 預填、紅燈推播、baseline 更新提案 | 護理師工作面 |
| 照服員 | 「這個月要注意的三件事」，他的語言 | 注意事項卡 |
| 家屬 | 白話版事件與月報 | 家屬通知 |
| 病人本人（有能力時） | 「你最近怎麼樣、醫師說了什麼」 | 第二階段 |

**它替他跟著走（Carry）**
場域變了（機構→急診→病房→回機構→另一家機構），紀錄不換，只是輸入通道和說話對象換。Handoff Packager 負責在每次轉場時打包該場域需要的切片。

---

## 4. Agent 層：一個總管、九個子 agent

**總管 Orchestrator**
只做路由：收到輸入 → 判斷屬於哪條路徑 → 派給子 agent → 在人工節點 interrupt。不生成內容。

**輸入端**
1. **Intake Agent（對話式引導）**
   輸入：照護者語音／文字／圖片，任何語言。
   做：轉文字、拆成八維度；每一題都由 LLM 依「八維度目前狀態、profile、基線、已問過的題、事件／紅燈事實、預算」決定問什麼、怎麼問並附 reason（進 trace）；沒有寫死的題目清單、沒有快速回覆；追問到八維度足夠，上限 4 題；已提到的維度不再問；沒有模型或呼叫失敗就報錯停止，不退回規則。紅燈不結束對話、只分岔：程式先通知護理師，agent 接著問跌倒等關鍵資訊，答案即時同步到護理師端。非紅燈結束時出「我理解的是這樣」摘要卡（照護者口吻）。state 記 `asked_dimensions`、`turn_count`。（demo 語言 zh-TW；翻譯／多語為第二階段）
   出：`StructuredObservation`，保留原話 `raw_text` 與 `language`。
   規則：不改照護者的口吻，不加判斷。

2. **Baseline Comparator（可先用規則，不一定 LLM）**
   輸入：新觀察 ＋ baseline。
   出：每維度的 delta（方向、幅度、持續天數）。
   例：進食 base 100% → 今 50%，持續 3 天。

3. **Triage Agent（規則優先，LLM 補位）**
   規則層：紅燈關鍵字與硬條件（意識改變、胸痛、呼吸困難、跌倒後無法起身、體溫門檻）→ 直接推播護理師，跳過一切草稿。
   LLM 層：非紅燈時判 `urgent（需看醫師）` / `routine（日常）`。
   出：`TriageResult{level, reasons, evidence_refs}`。
   Triage 只建議，護理師決定；護理師的決定覆寫並記錄。

**寫作端**
4. **Caregiver Section Writer**
   把 Intake 的結果排成「照護者區塊」：原話、結構化八格、影像摘要、AI 追問與回答、未知欄位。口吻是照護者的，不是醫療的。

5. **Nurse Assist Agent（ISBAR 預填）**
   輸入：照護者區塊 ＋ timeline 近期 ＋ baseline。
   出：ISBAR 草稿。I 身分、S 現況（引用照護者區塊）、B 背景（profile＋baseline）、A 只寫「觀察到的變化」，R 只寫「請確認事項」。
   護理師在此節點 interrupt：加現場評估（生命徵象、意識、傷口），改寫 A 與 R，按確認。確認後 ISBAR 的 author = nurse。

6. **Incident Compiler**
   把照護者區塊 ＋ 護理師區塊 ＋ Triage ＋ 分流決定 ＋ 通知紀錄（家屬、特約醫療機構、119）合成一份 `IncidentFile`，寫回 timeline。這就是你說的「單次事故完整資料檔」。

**彙整端（把散的變成總覽）**
7. **Timeline Curator（子 agent，背景跑）**
   去重、正規化單位、把同一件事的多筆觀察串成一條、標記與哪個 Incident/Order 相關。不生成文字，只整理結構。

8. **Trend Analyzer（子 agent）**
   對八維度算窗口趨勢（7 天、30 天、自上次巡診起），標出「跨維度同時變化」（例如進食＋睡眠＋活動同時下降），這是最值得醫師看的訊號。輸出是結構化的，不是文章。

9. **Familiarization Writer（「讓醫師熟悉這個人」）**
   輸入：profile、baseline、Trend Analyzer 結果、上次 Encounter 的醫囑與執行情形、期間所有 Incident。
   出：`RoundPage`，固定四段：
   ① 這是誰（一句話的人＋基線）
   ② 自上次巡診以來變了什麼（異常優先，附趨勢圖，每條指回 timeline）
   ③ 上次醫囑做了沒、有效嗎
   ④ 請醫師確認的事（提問式）
   一頁上限。護理長可增刪，不需醫師輸入。①②③④ 的句子由這個 subagent（模型）依 timeline 與 baseline 寫（工具：analyze_trends、get_round_context、submit_round_page；程式只驗證「② 只寫有變化的維度」「④ 只提問」等規則），每句附可點的「N 筆紀錄」連結，圖表只畫有變化的兩個維度，頁底寫由誰產生、呼叫了什麼幾次。

**周邊**
- **Roster Agent**：巡診前掃全部住民的 Trend，排出「這個月該看誰」名單與排序。
- **Order Ingest Agent**：醫囑 → 照護者本月注意事項（多語）＋ baseline 更新提案（護理師確認後生效）。
- **Handoff Packager**：後送頁／陪診頁，從同一份紀錄取不同切片。
- **Translation**：雙向，照護者語言 ↔ 中文，附在 provenance。

---

## 5. 路徑 A：急症（需看醫師，不到 119）

```
START
 → load PersonRecord
 → Intake Agent（對話式，多輪追問，上限 4 題）
 → Baseline Comparator
 → Triage Agent
     ├─ 紅燈 → 推播護理師（程式）→ Intake 繼續問規則必問題，答案即時進 caregiver_section → 護理師到場 → 後送 or 119 → Handoff Packager → END（緊急）
     └─ urgent → 續
 → Caregiver Section Writer → 照護者區塊定稿（照護者看一眼「是這個意思」）
 → 推播當班護理師
 → [interrupt] 護理師：現場評估 + 改 ISBAR 草稿 + 確認
       超時未回 → 升級：通知第二護理師／護理長
 → 護理師決定路徑：
     ├─ 聯絡特約醫療機構／在宅急症模式 B → Handoff Packager 產通話版 ISBAR
     ├─ 安排陪同就醫 → VisitPage
     └─ 轉為觀察 → 進路徑 B 的 timeline
 → Incident Compiler → IncidentFile 寫入 timeline
 → 家屬通知（白話版，護理師確認後發）
 → 追蹤：Intake 於指定時間再問一次照護者 → 更新 IncidentFile.follow_up
 → END
```

與你圖上的差異：
- 原本 5（臨床摘要）在 6（人工審核）之前；現在**護理師的現場評估是 ISBAR 的一部分**，所以審核在前、摘要是審核的產物。
- 「家屬易懂轉譯」保留，但發送前經護理師確認。
- 「醫師／護理師 Web」拆開：機構場景裡護理師在現場、醫師在外面，兩個介面不同。

---

## 6. 路徑 B：日常 → 本地歷史 → 巡診

```
每班：
 Intake → Baseline Comparator → Triage（routine）
 → Nurse Assist 產極簡 SBAR（一行 S、一行 A）
 → [interrupt] 護理師十秒確認（接受／改一句）
 → 寫入 timeline.Observation
 → Timeline Curator 背景整理

巡診前 1–2 天：
 Roster Agent 掃全院 → 名單
 → Trend Analyzer（每位住民）
 → Familiarization Writer → RoundPage
 → [interrupt] 護理長增刪名單、掃一眼每頁
 → 醫師端：名單 + RoundPage（只讀）

巡診當天：
 醫師看頁、看人、開醫囑（在他自己的系統或口頭）
 → 護理師輸入醫囑 → Order Ingest Agent
 → 照護者注意事項（多語）推給該住民的照護者
 → baseline 更新提案 → 護理師確認 → 生效
 → Encounter 寫入 timeline
 → 下個月，Familiarization Writer 的第③段會回頭看這些醫囑有沒有效
```

「讓醫師熟悉這個病人」的關鍵不是資料多，是**三段對照**：平常怎樣（baseline）→ 這個月怎樣（trend）→ 上次你說的做了怎樣（order follow-up）。醫師看完這三段，就像他上個月也在。

---

## 7. Global State（LangGraph）

```json
{
  "person_id": "…",
  "path": "incident | routine | round",
  "person_record_ref": "…",
  "raw_input": { "text": "…", "language": "id", "media": [] },
  "structured_observation": { "domains": { "intake": {...}, "sleep": {...}, "...": {} }, "unknown": [], "raw_text": "…" },
  "asked_dimensions": ["sleep", "pain"], "turn_count": 2,
  "baseline_delta": [ { "domain": "intake", "direction": "down", "magnitude": 0.5, "days": 3 } ],
  "triage": { "level": "red | urgent | routine", "reasons": [], "evidence_refs": [], "decided_by": "rule | llm | nurse" },
  "caregiver_section": { "…": "…" },
  "nurse_section": { "onsite_assessment": {}, "isbar": {}, "confirmed_by": "", "confirmed_at": "" },
  "route_decision": "contact_contract_hospital | accompany_visit | observe | escalate_119",
  "notifications": [ { "to": "family | hospital | 119", "sent_at": "", "content_ref": "" } ],
  "documents": { "incident_file": "", "round_page": "", "handoff_page": "" },
  "provenance": [ { "line_id": "", "source": "", "author": "", "confirmed_by": "", "ts": "" } ],
  "status": "…", "updated_at": ""
}
```

Checkpointer 用 PostgreSQL，interrupt 節點：護理師確認（A、B 都有）、護理長名單、baseline 更新。這三個是「人決定」的點，其餘都能自動跑。

---

## 8. Demo 範圍：真做 vs 假做

| 真做 | 假做／寫死 |
|---|---|
| Intake（語音→結構化，多輪追問上限 4 題） | 影像分析（用固定摘要） |
| Baseline Comparator（規則） | Timeline Curator（demo 資料先整理好） |
| Triage 規則層＋紅燈推播 | 119／特約醫療機構通知（畫面提示即可） |
| Nurse Assist ISBAR 預填＋護理師確認畫面 | 超時升級（旁白帶過） |
| Incident Compiler → 一份兩區塊的事故檔 | 家屬通知（顯示文字不真發） |
| Familiarization Writer → 一頁 RoundPage | Roster 排序（demo 用 3 位住民） |
| Order Ingest → 注意事項（多語） | baseline 更新（顯示提案即可） |

Demo 資料：3 位住民、各 14 天觀察、其中 1 位有一次急症。這樣路徑 A 和 B 都演得到，RoundPage 也有趨勢可看。

---

## 9. Demo 怎麼呈現這個層級

影片結構建議：
1. 開場 10 秒：一個人的名字，一份紀錄，「這份紀錄跟著他」。
2. 通道 1 進來：照服員講一句 → 八維度亮起來 → 護理師確認。
3. 急症一次：紅燈 → 護理師 → 兩區塊事故檔 → 後送頁。
4. 一個月後：Agent 替他對巡診醫師說話 → 熟悉頁。
5. 收尾：畫面拉遠，通道 2–7 以灰色示意接在同一份紀錄旁，「今天接了一條，這份紀錄會一直長」。

這樣評審看到的是「一個人的紀錄和替他說話的 agent」，照護者流程是它第一次開口的樣子。

---

### 9.1 畫面資訊架構（2026-09-05）

`/` 選角色（cookie）→ 角色首頁（照護者：住民卡；護理師：紅燈橫幅 → 等我確認 → 今日總覽 ＋ 巡診準備；醫師：巡診名單）→ 病人頁 `/p/{id}?tab=who|timeline|docs|talk`。病人頁是這份紀錄的唯一入口；`talk` 是 `graphs/talk.py`（每句一個小 LangGraph：load_person_record → record_caregiver_message → intake_agent → baseline_comparator → red_flag_rules → notify_nurse → decide_next → reply），節點以 `get_stream_writer()` 發自訂事件，API 以 SSE（`POST /patients/{id}/talk`）轉給畫面：活動事件 → 逐字回覆 → done。紅燈時 `notify_nurse` 直接 `runner.start("path_a")`／`update_caregiver`，對話不中斷。巡診 `POST /round/start/stream` 同樣串流 roster_agent → trend_analyzer → familiarization_writer 的每一步。

## 10. 評審會問的三題

**「這跟一個 workflow 差在哪？」**
它記得這個人（baseline＋timeline），跟著這個人跨場域（同一份紀錄產不同頁），知道現在該對誰說什麼（照護者聽注意事項、護理師看 ISBAR 草稿、醫師看熟悉頁）。三件事都靠 PersonRecord，不靠流程圖。

**「AI 寫錯誰負責？」**
provenance 每行有來源。AI 的行永遠標 `ai_extracted`，只有護理師確認過的行才會出現在給醫師的頁面。ISBAR 的作者是護理師。

**「為什麼 A 不寫評估？」**
因為寫評估的是護理師，不是 AI。AI 的 A 只寫「和基線比的變化」，護理師加現場評估後才是完整的 A。這條線在程式裡是兩個欄位，不是一個。

---

## 11. 還沒想清楚的（要決定）

- 照護者「看一眼是不是這個意思」要不要做成必要步驟？加了更準，少了更快。建議：紅燈不做，其他做。
- baseline 多久滾動一次？建議：只在醫囑或護理師確認時更新，不自動漂移，否則「平常」會被慢慢惡化帶走。
- Familiarization Writer 一頁放不放趨勢圖？建議放一張，八維度選變化最大的兩個。
- 路徑 A 的追蹤要問幾次？建議一次，指定時間由護理師設。
