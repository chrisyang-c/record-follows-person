> ## 這份文件的狀態：**待審提案，不是本專案的架構**
>
> | | |
> |---|---|
> | 來源 | 外部提案（D:\Health AI Bridge\docs\00-architecture.md），2026-09-05 收錄 |
> | 狀態 | **提案**。本專案的架構以 [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) 為準 |
> | 已採納 | 只有 §6 個人基準線（median／MAD／established 門檻）→ `apps/api/baseline/`，commit `c0a6802` |
> | 逐項取捨 | 見 [`docs/CONSOLIDATION.md`](../CONSOLIDATION.md) §3 |
>
> **它與本專案是兩條不同的路。** 斷言日誌、Zone 0–4 分區、CitationGate、GraphQL、
> Neo4j／TimescaleDB 都**沒有被採納**；本專案用 PersonRecord、Care Circle scope、
> provenance ＋ `timeline_write` 守門、REST、檔案系統 ＋ Postgres checkpointer。
>
> 讀這份文件時請記得：**它描述的不是這個 repo。** 保留它是為了日後逐項再議，
> 不是為了照著做。

---
# Personal Health Twin — 技術設計文件 v1

> 上游來源：`personal-health-twin.md`（產品架構，定義「是什麼」與「會長成什麼」）
> 本文件定義：**「用什麼做、怎麼切、哪些事情不准發生」**
> 範圍：PART A（§01–§17）九大元件的完整骨架。PART B 只保留擴充點，不實作。
> 狀態：待審。每個「選型」都可被逐項否決；每個「約束」不可被否決。

---

## 0｜這份文件怎麼讀

架構文件（母文件）用了 30 章講產品。這份文件把它壓成三個問題：

1. **哪些規則違反了就等於這個產品沒有存在意義？** → §1
2. **每條規則要靠什麼機制才不會在第 8 個月被繞過？** → §1 的機制欄 + §4–§11
3. **第一版要蓋到哪裡，蓋錯了怎麼退？** → §15

母文件裡最重要的一句話是 §13 的「**LLM 可替換。模型是零件不是地基。地基是 Graph、Baseline 與 Consent。**」
這份設計的每一個決定都是為了讓那句話在程式碼層面成立，而不只是投影片上成立。

---

## 1｜十條不可違反的約束

這不是價值宣言，是驗收條件。每一條都對應一個機制與一組會失敗的測試。

| # | 約束（出處） | 機制 | 驗收方式 |
|---|---|---|---|
| 1 | 寧可分開，不可錯合（§3.3） | `PersonCluster` 聚合 `SourceIdentity`，永不破壞性合併；合併/拆解皆可逆 | 合併後執行 unmerge，兩邊資料位元級還原 |
| 2 | 不猜、不合併、不隱藏（§06） | 衝突不解析成單值，回傳 `ConflictSet`；解析本身也是一筆帶來源的斷言 | 餵入三份矛盾用藥清單，API 必須回三筆 + 衝突旗標 |
| 3 | 沒有來源的句子不准輸出（§8.4） | `CitationGate`：AI 只能產出 `Claim{text, evidence[]}`，空 evidence 一律攔截 | 注入無來源 claim，gate 必須擋下並計數 |
| 4 | 最小揭露不做前端過濾（§15） | PEP 包在 repository 層；`TwinSession(access_context)` 是唯一入口，無 context 無法查詢 | 直打 GraphQL 要 Zone 4 欄位，回 `REDACTED` 而非資料 |
| 5 | AI 不診斷、不決定治療（§8.5） | Detection 不用 LLM；LLM 輸出型別中沒有 diagnosis / order 欄位 | 型別檢查 + 提示注入測試 |
| 6 | Twin 提議，人確認（§22.2） | 狀態機的每個對外動作都有 `requires_human_ack` 旗標，預設為真 | 狀態機窮舉測試：無人確認不得跨越審核節點 |
| 7 | 系統壞掉不能比沒系統更糟（§17） | 四級降級模式，每級有明確觸發、行為與 UI 狀態 | 故障演練：殺掉 Neo4j / LLM / 網路，通訊路徑仍在 |
| 8 | 本人意願高於系統建議（§27.09） | `Preference` 是查詢的一等公民；違反本人意願的建議一律標記並記錄 | 意願衝突測試：本人拒絕住院時，建議必須改寫並留痕 |
| 9 | 每一次存取都留痕（§9.5） | Hash 鏈稽核表，資料庫角色只有 INSERT 權限 | 嘗試 UPDATE/DELETE 稽核列必須被資料庫拒絕；鏈完整性檢查 |
| 10 | LLM 可替換（§13） | 所有模型呼叫走 `LLMProvider` port；臨床判斷不在 LLM 內 | 換掉 provider，Detection 與 Packet 的黃金樣本測試不得改變 |

**第 3、4、5 條是本設計與一般「醫療 AI App」的分界線。** 其他人做的是 prompt 加一句「請引用來源」；這裡做的是型別上不存在無來源的輸出。

---

## 2｜技術選型

### 2.1 §13 逐層對照

| §13 層 | 選型 | 為什麼 | 被否決的選項 |
|---|---|---|---|
| Experience | React 19 + TypeScript + Vite + TanStack Query + urql | 六個角色六種資訊密度，需要共用 design system 但獨立路由樹 | Next.js（SSR 對登入後的臨床介面沒有價值，反而多一層部署複雜度） |
| API（讀） | GraphQL — Strawberry（Python，code-first） | §12 六角色各看不同世界，§15 最小揭露必須在 schema 上宣告。欄位級 `@zone` 指令 + 單一授權中介層，勝過 N 套角色 REST | Graphene（維護較弱）、REST-only（授權邏輯會被複製六次） |
| API（寫） | REST / FastAPI | 寫入是命令（攝取、通報、授權），語意清楚，好稽核 | GraphQL mutation（把命令語意藏進 schema，不利授權與冪等） |
| Orchestration（照護） | Postgres 狀態機 + outbox + 計時器 worker | §10.3 升級計時器必須**持久、可檢視、可被人改**。人的節奏是分鐘到天 | Temporal（正確但太重，v1 不值得；列為規模化路徑） |
| Orchestration（AI） | LangGraph | §8.1 就是狀態機 + 工具呼叫 + 人工審核節點；LangGraph 的 interrupt/checkpoint 直接對應 | 自幹（會重造 checkpoint）、CrewAI（角色隱喻不適合確定性路由） |
| AI — LLM | **Claude `claude-opus-5`**（敘事/翻譯），`claude-sonnet-5`（追問、批次改寫） | 見 §2.2 | — |
| AI — 向量檢索 | pgvector（HNSW）在同一顆 Postgres | 單人語義索引量體小；重點是**檢索前就能用 SQL WHERE 做 zone 預過濾** | Qdrant/Weaviate（多一個服務，且跨庫做 zone 預過濾很痛） |
| AI — 規則引擎 | 純 Python 規則模組 + 宣告式 YAML 規則表 | 規則要能被護理師讀懂與否決，不能藏在程式碼裡 | Drools 類（JVM 依賴不划算） |
| AI — 時序異常 | 自寫 robust statistics（median/MAD/Theil–Sen）+ `statsmodels` | §7.3 的核心是**個人變異度**，現成套件的族群假設反而是錯的 | Prophet（趨勢模型過度擬合季節性，不適合個人生理） |
| Storage — 圖 | **Neo4j 5 Community** | §5.4 三種查詢（鄰居/路徑/子圖）是 Event Packet 的技術基礎。路徑查詢用 Cypher 是數量級的差距，且推理路徑要能被存成物件重播 | 見 §2.3 的取捨 |
| Storage — 時序 | **TimescaleDB**（Postgres 擴充） | 7d / 90d / 多年三個尺度直接對應 continuous aggregates；與關聯層同一顆引擎 | InfluxDB（又一個服務 + 又一種查詢語言） |
| Storage — 物件 | MinIO（S3 相容） | 本機與雲端同一組 API；原始訊息、影像、音檔 | 直接雲端 S3（本機開發與院內部署不通） |
| Storage — 關聯 | **PostgreSQL 17** | 身分、授權、稽核鏈、斷言日誌——全部需要 ACID | — |
| Streaming | **Postgres transactional outbox → relay → Redis Streams** | outbox 保證「不會為 rollback 掉的寫入發事件」；Redis Streams 給 consumer group 與重播 | 直接 Kafka（v1 過重）、只用 Redis（會發出不存在的寫入事件） |
| Interop | `fhir.resources`（Pydantic FHIR R4/R5）+ 自寫 HL7 v2 adapter | Pydantic 原生，與整個後端型別系統一致 | HAPI FHIR（JVM，只為了驗證不值得起一個服務） |
| Identity | OIDC（Keycloak）+ `did:key` / `did:web` + W3C VC | v1 用 OIDC 做真實登入，DID/VC 做授權憑證的簽發與驗證。兩者並行，見 §2.4 | 只做 OIDC（放棄 §3.2 的核心主張）、只做 DID（沒有可用的登入體驗） |
| 後端語言 | **Python 3.12** | AI 層、FHIR、術語對映、robust statistics、未來的環境感測訊號處理都在 Python 生態 | TypeScript 全端（前端省事，但整個臨床資料與統計層都要重造輪子） |

### 2.2 LLM 選型與定價

模型事實查於 2026-06-24 快取表：

| 模型 | Model ID | Context | 輸入 $/1M | 輸出 $/1M | 本系統用途 |
|---|---|---|---|---|---|
| Claude Opus 5 | `claude-opus-5` | 1M | $5.00 | $25.00 | Narrative Agent（SBAR / 敘事摘要 / 建議措辭） |
| Claude Sonnet 5 | `claude-sonnet-5` | 1M | $2.00 | $10.00 | Question Agent（追問缺漏）、Translation Agent（角色化改寫、多語） |
| Claude Haiku 4.5 | `claude-haiku-4-5` | 200K | $1.00 | $5.00 | 批次去識別化改寫、L3 敘事摘要的定期重生成（走 Batch API，半價） |

呼叫規範（寫進 `LLMProvider` 的 Anthropic adapter）：

- **結構化輸出**用 `output_config: {format: {...}}`。舊的 `output_format` 參數已棄用。
- **思考**用 `thinking: {type: "adaptive"}`。`budget_tokens` 在 Opus 5 / Sonnet 5 上會回 400，不得出現在程式碼中。
- **深度**用 `output_config: {effort: ...}`。Narrative Agent 用 `high`；Translation / Question 用 `low`。
- **不使用 assistant prefill**（Opus 5 / Sonnet 5 會回 400）。輸出格式一律靠 structured output 控制。
- **提示快取**：`tools → system → messages` 的順序決定前綴。把「臨床摘要規則 + 角色定義 + L2 基準線卡 + L3 敘事摘要」放在最前面並下 `cache_control`，把事件本身放在最後。驗證方式是看 `usage.cache_read_input_tokens` 不為零。

> **選 Claude 的理由不是偏好，是三件事**：繁體中文臨床語域的品質、對「不得捏造、缺項標未提供」這類負向指令的遵循度、以及 1M context 讓 L1 近期窗口不必激進裁切。但這仍然是 adapter 後面的一個字串——見約束 #10。

### 2.3 圖資料庫的取捨（需要你裁決）

| 方案 | 優點 | 代價 |
|---|---|---|
| **Neo4j 5 Community**（建議） | Cypher 路徑查詢成熟；`shortestPath`、變長路徑、子圖萃取都是一級公民 | GPLv3（純伺服器端使用不觸發散布義務，但院內部署要跟法務確認）；Community 版單一資料庫，跨人隔離只能靠 `person_id` 邏輯分區 |
| PostgreSQL + Apache AGE | 只有一顆引擎，維運成本最低；Apache-2 授權乾淨 | Cypher 支援不完整；複雜路徑查詢要退回 recursive CTE，可讀性與效能都差一截 |
| Memgraph | 記憶體內、快 | BSL 授權；社群小 |

**建議 Neo4j，理由**：圖是地基三件之一，而推理路徑（§8.4 的 `[圖路徑 #4471]`）必須是可儲存、可重播、可被醫師否決的物件。在這一格用比較弱的工具，直接折損產品的核心主張。
**但**——若「只養一顆資料庫」是硬需求，AGE 是可接受的降級，代價寫在上表。這一格請你裁決。

### 2.4 身分：DID 與 OIDC 並行

母文件 §3.2 主張 DID + VC，理由是「授權不需要中央伺服器同意」。這是對的，但 v1 直接全上 DID 會沒有可用的登入流程。切法：

```
登入與工作階段  ── OIDC（Keycloak）────────► access token
                                              │
授權與憑證      ── DID + Verifiable Credential ─┴─► 兩者都進 AccessContext
```

- **OIDC 管「你是誰、現在登入了嗎」** — 護理師、家屬、看護的日常登入。
- **DID/VC 管「你被授權做什麼」** — Consent Credential、角色憑證、代理憑證、Break-glass token。憑證由本人裝置的私鑰簽發，驗證方只需公鑰，不需回問中央。

兩者在 `AccessContext` 匯流。PDP 只看 VC，不看 OIDC token——這樣未來拔掉 OIDC 換成別的登入方式，授權邏輯不動。

### 2.5 授權注意事項（部署前需確認）

- Neo4j Community：GPLv3
- TimescaleDB：Community(TSL) 授權才有 continuous aggregates；Apache-2 版沒有。TSL 禁止拿去做 DBaaS，本產品用途不受影響
- Keycloak：Apache-2
- MinIO：AGPLv3 — 若最終要商業散布需評估，替代方案是直接用雲端 S3 相容服務

---

## 3｜系統分層與模組邊界

### 3.1 部署形狀：模組化單體，不是九個微服務

九個元件 ≠ 九個服務。v1 是**一個 Python 套件、三個行程**：

```
┌─ 行程 1：api ────────────────────────────────┐
│  GraphQL（讀）+ REST（寫）+ WebSocket（推送）  │
└──────────────────────────────────────────────┘
┌─ 行程 2：worker-ingest ──────────────────────┐
│  §06 九段攝取管線 + 投影（outbox → 圖 / 時序） │
└──────────────────────────────────────────────┘
┌─ 行程 3：worker-orchestrator ────────────────┐
│  §10 事件狀態機 + 升級計時器                   │
└──────────────────────────────────────────────┘
```

**模組邊界靠 import-linter 強制**，不是靠自律。契約寫在 `pyproject.toml`：任一模組只能透過 `ports/` 匯入他模組，直接 import 內部實作會讓 CI 紅燈。這樣未來要抽成服務，切線已經畫好了。

### 3.2 資料的權威來源

這是整份設計最重要的結構決定：

```
                    ┌─────────────────────────────┐
                    │  Assertion Log（Postgres）   │  ◄── 唯一權威來源
                    │  append-only, 雙時間軸        │      Single Source of Truth
                    └──────────────┬──────────────┘
                                   │ transactional outbox
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
        ┌───────────────────────┐     ┌───────────────────────┐
        │  Neo4j                │     │  TimescaleDB          │
        │  關係的查詢加速器       │     │  時間的查詢加速器      │
        │  可重建               │     │  可重建                │
        └───────────────────────┘     └───────────────────────┘
```

推論：
- **Neo4j 掛掉不是資料遺失，是功能降級**（§17 的降級路徑 L1）。重建腳本必須存在且被定期演練。
- 需要強一致的讀（授權判定、身分比對）**永不走圖**，只走 Postgres。
- 圖與時序是 eventually consistent，延遲有 SLO 且被監控。

---

## 4｜核心資料模型：Assertion Log

### 4.1 為什麼不是一般的 CRUD 表

母文件有四個需求，任何一個都足以否定「UPDATE 一列」的做法：

| 需求 | 出處 |
|---|---|
| 上層永遠可回溯下層（Provenance） | §4.1 |
| 衝突不合併，並列標記 | §06 |
| Event Packet 要能重播「當時護理師看到什麼」 | §11 + §16 |
| 稽核鏈不可竄改 | §9.5 |

所以：**系統中不存在「修改一筆事實」這個操作。** 只有新增斷言與標記撤回。

### 4.2 Assertion

```python
@dataclass(frozen=True)
class Assertion:
    assertion_id: UUID
    person_id: PersonID                # 分區鍵，每一筆都有
    subject: NodeRef                   # 在講哪個節點
    predicate: str                     # 在講它的什麼
    value: JsonValue

    # ── 雙時間軸 ──
    valid_from: datetime               # 世界時間：這件事何時開始為真
    valid_to: datetime | None          # None = 目前仍為真
    recorded_at: datetime              # 系統時間：我們何時知道
    retracted_at: datetime | None      # 永不刪除，只標記撤回
    retracted_by: AssertionID | None    # 被哪一筆取代

    # ── 溯源 ──
    source: SourceRef                  # 醫院甲 / 穿戴裝置 / 照顧者回報
    ingest_run_id: UUID                # 哪一次攝取
    raw_ref: ObjectRef                 # 原始訊息在物件儲存的位置
    transform_chain: list[str]          # 經過哪些正規化步驟

    # ── 治理 ──
    zone: Zone                         # 0–4，內容決定，見 §7.2
    confidence: float
    conflict_set_id: UUID | None
```

**雙時間軸讓「2026-03-11 我們相信什麼」變成一次 SQL 查詢**，而不是考古。這是終身資料唯一站得住的存法。

### 4.3 衝突不是例外，是常態

母文件 §06 的三家醫院用藥清單例子，落地成：

```
ConflictSet(cs-9931, predicate="medication.status", subject=med:amlodipine-5mg)
  ├── assertion a1  來源 醫院甲  valid_from 2026-03-11  value "active"
  └── assertion a2  來源 診所乙  valid_from 2026-05-02  value "stopped"
```

查詢 `medication.status` 回傳的**不是一個值**，是：

```json
{
  "resolved": null,
  "conflict": { "set_id": "cs-9931", "reason": "SOURCE_DISAGREEMENT" },
  "assertions": [ {...a1}, {...a2} ]
}
```

解析衝突需要有資格的人；解析結果本身是一筆帶 `source=nurse:did:...` 的新斷言，不會抹掉 a1/a2。
API 層沒有「給我一個值」這個選項——**呼叫端被迫處理衝突**，這是型別層面的強制，不是文件上的請求。

---

## 5｜Health Graph

### 5.1 節點與邊

節點標籤（對應 §5.2），每個節點都帶 `person_id`（分區）、`zone`、`assertion_ids`：

```cypher
(:Person {person_id})
(:Encounter {encounter_id, class, start, end})
(:Condition {condition_id, system, code, display, clinical_status, onset})
(:Procedure {procedure_id, code, performed})
(:Medication {medication_id, atc, display, dose, route, status, effective_from, effective_to})
(:LabResult {obs_id, loinc, value, unit, effective})
(:Vital {obs_id, loinc, value, unit, effective})
(:Event {event_id, type, level, status, detected_at})
(:Provider {provider_id, role})  (:Facility {facility_id})  (:Device {device_id, kind})
(:CaregiverRelation {relation_id, kind})  (:CarePlan {plan_id})
(:Preference {pref_id, kind})  (:Baseline {baseline_id, metric, scale})
```

邊全部帶 `{assertion_id, source, confidence, valid_from, valid_to}`。

### 5.2 關鍵設計：邊的證據等級

母文件 §5.3 的推理路徑 `(跌倒)←(低血壓)←(降壓藥)` 之所以能被醫師接受或否決，取決於**每一條邊是怎麼來的**。所以 `MAY_CONTRIBUTE_TO` 這類推論邊必須帶 `evidence_kind`：

| `evidence_kind` | 意思 | 例子 | 呈現時的措辭 |
|---|---|---|---|
| `KNOWLEDGE` | 來自策展的藥物/疾病知識庫，帶文獻引用 | Amlodipine → 姿勢性低血壓（已知副作用） | 「已知的藥理關聯」 |
| `POPULATION` | 族群統計關聯 | 高齡 + 多重用藥 → 跌倒風險 | 「族群層級的統計關聯」 |
| `PERSONAL` | **這個人自己**重複出現的模式 | 過去兩次跌倒都在夜間起身後 | 「這位病人自己的紀錄顯示」 |

沒有這一欄，AI 就只能講「可能有關」，臨床人員會問「你憑什麼」而系統答不出來。**§8.4 那個範例裡的依據 1/2/3 全是 PERSONAL，而藥理那條邊是 KNOWLEDGE——分不開，整條路徑就不可辯護。**

### 5.3 三種查詢（§5.4）

```cypher
-- 鄰居：這個病人有哪些活躍問題
MATCH (p:Person {person_id:$pid})-[:HAS_CONDITION]->(c:Condition)
WHERE c.clinical_status = 'active' AND c.zone <= $max_zone
RETURN c

-- 路徑：這次事件與過去哪些事有關聯（限深度，限 zone）
MATCH path = (e:Event {event_id:$eid})-[*1..4]-(n)
WHERE n.person_id = $pid AND ALL(x IN nodes(path) WHERE x.zone <= $max_zone)
RETURN path, [r IN relationships(path) | r.evidence_kind] AS evidence

-- 子圖萃取：Event Packet 的技術基礎
MATCH (e:Event {event_id:$eid})
CALL apoc.path.subgraphAll(e, {maxLevel:3, labelFilter:$allowed_labels})
YIELD nodes, relationships
RETURN nodes, relationships
```

**每一個查詢都帶 `$max_zone`。** 這不是選項，是 §5 節的 repository 只接受帶 `AccessContext` 的呼叫（見 §7.3）。

### 5.4 ReasoningPath 是一等公民

```python
@dataclass(frozen=True)
class ReasoningPath:
    path_id: str                       # 對應 §8.4 的「圖路徑 #4471」
    event_id: EventID
    nodes: list[NodeRef]
    edges: list[EdgeRef]
    evidence_kinds: list[EvidenceKind]
    extracted_at: datetime
    graph_version: str                 # 對應的 assertion log 位置，可重播
```

護理師可以點開 #4471 看到整條路徑；可以**否決**它：

```python
PathRejection(path_id, rejected_by: DID, reason: str, at: datetime)
```

否決紀錄回饋到 §16 的誤報率指標，也回饋到知識庫策展。這是系統從臨床端學習的唯一合法管道。

---

## 6｜Baseline Engine

母文件說這是「終身資料唯一的技術正當性」。所以它必須是真的，不能是 mean ± 2sd。

### 6.1 基準線的形狀

Key 是 `(person_id, metric, scale, context_bucket)` — **context bucket 是關鍵**：靜息心率在凌晨三點和下午三點不是同一件事。

```python
@dataclass(frozen=True)
class BaselineWindow:
    person_id: PersonID
    metric: MetricCode                  # LOINC 或自訂
    scale: Literal["short_7d", "mid_90d", "long"]
    context: ContextBucket              # {tod_bucket, activity_state, posture}

    n_samples: int
    coverage: float                     # 該窗口內實際有資料的比例
    center: float                       # 中位數
    spread: float                       # MAD（不是標準差）
    band_low: float                     # p10
    band_high: float                    # p90

    slope_per_year: float | None        # 僅 long：Theil–Sen 斜率
    slope_ci: tuple[float, float] | None

    computed_at: datetime
    established: bool                   # 見 §6.3
```

用 **median + MAD** 而不是 mean + sd，因為生理資料有離群值且不是常態分布。用 **Theil–Sen** 抓老化漂移，因為它對離群點穩健。

### 6.2 偏離分數

母文件 §7.3：`Deviation Score = f(當前值, 個人基準, 個人變異度, 時間持續度)`。落地：

```python
robust_z = (x - center) / (1.4826 * spread + EPS)      # 個人變異度
novelty  = 1 - empirical_percentile(x, person_lifetime_dist[metric][context])
duration = persistence_factor(consecutive_samples_outside_band)

deviation = {
    "robust_z": robust_z,
    "novelty": novelty,
    "duration": duration,
    "band": (band_low, band_high),
    "n": n_samples,
}
```

**注意回傳的是分量，不是一個純量。** 兩個理由：

1. §19.2 明確要求「講模式與依據，不講裸露的機率數字」。給臨床人員一個 `0.73` 只會招來「這怎麼算的」。
2. 加權合成的權重必須靠 §16 的誤報率回頭校準。在校準前把它硬編成一個數字，等於把未經驗證的判斷寫死。

母文件的「心率 74」例子在這個模型下自然成立：對 55–95 那個人 `robust_z ≈ 0`，對 58–62 那個人 `robust_z ≈ 5`。

### 6.3 建立門檻：防誤報的第一道閘

**`established = False` 的基準線不得產生任何偏離告警。** 條件：

```
n_samples >= MIN_N[metric]        且
coverage >= 0.6                   且
spread > 0                        （全同值代表裝置卡住，不是穩定）
```

母文件 §16 說「誤報率是這個系統的生死線」。最常見的誤報來源不是演算法太敏感，是**基準線建立在四筆資料上**。這道閘擋掉的比任何調參都多。

### 6.4 老化漂移 vs 異常加速（§7.4）

不是比較數值，是比較**斜率**：

```
若  slope_short_90d  落在 slope_long 的外插信賴區間之外
且  持續 >= K 個窗口
則  標記為「異常加速下降」，而非正常老化漂移
```

母文件的例子：步速每年 1–2%（在 CI 內）vs 三個月 15%（遠在 CI 外）。這是斜率變化偵測問題，不是門檻問題——用門檻做會同時漏掉緩慢惡化與誤報正常老化。

### 6.5 實作

TimescaleDB continuous aggregate 直接對應三個尺度：

```sql
CREATE MATERIALIZED VIEW baseline_short_7d
WITH (timescaledb.continuous) AS
SELECT person_id, metric, tod_bucket,
       time_bucket('1 day', observed_at) AS day,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS median,
       count(*) AS n
FROM observations
GROUP BY person_id, metric, tod_bucket, day;
```

MAD 與 Theil–Sen 在 Python 側算（SQL 裡做不乾淨），寫回 `baseline_windows` 表。

---

## 7｜Consent & Trust

### 7.1 五個維度落地

```python
@dataclass(frozen=True)
class ConsentGrant:
    grant_id: UUID
    person_id: PersonID
    grantee: DID                        # WHO
    zones: frozenset[Zone]              # WHAT
    resource_filter: ResourceFilter | None  # WHAT（更細：只給用藥清單）
    valid_from: datetime                # WHEN
    valid_to: datetime | None           # WHEN
    purposes: frozenset[PurposeCode]    # WHY
    capability: Capability              # HOW MUCH: READ | REPORT | ACT_AS
    credential_id: str                  # 對應的 VC
    revoked_at: datetime | None
```

### 7.2 Zone 是內容的屬性，不是資源型別的屬性

這是最容易做錯的地方。母文件 §9.2 的 Zone 4 是「精神科、性健康、遺傳、成癮治療」——**這些是內容分類，不是 FHIR resource type。** 一個 `Condition` 可能是 Zone 3（高血壓）也可能是 Zone 4（思覺失調症）。

```python
class ZoneClassifier:
    def classify(self, assertion: Assertion) -> Zone:
        # 1. 編碼比對優先（ICD-10 F*, 特定 LOINC, ATC N07B* 等）
        if z := self._by_code(assertion): return z
        # 2. 自由文字關鍵詞掃描（進 quarantine 待人工確認，不直接降級）
        if self._sensitive_keywords(assertion): return Zone.Z4
        # 3. resource type 預設
        if z := self._by_type(assertion): return z
        # 4. Fail closed
        return Zone.Z4
```

**未分類 → Zone 4（最高），不是 Zone 0。** 分類規則變更時必須能重跑全庫並產生差異報告。

### 7.3 PEP：靠建構強制，不靠自律

```python
class TwinSession:
    """唯一的資料存取入口。沒有 AccessContext 就建不出 session。"""
    def __init__(self, ctx: AccessContext, pdp: PolicyDecisionPoint): ...

class ConditionRepository:
    def __init__(self, session: TwinSession):   # ← 沒有無參數建構子
        self._s = session

    def active_for(self, pid: PersonID) -> ConflictAware[list[Condition]]:
        # session 內部把 ctx.max_zone 注入每一條查詢，並寫稽核
        ...
```

**沒有任何一條路徑可以繞過 PEP 拿到資料**，因為 repository 的建構子要求 session，session 的建構子要求 context。這是約束 #4 的機制：型別系統擋掉，不是 code review 擋掉。

GraphQL 層再加一層宣告：

```graphql
directive @zone(level: Int!) on FIELD_DEFINITION

type Condition {
  id: ID!
  display: String @zone(level: 3)
  code: Coding    @zone(level: 3)
  _access: AccessMeta!          # 每個型別都有
}

type AccessMeta { redacted: [RedactionInfo!]! }
type RedactionInfo { field: String!, reason: RedactionReason! }
enum RedactionReason {
  ZONE_NOT_GRANTED      # 有資料，你沒權限
  NO_DATA               # 真的沒有這筆資料
  NOT_COMPUTED          # 基準線還沒建立
  CONFLICT_UNRESOLVED   # 有多個矛盾來源
}
```

**`null` 有四種意思，必須分開。** 母文件 §17 說「資料來源缺漏，明確標示無資料，AI 不得補寫」；§15 說最小揭露。如果 UI 分不出「沒權限」與「沒資料」，兩條規則同時失效。TypeScript 型別由 schema codegen 產生，前端被迫處理 `_access`。

### 7.4 Break-glass（§9.4）

```python
@dataclass(frozen=True)
class BreakGlassGrant:
    grantee: DID                        # 出示執業憑證的救護人員
    person_id: PersonID
    opened_at: datetime
    expires_at: datetime                # 硬上限 24h，不可延長
    justification: str                  # 必填
    zones: frozenset[Zone]              # 恆為 {Z0} + 當下生理值
    notifications: list[NotificationRecord]   # 本人 + 所有代理人
    auto_closed_at: datetime | None
    disputed: bool
```

**通知是不可抑制的副作用。** 若通知全數失敗，該事實本身寫入稽核並觸發告警——不能安靜地開鎖。

### 7.5 稽核鏈（§9.5）

```sql
CREATE TABLE audit_log (
  seq           BIGSERIAL PRIMARY KEY,
  who_did       TEXT NOT NULL,
  action        TEXT NOT NULL,
  resource_refs TEXT[] NOT NULL,
  purpose_code  TEXT NOT NULL,
  credential_id TEXT,
  origin        JSONB NOT NULL,       -- device / ip / org
  at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  prev_hash     BYTEA NOT NULL,
  entry_hash    BYTEA NOT NULL        -- H(prev_hash || canonical(entry))
);

REVOKE UPDATE, DELETE ON audit_log FROM ALL;
GRANT INSERT, SELECT ON audit_log TO twin_app;
```

每日錨定 hash 另存。本人的「誰看過我的資料」畫面直接讀這張表——母文件說這是使用者最有感的功能之一，它同時也是最便宜的：資料已經在那裡了。

---

## 8｜攝取管線（§06 九段）

### 8.1 契約

每筆資料是一個 envelope，流過九段，每段追加一個 `ProvenanceStep`。
冪等鍵：`sha256(source_system, source_record_id, source_version)`。同一筆進兩次，結果位元相同。

| # | 階段 | 輸入 → 輸出 | 失敗時 |
|---|---|---|---|
| 1 | Ingestion | 原始訊息 → 存入物件儲存，得 `raw_ref` | 不可能失敗（先存後處理） |
| 2 | Validation | → `ValidationReport` | **進 quarantine，不丟棄** |
| 3 | Normalization | 單位換算、ICD/SNOMED/LOINC/ATC 對映 | 未知碼 → `unmapped_codes` 佇列，**不靜默丟棄** |
| 4 | Identity Resolution | → `IdentityLink{tier}` | 疑似 → 待確認佇列 |
| 5 | Deduplication | → `DedupDecision` | 不確定 → 保留兩筆 + 標記 |
| 6 | Conflict Handling | → `ConflictSet` 成員 | — |
| 7 | Graph Write | → assertions committed + outbox event | 交易失敗則整批回滾 |
| 8 | Baseline Update | 重算受影響窗口 | 失敗不阻塞攝取，排重試 |
| 9 | Event Bus | 發布變更事件 | outbox relay 保證至少一次 |

**貫穿規則：沒有任何一筆資料被靜默丟棄。** 每一種失敗都有一個可見的桶子，每個桶子的深度都出現在 §14 的儀表板上。積壓量本身就是資料品質指標。

### 8.2 身分比對（§3.3）永不破壞性合併

```
SourceIdentity(醫院甲, A0093821)  ─┐
SourceIdentity(醫院乙, B7712004)  ─┼─► PersonCluster(P-0019283)
SourceIdentity(穿戴, uuid_xxx)    ─┘
```

- 「合併」＝ 把 `SourceIdentity` 加進 cluster，附上 `tier` 與 `evidence`
- 「拆解」＝ 從 cluster 移除，原始資料完好無損
- 四個信心層級（確定 / 高度可能 / 疑似 / 不同人）決定加入是否需要人工確認

**任何時刻都能完全回退**，這是約束 #1 的機制。錯合病歷是母文件點名的最嚴重故障模式，而破壞性合併是不可回復的——這一格沒有折衷空間。

---

## 9｜Personal AI

### 9.1 哪些 Agent 用 LLM，哪些不用

這是整份設計最重要的一張表。

| Agent（§8.1） | 用 LLM？ | 實作 |
|---|---|---|
| Orchestrator | ❌ | 確定性狀態機（LangGraph）。**路由不由 LLM 決定** |
| Context Agent | ❌ | 載入 identity + consent + L2/L3 常駐記憶，純查詢 |
| Retrieval Agent | 部分 | 子圖萃取＝Cypher；語義檢索＝pgvector。只有 query 改寫可選用 LLM |
| **Detection Agent** | **❌** | Baseline Engine + 宣告式規則 + 時序異常。**絕不用 LLM** |
| Narrative Agent | ✅ | 產生 SBAR / 摘要，但只能引用已存在的 Claim |
| Question Agent | ✅ | 追問缺漏欄位 |
| Translation Agent | ✅ | 角色化改寫與多語（§12 的六種資訊密度） |

**Detection 不用 LLM，理由有三個，每一個都是硬的：**

1. **可重現** — 同樣輸入必須同樣輸出。誤報率（§16 的生死線）不能隨模型版本漂移。
2. **可校準** — 你要能調一個參數讓誤報下降。你調不動 LLM 的直覺。
3. **可辯護** — 「為什麼觸發？」的答案必須是「robust_z = 4.8，超出 p10–p90 帶且持續 6 個取樣點」，不是「模型認為異常」。

這條規則同時讓約束 #10（LLM 可替換）真的成立：**換模型不會改變臨床行為，只會改變措辭。** 若 detection 在 LLM 裡，換模型就是一次未經驗證的臨床變更。

### 9.2 記憶階層（§8.2）落地

| 層 | 內容 | 存哪 | 常駐？ | 大小 |
|---|---|---|---|---|
| L0 | 全量斷言 | Postgres + MinIO | ❌ 永不進 context | — |
| L1 | 近 30 天 | Postgres 物化視圖 | 按需，摘要後注入 | 變動 |
| L2 | **BaselineCard** — 數十個數值 | `baseline_windows` | ✅ | ~200 token |
| L3 | **NarrativeSummary** — 一段話講完這個人 | Postgres，版本化 | ✅ | ~150 token |
| L4 | 語義索引 | pgvector HNSW | 按需檢索 | — |

L2 + L3 常駐約 350 token，AI 隨時「認識這個人」。母文件說「幾百 token」，這裡對得上。

**L4 的檢索必須先過濾再排序：**

```sql
SELECT chunk_id, content, 1 - (embedding <=> :q) AS score
FROM narrative_chunks
WHERE person_id = :pid
  AND zone <= :max_zone          -- ← 在 ANN 查詢裡，不是查完再濾
ORDER BY embedding <=> :q
LIMIT 12;
```

查完再濾 = Zone 4 的內容已經影響了排序，等於洩漏。這是 pgvector 相對於外部向量庫的實際優勢：**同一個交易裡就能做授權預過濾。**

L3 敘事摘要本身也受 CitationGate 約束——它是 AI 產物，不是原始資料。重生成觸發於「材料性變更」（新診斷、用藥變更、事件結案），走 Batch API 半價。

### 9.3 CitationGate：約束 #3 的機制

AI 不輸出散文，輸出 Claim：

```python
@dataclass(frozen=True)
class EvidenceRef:
    kind: Literal["assertion", "observation", "baseline", "path"]
    ref_id: str
    display: str                        # 「血壓 102/65」
    source: SourceRef                   # 「家用血壓計 21:50」
    at: datetime

@dataclass(frozen=True)
class Claim:
    template: str                       # 「{subject} 低於個人基準 {band}」
    evidence: tuple[EvidenceRef, ...]   # 空的 → 攔截
    claim_type: Literal["observation", "comparison", "trend", "suggestion"]
```

Gate 的三道檢查：

```python
def check(claims: Sequence[Claim], ctx: AccessContext) -> GateResult:
    for c in claims:
        if not c.evidence:                       reject(NO_EVIDENCE)
        if not all(resolve(e) for e in c.evidence): reject(DANGLING_REF)
        if any(zone_of(e) > ctx.max_zone for e in c.evidence): reject(ZONE_LEAK)
```

第三道檢查常被忽略但很重要：**AI 可能引用了它有權讀、但收件人無權看的證據。** 給家屬的摘要不能引用 Zone 3 的檢驗值，即使 AI 用它推理過。

攔截次數 → §14 的 `ai.citation_gate.rejections`，這正是母文件 §16 要的「無來源輸出的攔截次數」。

輸出型別中**不存在** `diagnosis`、`order`、`prescription` 欄位（約束 #5）。`claim_type` 最強只到 `suggestion`。

### 9.4 三個 Context（§8.3）

每次推理組裝：

```python
PAST    = graph.longitudinal_summary(pid, ctx)      # 病史/手術/用藥/住院/檢驗
PRESENT = timeseries.current_with_deviation(pid)    # 即時值 + 偏離基準度
CONTEXT = care_circle(pid) + location + active_event  # 誰在照顧/住哪/現在發生什麼
```

母文件說少了 CONTEXT 就只是病歷摘要器。程式碼層面的落實：`NarrativeAgent.run()` 的簽章要求三者皆非 None，缺一個就不執行。

---

## 10｜Care Orchestration

### 10.1 狀態機（§10.2）

```
DETECTED → PENDING_CONFIRM → CONFIRMED → PACKAGED → PENDING_REVIEW → CLOSED
                │                                          │
                └──(逾時)──► AUTO_ESCALATED ──┘             └──► ESCALATED → 醫師/緊急
```

轉換用樂觀併發（`WHERE state = :expected`），保證計時器與人工操作競態時不會雙重轉換。
每個轉換寫一筆 `EventTransition{from, to, actor, reason, at}`——事件的完整歷程可重播。

### 10.2 升級計時器必須是持久的

母文件 §10.3 的 0 / 3 / 8 / 15 分鐘，且明說「不是系統寫死」：

```python
@dataclass
class EscalationPolicy:
    policy_id: UUID
    person_id: PersonID                 # 每個人可以不一樣
    event_level: Literal["L1","L2","L3","L4"]
    steps: list[EscalationStep]         # 有序

@dataclass
class EscalationStep:
    after: timedelta                    # 0m / 3m / 8m / 15m
    target: TargetResolver              # 第一順位照顧者 / 居家護理師 / 緊急聯絡
    channel: list[Channel]              # push / sms / 電話
```

Worker 迴圈：

```sql
SELECT * FROM escalation_timers
WHERE fire_at <= now() AND state = 'armed'
FOR UPDATE SKIP LOCKED
LIMIT 50;
```

`FOR UPDATE SKIP LOCKED` 讓多個 worker 可以水平擴充而不重複派送。
**計時器在資料庫裡，不在記憶體裡** —— 重啟不會讓一個等待中的 L1 事件永遠沉默。這是約束 #7 在這一格的具體含義。

### 10.3 事件分級（§10.1）與 L3 的特殊性

| 級別 | 觸發源 | 偵測者 | 目標反應 |
|---|---|---|---|
| L1 突發 | 裝置訊號 | Edge + Detection Agent | 秒–分鐘 |
| L2 回報 | 人的觀察 | 照顧者 App | 分鐘–小時 |
| L3 偏離 | **Baseline Engine** | 每日批次 | 天–週 |
| L4 排程 | CarePlan | 排程器 | 依計畫 |

**L3 是這個系統存在的理由**，也是唯一需要終身資料的一級。L1/L2/L4 任何一個警報器都做得到。
所以 L3 的品質門檻最高：`established=True` 的基準線、持續多個窗口、斜率變化而非單點越界。寧可少報。

---

## 11｜Event Packet

### 11.1 它是投影，不是文件

同一個事件，家屬看到的、護理師看到的、醫師看到的**不是同一份**。所以：

```
EventPacket = f(event_id, recipient_role, consent_credential, as_of)
```

```python
@dataclass(frozen=True)
class EventPacket:
    packet_id: UUID
    event_id: EventID
    recipient_role: Role
    consent_basis: str                  # 憑證 ID，對應 §11 的 consent_basis
    as_of: datetime

    assertion_snapshot: tuple[AssertionID, ...]   # 凍結：這份 packet 看到的世界
    sections: PacketSections
    redactions: tuple[Redaction, ...]             # 每一項都有 reason
    reasoning_path_id: str | None                 # §8.4 的「圖路徑 #4471」

    rendered_at: datetime
    model_id: str                       # claude-opus-5
    prompt_version: str                 # 可重播
```

`assertion_snapshot` + `prompt_version` + `model_id` 讓「三個月後回頭看，當時護理師到底看到什麼」變成一次查詢。這同時是 §16 的「摘要被修改的比例」的計算基礎，也是任何事後檢討的前提。

### 11.2 欄位對照

母文件 §11.1 的欄位全部保留，補上型別與來源：

| §11 欄位 | 型別 | 來源 |
|---|---|---|
| `baseline_context` | `list[BaselineWindow]` | Baseline Engine（L2） |
| `pre_event` / `post_event` | `list[Observation + Deviation]` | TimescaleDB + Baseline |
| `trend_context` | `list[TrendSummary]` | Baseline Engine（mid/long 斜率） |
| `relevant_history` | `Subgraph` | Neo4j 子圖萃取 |
| `active_medications` | `ConflictAware[list[Medication]]` | **可能是衝突集** |
| `caregiver_report` | `Assertion` | 照顧者 App |
| `preference_note` | `Preference` | 意願層 |
| `ai_summary` | `list[Claim]` | Narrative Agent → CitationGate |
| `ai_reasoning_path` | `ReasoningPath` | 圖路徑，可否決 |
| `recommendation` | `Claim(type=suggestion)` | 最強只到 suggestion |
| `sources` | `list[SourceRef]` | 從 evidence 自動彙總 |
| `consent_basis` | `credential_id` | PDP |

**`baseline_context` 與 `trend_context` 是驗收項，不是選填。** 母文件 §11.2 說得很直白：沒有這兩欄，這個 Packet 三天資料就能生成，「終身」是修辭。所以：**缺這兩欄的 packet 不得送出**，缺資料時要送出的是 `Redaction(reason=NOT_COMPUTED)`，明說基準線尚未建立。

---

## 12｜API 契約

### 12.1 讀：GraphQL

```graphql
type Query {
  person(id: ID!): Person
  event(id: ID!): Event
  eventPacket(eventId: ID!, as: Role!): EventPacket
  timeline(personId: ID!, from: DateTime!, to: DateTime!): [TimelineEntry!]!
  whoAccessedMe(personId: ID!, limit: Int = 50): [AuditEntry!]!   # §9.5
  askMyTwin(personId: ID!, question: String!): TwinAnswer!        # §12 本人介面
}

type TwinAnswer {
  claims: [Claim!]!          # 沒有裸文字欄位
  redactions: [RedactionInfo!]!
}
```

`TwinAnswer` 沒有 `text: String` 欄位——**約束 #3 寫進 schema**。前端拿到 claims 自己渲染，每一句旁邊都有來源。

### 12.2 寫：REST

```
POST   /v1/ingest/fhir                 FHIR Bundle
POST   /v1/ingest/hl7                  HL7 v2
POST   /v1/ingest/device               裝置讀數（批次）
POST   /v1/events                      事件通報（照顧者 / 裝置）
POST   /v1/events/{id}/confirm         照顧者確認
POST   /v1/events/{id}/review          護理師審閱（含否決推理路徑）
POST   /v1/events/{id}/false-alarm     標記誤報 → §14 指標
POST   /v1/consent/grants              簽發授權
DELETE /v1/consent/grants/{id}         撤銷（即時生效）
POST   /v1/consent/break-glass         緊急開鎖
POST   /v1/identity/links/{id}/confirm 身分比對人工確認
```

所有寫入端點接受 `Idempotency-Key`。

### 12.3 推送

WebSocket 給臨床 console（事件佇列即時更新）；Webhook 給機構系統（帶 HMAC 簽章與重試）。

---

## 13｜目錄結構

```
health-twin/
├── docs/
│   ├── 00-architecture.md              ← 本文件
│   ├── adr/                            架構決策紀錄（每個否決的選項都留一筆）
│   └── source/personal-health-twin.md  上游產品架構
├── contracts/                          跨語言契約，CI 驗證
│   ├── graphql/schema.graphql
│   ├── openapi/write-api.yaml
│   ├── events/*.schema.json            事件匯流排
│   └── packet/event-packet.schema.json
├── twin/                               Python 套件（模組化單體）
│   ├── core/                           Assertion / Provenance / Zone / NodeRef / ConflictAware
│   ├── identity/                       §01 §3.3  PersonCluster、比對、生命週期
│   ├── consent/                        §06 §09   PDP / PEP / ZoneClassifier / 稽核鏈
│   ├── ingest/                         §06       九段管線 + fhir/hl7/device adapters
│   ├── graph/                          §03 §05   Neo4j repository + Cypher 查詢庫 + ReasoningPath
│   ├── baseline/                       §04 §07   基準線引擎 + 偏離 + 斜率
│   ├── ai/                             §05 §08
│   │   ├── agents/                     七個 agent
│   │   ├── memory/                     L0–L4
│   │   ├── citation_gate.py            約束 #3
│   │   └── llm/                        LLMProvider port + anthropic adapter
│   ├── orchestration/                  §07 §10   狀態機 + 計時器 + 升級策略
│   ├── packet/                         §11       Event Packet 組裝器
│   ├── governance/                     §09 §16   稽核查詢、指標、去識別化管線
│   └── api/                            §12 §13   graphql + rest + ws
├── workers/
│   ├── ingest_worker.py
│   ├── projection_worker.py            outbox → Neo4j / TimescaleDB
│   └── orchestrator_worker.py          升級計時器
├── web/                                React + TS
│   ├── src/roles/{person,family,caregiver,nurse,doctor,admin}
│   ├── src/design-system/
│   └── src/gql/                        codegen 產物（含 _access 型別）
├── edge-sim/                           §14 §21   裝置端模擬器
├── ops/
│   ├── docker-compose.yml              pg+timescale+pgvector / neo4j / redis / minio / keycloak
│   ├── migrations/
│   └── seed/                           假的終身病歷 + 假基準線（§28 Demo 需要）
└── tests/
    ├── contract/                       契約測試
    ├── policy/                         §9.3 六角色 × 五分區窮舉矩陣
    ├── golden/                         Event Packet 黃金樣本（換模型不得改變結構）
    └── chaos/                          §17 降級演練
```

`tests/policy/` 是表格驅動的窮舉測試。母文件 §9.3 那張矩陣有 30 格，每一格都是一個測試案例。**授權邏輯漂移時，這 30 個測試會先紅。**

---

## 14｜可觀測性與失效降級

### 14.1 指標（§16）

| 群 | 指標 | 為什麼重要 |
|---|---|---|
| 資料 | `ingest.source_lag`、`ingest.completeness`、`identity.pending_confirmations`、`conflict.open_count / resolution_rate`、`normalize.unmapped_codes` | 每一個都對應 §8.1 的一個「桶子」 |
| AI | **`ai.false_alarm_rate`**、`ai.miss_rate`、`ai.summary_edit_rate`、`ai.citation_gate.rejections`、`ai.path_rejection_rate` | 生死線 |
| 流程 | `event.detect_to_review_p50`、`escalation.timeout_rate`、`caregiver.response_rate` | §10 的健康度 |
| 信任 | `breakglass.count / post_hoc_approval`、`consent.revocations`、`audit.self_view_frequency` | §9 的健康度 |

**誤報率的定義要精確**，否則會被優化成無意義的數字：

```
ai.false_alarm_rate = (護理師標記為誤報的事件數) / (送到護理師眼前的事件數)
```

按 **detector 分群**，否則你只知道「太吵」，不知道是哪條規則吵。

**告警預算**：每人每週的告警數有上限。超過時觸發的是**detector 檢討**，不是更多告警。母文件說「一個常誤報的系統，三週後就沒有人看了」——這是唯一能在工程上防住這件事的機制。

### 14.2 降級模式（§17）

| 級 | 觸發 | 行為 | UI 狀態 |
|---|---|---|---|
| **L0** 正常 | — | 全功能 | 無標示 |
| **L1** AI 降級 | LLM 不可用 / CitationGate 拒絕率飆高 | Packet 照組，**只是沒有敘事**：結構化資料、基準線、偏離度照常送到護理師 | 「AI 摘要暫停，資料正常」 |
| **L2** 圖降級 | Neo4j 不可用 | 路徑推理停用；鄰居查詢退回 Postgres 斷言表 | 「關聯分析暫停」 |
| **L3** 網路中斷 | Edge 失聯 | 裝置端本地告警 + 離線暫存；恢復後補傳 | 裝置端顯示「離線模式」 |
| **L4** 後端中斷 | API 不可用 | **純通訊模式**：至少能把人叫來 | 「系統異常，緊急聯絡功能仍可用」 |

母文件 §27.08 是「誠實失效」——所以每一級都有明說的 UI 狀態。**系統壞掉時要說，不要假裝正常。**
L1 這一級的設計特別重要：它證明了 AI 是加值層不是關鍵路徑。這也是約束 #10 的另一面。

`tests/chaos/` 逐級演練，每次發布前跑。

---

## 15｜里程碑

| 里程碑 | 內容 | 完成判準 |
|---|---|---|
| **M0** 骨架 | contracts、`core/` 斷言模型、**`TwinSession` 骨架**、docker-compose、CI、import-linter | 空的 repository 也必須要求 session 才能建構 |
| **M1** 攝取與圖 | §06 九段管線、FHIR + device adapter、outbox → Neo4j 投影、種子假終身病歷 | 三份矛盾用藥清單進去，出來是 ConflictSet |
| **M2** 授權與稽核 | ZoneClassifier、PDP、稽核鏈、§9.3 矩陣測試 | 30 格窮舉測試全綠；直打 API 拿不到 Zone 4 |
| **M3** 基準線 | 三尺度窗口、robust 偏離、Theil–Sen 斜率、`established` 閘 | 母文件 §7.1 的王先生表格能被真的算出來 |
| **M4** Personal AI | L0–L4 記憶、Retrieval、CitationGate、Narrative | 注入無來源 claim 被擋；黃金樣本穩定 |
| **M5** 編排與 Packet | 狀態機、持久計時器、Packet 組裝器 | 殺掉 worker 再啟動，等待中的 L1 仍會升級 |
| **M6** 介面 | 六角色路由樹、`_access` 處理、Ask My Twin | 家屬與護理師看同一事件得到不同 packet |
| **M7** 觀測與降級 | 指標、告警預算、四級降級、chaos 測試 | 拔掉 Neo4j / LLM，通訊路徑仍在 |

**M0 的關鍵不是產出多少程式碼，是把 PEP 的形狀先立起來。** 授權不能是 M2 才「補上去」——補的授權一定有洞。M0 先讓所有 repository 在型別上要求 `TwinSession`，M2 再把政策填進去。

M1 與 M2 的順序看起來反直覺（先資料後授權），理由是沒有資料就無法驗證授權。用 M0 的建構強制彌補這個順序風險。

---

## 16｜未決事項

### 16.1 需要你裁決

1. **Neo4j vs Apache AGE**（§2.3）— 兩顆引擎換路徑查詢能力，還是一顆引擎換維運簡單。
2. **Keycloak 是否必要** — 若 v1 只在單一機構內 demo，可以先用簡化的 OIDC stub，把 Keycloak 排到 M6。
3. **前端要不要拆多個 app** — 目前設計是單一 app + 六個路由樹。若外籍看護版要做成獨立 PWA（母文件 §12 說「文字最少化」），可能值得拆。
4. **Edge 層的範圍** — v1 是否只做模擬器，還是要接一款真實裝置。這會影響 M1 的時程。

### 16.2 沿用母文件的待查證清單

母文件末尾列的六項全部有效，且其中三項會直接改變技術設計：

- **FHIR 資源名稱與版本** — 影響 §4.2 對照表與 adapter 實作
- **AI 醫療器材（SaMD）認定界線與 TFDA 指引** — 影響 §9.1 Detection 的定位與 §11 `recommendation` 的措辭邊界
- **個資法與電子病歷上雲/委外規定** — 直接影響 §3.2 的部署形狀（雲端託管 / 機構託管 / 自持 三選一是否都合法）

其餘三項（健保長照給付、病主法委任代理程序、學術文獻）不改技術設計，但改產品定位與意願層的法律效力。

### 16.3 我刻意沒做的

- **PART B 全部**（§18–§26）。Predictive / Simulative / Ambient / Twin-to-Twin / Population 都只在 §5.2 的邊型別與 §13 的目錄結構留了擴充點，沒有實作。理由：母文件 §19.3 自己說了，預測層在完成驗證前只能做排序與提醒——那不是這一版該碰的東西。
- **零知識證明**（§15）。留在未來方向。
- **多代 Twin 與遺傳傳承**（§25）。資料模型的 `PersonCluster` 沒有排除它，但家族圖不在 v1。

---

## 附錄 A｜約束 → 機制 → 檔案

給實作時查表用。

| 約束 | 機制 | 主要檔案 |
|---|---|---|
| #1 不錯合 | PersonCluster 可逆合併 | `twin/identity/cluster.py` |
| #2 不猜不合併 | ConflictSet + `ConflictAware[T]` | `twin/core/conflict.py` |
| #3 無來源不輸出 | CitationGate | `twin/ai/citation_gate.py` |
| #4 最小揭露 | TwinSession + PDP/PEP | `twin/consent/session.py` |
| #5 不診斷 | Claim 型別無 diagnosis 欄位 | `twin/ai/types.py` |
| #6 人確認 | 狀態機 `requires_human_ack` | `twin/orchestration/machine.py` |
| #7 誠實降級 | DegradationLevel + chaos 測試 | `twin/governance/degradation.py` |
| #8 意願優先 | Preference 一等公民 | `twin/packet/assembler.py` |
| #9 全留痕 | Hash 鏈 + INSERT-only 角色 | `twin/consent/audit.py` |
| #10 LLM 可替換 | LLMProvider port | `twin/ai/llm/port.py` |
