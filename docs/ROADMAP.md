# ROADMAP — 從照護迴圈到健康資料平台

> **這份文件管「之後要做什麼、依什麼順序」。**
> 長期願景在 [`VISION_personal_health_twin.md`](VISION_personal_health_twin.md)；
> 已採納的架構在 [`ARCHITECTURE.md`](ARCHITECTURE.md)；
> 目前進度與下一步在 [`HANDOFF.md`](HANDOFF.md)。

---

## 0. 先講一件會影響全部排序的事

拿 `VISION_personal_health_twin.md`（36,000 字）當規格算完成度，會得到一個
**數學上正確、決策上有害**的數字：每個方向都同樣「沒做完」，所以挑哪個都對，也都不對。

VISION 描述的是需要多人多年、要跟醫院簽資料協議、要過 SaMD 認定的東西。
CLAUDE.md §0.2 已經寫明：**實作範圍以 ARCHITECTURE.md 與 HANDOFF.md 為準**，VISION 是願景。

所以這份 ROADMAP 的分母不是 VISION，是：

> **一個居家護理師連續用一週之後，願不願意繼續用。**

這個分母有出口、可驗證，而且會自動告訴你哪些平台層是必要的（大部分不是）。

---

## 1. 已經在的東西（不要重做）

Path A 急症與 Path B 日常兩條流程走完，含退回與超時升級；照護者對話（模型決定每一題、
缺口驗證、摘要卡）；Health ID、Care Circle、access log、以病人為核心的登入；
本人 App（人體圖、終身時間軸、問我的紀錄）；模擬跌倒訊號、硬條件紅燈、四鍵驗證、
事件資訊包；個人生理值正常帶與 RF13；OMNI-TWIN 深色殼、列印白底。

**api 133 個測試、ruff 乾淨、評測 46 句：provenance 100%、無診斷詞 100%、hallucination 6.5%。**

---

## 2. 排序原則

**每個 Epic 結束時，demo 必須仍然能跑，而且要多一件看得見的事。**

這條原則排除了「由下往上重建平台」的順序（Identity → Consent → Canonical → FHIR →
Ingestion → Storage → …）。那個順序前六個 Epic 全是平台層，做完之前畫面一個字都不會變；
而 Canonical／Storage／FHIR 每一個都要動 `record/store.py`，在 Storage 完成之前會同時
存在 `records/{id}/*.json` 與資料庫兩個真相來源 —— 那段期間任何一次 demo 都可能是壞的。

---

## 3. Epic 排序

### E1　真正驗證產品命題　⭐ 最高優先

整個專案的論點是「照服員講一句話 → 護理師省下寫紀錄的時間」。
現在的證據是 46 句**自己寫的**合成語句 —— 那證明抽取穩定，不證明護理師願意用。

| | |
|---|---|
| 做什麼 | 找 1–3 位居家護理師或機構護理師，用現有系統連續操作一週 |
| 新增 | `docs/FIELD_NOTES.md`：每次使用的實際語句、卡住的地方、放棄的地方 |
| 不寫程式 | 這個 Epic 的產出是**證據**，不是功能 |
| Done | 有一份真人使用紀錄；`KNOWN_ISSUES` 多出至少 5 條來自真實使用的問題 |

**為什麼排第一**：後面每一個 Epic 的優先序都會被這一週的結果重排。沒有它，
下面的排序全是推測。

---

### E2　Retrieval：「問我的紀錄」真的能回答

| | |
|---|---|
| 現況 | KNOWN_ISSUES #29：關鍵字 bigram，「心臟開刀」找不到「心臟手術」 |
| 新增目錄 | `apps/api/retrieval/`（embed.py、index.py、search.py） |
| schema | `RetrievalChunk`（chunk_id、health_id、text、source_ref、embedding_ref、ts） |
| endpoint | 沿用 `POST /me/{id}/ask`，內部換檢索；新增 `GET /debug/retrieval/{id}?q=` |
| 儲存 | `records/{id}/index/`（demo 規模用檔案；向量庫列在 E6） |
| jobs | timeline 寫入後重建該住民的索引（背景，非阻塞） |
| 前端 | 不變 |
| 測試 | 同義詞案例集（心臟開刀／心臟手術、血壓藥／降壓藥…）≥20 組；每個答案仍必須引用既有行 |
| Done | 同義詞測試 ≥90% 命中；**答案沒有來源時仍然說「紀錄裡沒有這件事」**，不得因為檢索變強而開始捏造 |

**為什麼排這裡**：最小、最獨立、不動 `store`，而且修的是 `/me` 的核心賣點。

---

### E3　Event Engine：從「跌倒」抽象化

| | |
|---|---|
| 現況 | `SensorEvent` 只描述跌倒；Path A 是為跌倒寫的 |
| 新增 | `packages/schema`：`HealthEvent`（type、source、detected_at、evidence、status、verification、assignments、escalation、resolution） |
| 遷移 | `SensorEvent` 成為 `HealthEvent` 的一個 `source="wearable"` 特例；`record/events.py` 改讀寫 `HealthEvent` |
| 狀態機 | `DETECTED → NOTIFIED → ACKNOWLEDGED → VERIFIED → UNDER_REVIEW → ESCALATED → RESOLVED → FOLLOW_UP` |
| 事件型別 | fall、hypoxia、abnormal_bp、fever、medication_miss、reduced_intake、confusion、wound、post_op_change、discharge |
| endpoint | `GET/POST /events`、`POST /events/{id}/verify`、`POST /events/{id}/assign` |
| 前端 | Clinical Queue 依 `event.type` 而非寫死跌倒 |
| 測試 | 每個狀態轉換的合法／非法各一；`test_sensor_fall.py` 改寫為 `HealthEvent` 版本後仍全過 |
| Done | 新增一種事件型別（例如發燒）**不需要改 Path A 的任何節點** |

**紅線**：`HealthEvent` **不得有 `confidence`／`severity`／`weight` 欄位**。
CLAUDE.md §1.8 禁止分數出現在照護者／護理師／醫師介面；把它放進資料模型，
早晚會漏到畫面上。感測原始值另存，只給護理師。
（概念參考：chenni416/Healthcare 的 `HealthEvent`；該專案無授權宣告，僅借用概念，
其 `confidence: float` 與 evidence `weight` 欄位**刻意不採用**。）

---

### E4　Consent／Policy Engine

| | |
|---|---|
| 現況 | KNOWN_ISSUES #35：`/role?set=` 可繞過密碼；scope 只有四種頁面級 |
| 先做 | `CareCircleMember.purpose`、`AccessLogEntry.purpose`（見 CONSOLIDATION §4）—— 小、獨立、補上 VISION 的 WHY |
| 再做 | 資源級 scope：從 `who/timeline/docs/talk` 細到 `meds/labs/imaging/events` |
| 再做 | 緊急開鎖：獨立憑證、TTL、不可抑制的通知、事後可申訴 |
| endpoint | `POST /patients/{id}/emergency-access`、`GET /patients/{id}/access-log?purpose=` |
| 測試 | 角色 × scope × purpose 的窮舉矩陣；每一格一個案例 |
| Done | 授權矩陣測試全綠；`/role?set=` 不再能繞過（session token 由 API 簽發） |

**為什麼 OIDC 不排這裡**：OIDC 解決「證明你是誰」，你們的差異化在「**誰能看我的紀錄**」——
那是 Consent，不是 Authentication。接 Keycloak 不會讓 Care Circle 變細粒度。
先把 Policy Engine 做對，登入層之後換掉不影響它（現在 cookie-only 的設計反而讓這件事很容易）。

---

### E5　Canonical Model ＋ Storage

| | |
|---|---|
| 為什麼排在這裡 | 前三個 Epic 已經把 domain 邊界磨清楚，現在遷移知道要遷什麼 |
| 做法 | **保持 `store` 的介面不動**，在後面塞一個 `PostgresBackend` → 雙寫 → 比對 → 切換 → 移除 filesystem backend |
| 不做法 | ~~「改成用 Postgres」~~ —— 這個差別決定遷移期間 demo 會不會壞 |
| tables | persons、external_identifiers、consents、relationships、encounters、conditions、medications、procedures、observations、events、workflows、audit |
| 測試 | 兩個 backend 跑同一組 `record/test_store.py`，結果必須相同 |
| Done | 切換 backend 只改一個環境變數；20 個測試檔全過 |

---

### E6　之後（順序視 E1 結果重排）

| Epic | 內容 | 前置 |
|---|---|---|
| E6 FHIR Adapter | Patient／Encounter／Condition／Observation／MedicationStatement／Procedure／DocumentReference／Provenance 的 import/export | E5 |
| E7 Device Platform | 真實穿戴裝置 connector、pairing、stream ingestion | E3、E5 |
| E8 Vector Store | E2 的檔案索引換成 pgvector／Qdrant | E2、E5 |
| E9 Identity／OIDC | session token 由 API 簽發、MFA、真正 IdP | E4 |
| E10 Observability | metrics、distributed trace、SLO、alerts | — |
| E11 Backup／DR | backup、restore、retention | E5 |
| E12 Deployment | staging／prod、IaC、secrets、rolling deploy | E5 |

---

## 4. 明確不做（第二階段以後）

這一節跟 Epic 清單一樣重要 —— **沒有「不做什麼」，就沒有進度。**

| 項目 | 出處 | 理由 |
|---|---|---|
| Health Graph 知識圖 | OVERVIEW §8 已列 | 每位住民約 10 個診斷、7 種用藥；這個規模用一張策展的對照表（藥 → 已知副作用 → 症狀）就做得到，不需要圖資料庫 |
| 多語（印尼語／越南語）介面 | CLAUDE.md §12 | Demo 只用 zh-TW；schema 的 `lang` 欄位保留 |
| 02 風格美學／03 心理情緒／04 全資產生命週期 | UIUX_OMNI_TWIN | 五維度 rail 只有 01 與 05 有內容 |
| 3D 人體模型 | KNOWN_ISSUES #36 | 現有向量解剖圖夠用 |
| 通道 5 家屬觀察、通道 6 健保雲端藥歷 | ARCHITECTURE §2 | 第二階段 |
| 影像分析、119／特約通知實發、LINE 實發 | ARCHITECTURE §8 | Demo 範圍內顯示不真發 |

---

## 5. ARCHITECTURE §11 的四個未決事項

這四個是**具體且到現在還開著**的決定，比 12 個 Epic 更該先處理：

| # | 問題 | 文件裡的建議 | 現況 |
|---|---|---|---|
| 1 | 照護者「看一眼是不是這個意思」要不要做成必要步驟？ | 紅燈不做，其他做 | 已實作摘要卡（非紅燈） ✅ |
| 2 | baseline 多久滾動一次？ | **只在醫囑或護理師確認時更新，不自動漂移** | 已遵守；`propose_vitals_usual` 因此被移除（commit `6c12cd2`） |
| 3 | Familiarization Writer 一頁放不放趨勢圖？ | 放一張，選變化最大的兩個維度 | 已實作 ✅ |
| 4 | 路徑 A 的追蹤要問幾次？ | 一次，指定時間由護理師設 | `schedule_follow_up` 已有，時間是否可由護理師設 —— **未確認** |

---

## 6. 為什麼不用「完成 40–45%」當排程基準

那個數字的分母是 VISION，而 VISION 的許多項目在 ARCHITECTURE 裡被明確標為
第二／第三階段或「假做」：

| 被算成「缺」的 | 文件裡的實際狀態 |
|---|---|
| Wearables「幾乎缺」、Home IoT「缺」 | ARCHITECTURE §2 通道 7：**第三階段** |
| 家屬觀察「部分」 | 通道 5：第二階段 |
| 健保雲端藥歷 | 通道 6：第二階段 |
| baseline 更新 | §8「假做」清單：顯示提案即可 |
| 超時升級 | §8「假做」清單：旁白帶過 |
| 影像分析、119 通知、LINE | §8「假做」清單 |

把設計上的階段界線算成完成度缺口，會得到一個看起來很慘、但其實是照計畫走的數字。
**沒有逐項驗收與權重依據的百分比，不拿來當排程基準。**
