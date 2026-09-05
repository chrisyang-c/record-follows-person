# CONSOLIDATION — 工作區整併（2026-09-05）

> 目標：**只取得這個 repo，就能開發、啟動、測試**。工作區其他資料夾只供參考，不再是產品運作的依賴。

本文件記錄整併期間每一份來源內容的去向。沒有列在這裡的東西，就是沒有被檢查過。

---

## 0. 整併前後的工作區

```
整併前                              整併後
D:\Health AI Bridge\               D:\Health AI Bridge\
├── record-follows-person\   ←──── ├── record-follows-person\   唯一正式專案
├── Healthcare\             ─改名─→ ├── health-ref\             參考來源，唯讀
├── claude_healthcare\      ─刪除            （內容見 §2）
├── gpt_healthcare\         ─刪除
├── docs\00-architecture.md ─收錄─→ └── docs\ 外層只剩這一份提案的原件
└── …最終版.md              ─刪除
```

**重要更正**：`health-ref` **只等於原本的 `Healthcare`**（robocopy `/MOVE`，逐位元相同，git repo 與 5,528 行未提交的工作都完好）。它**不包含** `claude_healthcare` 或 `gpt_healthcare` 的內容 —— 那兩個是分別刪除的，不是併進去的。

---

## 1. 整合清單

| # | 來源 | 用途 | 目的位置 | 採用狀態 | 驗收方式 |
|---|---|---|---|---|---|
| 1 | `claude_healthcare/twin/baseline/` | 個人生理值正常帶（median／MAD／p10–p90）、established 門檻 | `apps/api/baseline/` | **已採用** `c0a6802` | `pytest baseline/` 全過；`test_band_not_established_on_too_few_readings` 驗證門檻 |
| 2 | `claude_healthcare/twin/detection/` 的「偵測不用 LLM」原則 | 紅燈規則不呼叫模型 | `red_flags/rules.py` | **已存在**（本 repo §1.4 早有同一條） | `test_rules_module_never_calls_an_llm` |
| 3 | `claude_healthcare/twin/consent/` Zone 0–4 分區授權 | 依內容敏感度分區 | — | **不採用** | 本 repo 用 Care Circle scope（`who/timeline/docs/talk`），兩套不相容，見 §3 |
| 4 | `claude_healthcare/twin/ai/citation_gate.py` | 沒有來源的句子不准輸出 | — | **不採用** | 本 repo 用 provenance ＋ `timeline_write` 守門達成同一目的 |
| 5 | `claude_healthcare/twin/core/` 斷言日誌（append-only、雙時間軸） | 唯一權威資料來源 | — | **不採用** | 本 repo 用 PersonRecord ＋ `timeline_write`，見 §3 |
| 6 | `claude_healthcare/twin/packet/` Event Packet 組裝器 | 依角色投影的事件資訊包 | — | **不採用** | 本 repo 的 `IncidentFile`（事件資訊包）已涵蓋 |
| 7 | `claude_healthcare/web/` 四角色前端 | Patient／Caregiver／Nurse／Doctor 介面 | — | **不採用** | 本 repo 的四扇門更完整（OMNI-TWIN 殼、列印白底、body hologram） |
| 8 | `claude_healthcare` 其餘（約 13,500 行） | — | — | **已刪除，未保存** | 見 §2 的風險說明 |
| 9 | `gpt_healthcare/docs/PROJECT_MASTER.md` 等 5 份 | 產品願景 | — | **重複** | 與 `docs/VISION_personal_health_twin.md` 內容重疊，無獨有資訊 |
| 10 | 根目錄 `…最終版.md`（35.4 KB） | 產品願景 | — | **重複** | 與 `docs/VISION_personal_health_twin.md` 同一份檔案（同 35,4xx bytes） |
| 11 | 外層 `docs/00-architecture.md`（50 KB） | 平台架構提案 | `docs/proposals/00-architecture.md` | **收錄為待審提案** | 逐項採納狀態記在該檔頁首；未採納者維持提案狀態 |
| 12 | `health-ref` 的 `HealthEvent` 通用事件模型 | 事件不寫死成「跌倒」 | 候選 → `docs/ROADMAP.md` Epic 2 | **僅供參考（想法）** | 見 §2 授權限制：只能借想法，不能移植程式碼 |
| 13 | `health-ref` 的 `ConsentGrant.purpose` / `AuditLog.purpose` | 授權與稽核記錄「為了什麼目的」 | `packages/schema`（`CareCircleMember`、`AccessLogEntry`） | **已移植（想法，重寫）** | 見 §4 |
| 14 | `health-ref` 其餘（前端 6 頁、twin_service、SQLAlchemy 模型、3,993 行 CSS） | — | — | **僅供參考** | 本 repo 皆有對應且更完整的實作 |
| 15 | Windows 開發入口 | 從 repo 根目錄啟動／檢查／codegen | `scripts/dev.ps1` | **已採用** | 見 §5 |

---

## 2. `health-ref` 的授權限制（硬約束）

```
health-ref  =  github.com/chenni416/Healthcare
LICENSE     :  沒有
package.json:  "license": ""，"private": true
本 repo     :  Apache-2.0
```

**沒有授權檔 = 著作權法預設保留所有權利。** 依 CLAUDE.md §0.5：只借想法，或 MIT／Apache／CC0 授權下的程式碼。

因此：

- ❌ **不得複製 `health-ref` 的任何程式碼進本 repo** —— 把無授權的碼放進 Apache-2.0 專案是授權違規。
- ✅ 可以借**想法**，自行重寫，並在檔案頂端註明「概念參考：chenni416/Healthcare（無授權宣告，僅借用概念）」。

清單第 12、13 項是唯二值得借的想法，兩項都會自行重寫。

### 2.1 兩個要讓擁有者知道的事

1. **`health-ref` 有 18 個檔案、5,528 行新增沒有提交。** 角色從 `caregiver|nurse` 擴成 `patient|family|caregiver|nurse|doctor`、`src/index.css` 加了 4,629 行、router／langgraph_service／test_api 都改過。放在本機未推的狀態風險很高。
2. **`backend/venv` 有 4,101 個檔案被 commit 進該 repo。** 這是它 `.git` 15 MB 的來源。處理方式是 `git rm -r --cached backend/venv` ＋ 補 `.gitignore`，但那是該 repo 擁有者的決定。

### 2.2 `claude_healthcare` 已不可回復

依使用者指示刪除。除了第 1 項（baseline 引擎）已移植，其餘約 13,500 行沒有備份。設計文件本身保存在第 11 項。**這是整併期間唯一不可逆的損失，記錄於此以免日後誤以為它在 `health-ref` 裡。**

---

## 3. 兩套架構方向的取捨

外層提案（`docs/proposals/00-architecture.md`）與本 repo 是兩條不同的路。**不能靠複製檔案合成**，逐項決定如下：

| 議題 | 提案的做法 | 本 repo 的做法 | 決定 |
|---|---|---|---|
| 權威資料 | append-only 斷言日誌，雙時間軸 | PersonRecord ＋ `timeline_write` 單一寫入點 | **維持本 repo**。兩者都達成「只增不改」，本 repo 的已有 20 個測試檔繞著它建立 |
| 授權模型 | Zone 0–4 依**內容敏感度**分區 | Care Circle scope 依**頁面**分區（who/timeline/docs/talk） | **維持本 repo**，但補 purpose 欄位（§4）。Zone 分區留在 ROADMAP 作為 Consent Engine 的候選 |
| AI 輸出守門 | CitationGate：型別上不存在無來源的 Claim | provenance ＋ 護理師確認閘門 | **維持本 repo**。同一個目的，本 repo 的做法與 LangGraph interrupt 結構一致 |
| 前端 | Vite ＋ 原生 JS | Next.js App Router ＋ Tailwind | **維持本 repo** |
| 讀取 API | GraphQL 欄位級 `@zone` | REST | **維持本 repo** |
| 儲存 | Postgres ＋ Neo4j ＋ TimescaleDB | 檔案系統 ＋ Postgres（LangGraph checkpointer） | **維持本 repo**；正式儲存層列入 ROADMAP |
| 個人基準線 | median／MAD／三尺度 | 護理師寫的 `vitals_usual` | **已合流**（第 1 項）：兩者並存，帶只描述比較，不寫回 baseline |

**唯一已合流的是基準線。** 其餘皆維持本 repo，提案文件保留在 `docs/proposals/` 供日後逐項再議。

---

## 4. 待移植：授權與稽核的 purpose 欄位

VISION §16 定義存取要回答 `WHO / WHAT / WHEN / WHY / HOW MUCH`。本 repo 現況：

| 維度 | `CareCircleMember` | `AccessLogEntry` |
|---|---|---|
| WHO | `member_id`、`role` ✅ | `who`、`role` ✅ |
| WHAT | `scopes` ✅ | `what` ✅ |
| WHEN | `valid_from`／`valid_to` ✅ | `ts` ✅ |
| **WHY** | **缺** | **缺** |
| HOW MUCH | `scopes` ✅ | — |

**採用狀態：已移植（2026-09-05 統整 commit）。** 目的位置 `packages/schema/record_schema/models.py`。
驗收方式：`CareCircleMember.purpose` 與 `AccessLogEntry.purpose` 存在且非空；`/patients/{id}/access-log` 回傳含 purpose；`tests/test_care_circle.py` 新增一個「授權必須說明目的」的案例。


---

## 5. 開發入口

`Makefile` 的 `db-local`／`reset` 綁 Homebrew，只在 macOS 可用。新增 `scripts/dev.ps1` 作為 Windows 入口，指令與 Makefile 對應。

**安全邊界（brief 要求）**：日常指令（`api`／`web`／`test`／`lint`／`codegen`）**不會**清空 `records/` 或重建資料庫。破壞性操作是獨立且需要明確確認的指令（`init`／`reset`），會先列出將被刪除的東西並要求輸入 `yes`。

---

## 6. 剩餘差異與未完成項目

| 項目 | 狀態 |
|---|---|
| §4 的 purpose 欄位 | 已執行：schema、seed、登入、授權端點必填、access log 帶入、前端顯示；`tests/test_integration_bands_purpose.py` |
| ROADMAP 的 12 個平台 Epic | 未排程，見 `docs/ROADMAP.md` |
| `health-ref` 的未提交工作與 venv 問題 | 已通知，屬該 repo 擁有者 |
| `claude_healthcare` 的 13,500 行 | 已刪除，不可回復（§2.2） |
| web 端測試未在此機器驗證 | 這台機器沒有 pnpm；api 側 133 測試全過、ruff 乾淨 |
