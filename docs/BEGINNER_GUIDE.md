# Personal Health Twin 入門指南

> 給第一次接觸這個專案的人。先用白話了解「它在解決什麼問題、怎麼操作、每個資料夾放什麼」，再進入技術文件。

## 先用一句話理解

這是一個「跟著同一個人走的健康紀錄」示範系統。

照顧者可以用一句話告訴系統住民今天的狀況；AI 會把這句話整理成紀錄，但不替人下診斷；護理師確認後，醫師才會在巡診頁看到整理好的資訊。

```text
照顧者說今天的狀況
        ↓
AI 整理原話（不做診斷）
        ↓
護理師確認或修改
        ↓
正式寫入健康紀錄
        ↓
醫師在巡診頁閱讀
```

---

## 這個系統想解決什麼？

長照現場每天都有很多重要觀察，例如「今天吃得比較少」、「走路變慢」、「晚上一直醒來」。這些話常常只停留在口頭交班，沒有進入可以長期查找的紀錄。

本專案的做法是：

- 讓照顧者用說話或打字提供原始觀察。
- 保留原話，不把 AI 改寫後的句子當成唯一證據。
- 讓 AI 幫忙分類與整理，不讓 AI 代替護理師判斷。
- 讓護理師確認後，才把內容變成正式的健康紀錄。
- 讓醫師在巡診前看到這個人的長期變化，而不是只看到零散的一次交班。

這是一個可以操作與測試的 prototype（原型），不是已經可以拿來看診的醫療產品。

## 四種使用者，用白話說

| 使用者 | 他在做什麼 | 在畫面上看到什麼 |
|---|---|---|
| 本人 | 看自己的健康故事，決定誰可以看 | `/me`：今天、長期時間軸、問我的紀錄、Care Circle |
| 家屬／照顧者 | 回報今天觀察到的狀況 | `/caregiver`：住民卡與對話；可以在病人頁補充原話 |
| 護理師 | 確認內容、補現場評估、處理需要追蹤的事件 | `/nurse`：Clinical Queue、事件資訊包、巡診準備 |
| 醫師 | 在巡診時快速了解這個人的歷史與最近變化 | `/doctor`：一人一頁、縱向摘要、RoundPage |

另外的 `/twin` 是活體數位孿生視圖：它用圖像和趨勢呈現資料，但其中的 3D 外觀與部分狀態是示意，不是診斷或預測。

## 一次照護事件怎麼走

### 一般日常觀察

1. 照顧者說：「今天早餐只吃一半，下午比較沒精神。」
2. AI 把內容整理到「進食」和「活動／功能」等觀察面向，並保留原話。
3. 系統可能再問一個問題，例如是否發燒、是否叫得醒；問題是為了補齊資料，不是為了下結論。
4. 護理師在審核畫面確認、修改或退回。
5. 確認後才寫入正式時間軸，未確認內容仍是草稿或對話資料。
6. 醫師之後可以在巡診頁看到這筆已確認的資訊與來源。

### 可能跌倒或其他紅燈事件

1. 示範感測器送出「可能跌倒」訊號。
2. 純程式規則先檢查是否需要立即通知護理師；這一步不交給 AI 判斷。
3. 照顧者可以回報「他沒事」、「可能受傷」或其他現場狀況。
4. 護理師查看事件資訊包與感測原始值，填寫自己的評估與處理方式。
5. 後續追蹤會建立任務；目前 demo 只會把任務放進系統供護理師查看，還沒有真的發送 LINE／簡訊。

## 外層工作區怎麼看

從 `D:/Health AI Bridge/` 開始：

| 資料夾 | 白話用途 | 你要不要修改 |
|---|---|---|
| `record-follows-person/` | 正式程式專案，所有程式、測試與公開文件都在這裡 | **只在這裡修改** |
| `references/lectures/` | 三篇演講 PDF，當作背景閱讀 | 不要當程式相依，也不要放進 commit |
| `_archive/20260906-consolidation/` | 舊資料與舊提案的保存區 | 不要從這裡繼續開發 |
| 外層 `README.md` | 工作區入口 | 只用來找路 |

完整的逐資料夾說明在 [`docs/DIRECTORY_GUIDE.md`](DIRECTORY_GUIDE.md)。

如果你是從 GitHub 重新 clone，本機可能只有 `record-follows-person/` 這個 repo；`references/` 和 `_archive/` 是這台電腦保留的閱讀材料與歷史備份，不是執行相依，也不需要為了啟動程式特別下載。下面的 `D:/Health AI Bridge/record-follows-person` 請換成你實際 clone 的路徑。

## 正式 repo 裡的資料夾怎麼看

| 資料夾 | 白話用途 |
|---|---|
| `apps/api/` | 後端伺服器：接收請求、跑照護流程、管理資料與權限 |
| `apps/web/` | 前端網頁：四種角色看到的畫面與互動 |
| `data/seed/` | 產生三位合成住民的示範資料 |
| `packages/schema/` | 定義 API 與網頁共用的資料格式 |
| `scripts/` | 安裝、測試、備份、部署前檢查與隔離 smoke test |
| `docs/` | 架構、交接、安全、驗證、設計與歷史證據 |
| `design-system/` | UI 設計的原始產物；實際採用規則以 `docs/design.md` 為準 |
| `local-notes/` | 本機私人筆記，不會跟著 Git clone 或 push |

想知道每個子資料夾的工作，再看 [`docs/DIRECTORY_GUIDE.md`](DIRECTORY_GUIDE.md)；不用先讀所有 Python 或 TypeScript 檔案。

## 第一次在 Windows 啟動

以下都在 PowerShell 執行。先進入正式 repo：

```powershell
Set-Location 'D:/Health AI Bridge/record-follows-person'
```

安裝相依並跑完整檢查：

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.\scripts\dev.ps1 setup
.\scripts\dev.ps1 check
```

每一行的意思：

- `Copy-Item`：從範本建立本機設定檔；`.env` 不會被提交。
- `setup`：安裝 Python 與 web 相依套件，不會清掉 records。
- `check`：跑測試、格式檢查、前端建置與 mock 評測。

沒有 OpenAI API key 時，在 `.env` 加上：

```dotenv
MODEL_PROVIDER=mock
```

這樣可以驗證程式接線，但 mock 不是實際 AI 品質測試。

## 要看到網頁 demo

啟動網頁流程需要 PostgreSQL 17。若使用 Docker：

```powershell
docker compose up -d postgres
.\scripts\dev.ps1 migrate
.\scripts\dev.ps1 seed
```

`seed` 會重新建立可丟棄的合成資料，執行前確認沒有重要資料。

再開兩個 PowerShell 視窗：

```powershell
.\scripts\dev.ps1 api
```

```powershell
.\scripts\dev.ps1 web
```

瀏覽器開啟：

- <http://localhost:3000>：網頁
- <http://localhost:8000/docs>：API 操作文件

## 新手最常用的文件順序

1. 本頁：先了解專案在做什麼。
2. [`docs/DIRECTORY_GUIDE.md`](DIRECTORY_GUIDE.md)：了解每個資料夾與文件。
3. [`docs/OVERVIEW.md`](OVERVIEW.md)：了解產品故事與一次事件。
4. [`docs/HANDOFF.md`](HANDOFF.md)：了解現在做到哪裡、下一步是什麼。
5. [`docs/SECURITY.md`](SECURITY.md)：了解登入、授權與不能做的事。
6. [`docs/VALIDATION.md`](VALIDATION.md)：了解哪些測試真的跑過。
7. [`docs/ARCHITECTURE.md`](ARCHITECTURE.md)：需要修改流程時再讀技術架構。
8. [`docs/ROADMAP.md`](ROADMAP.md)：要規劃新功能時再讀分期計畫。

## 重要名詞小字典

| 名詞 | 初學者版解釋 |
|---|---|
| repo | 放程式與 Git 版本紀錄的專案資料夾；本專案就是 `record-follows-person` |
| frontend／web | 使用者在瀏覽器看到的畫面，位於 `apps/web` |
| backend／API | 在背景接收請求、跑流程、讀寫資料的服務，位於 `apps/api` |
| schema | 資料格式的規則，例如一筆觀察必須有哪些欄位 |
| synthetic data | 虛構的示範資料，不是真實病人資料 |
| mock | 模擬模型的固定程式，方便測試，不代表真正 AI 能力 |
| session | 登入後由伺服器暫時記住「現在是誰」的憑證 |
| consent／授權 | 病人同意某個人可以看哪些資料 |
| purpose／用途 | 這次為什麼要查看資料，例如照護或治療 |
| scope／範圍 | 可以看的資料區塊，例如 timeline 或 docs |
| provenance／來源 | 一筆資料是誰說的、何時產生、誰確認過 |
| baseline／基線 | 這個人平常的狀態，用來比較最近是否不同 |
| timeline／時間軸 | 按時間排列的已確認健康紀錄 |
| FHIR | 醫療資料交換的一套通用格式；本 repo 目前只有合成資料切片，不是完整 FHIR server |
| LangGraph | 把「抽取、比較、人工確認、寫入」排成可中斷流程的工具 |
| worker | 背景工作程式，例如掃描到期的追蹤任務 |
| CI | GitHub 自動幫忙跑測試與建置的檢查 |

## 這個專案的安全底線

- 不要匯入真實病人資料。
- 不要把本機 demo 公開到網際網路。
- AI 不下診斷、不取代護理師或醫師。
- 只有確認後的內容才是正式 timeline 紀錄。
- 看到「沒有紀錄」不等於事情一定沒有發生，可能只是尚未匯入或尚未找到證據。
- 修改前先看 `git status`；不要直接使用 `reset`、`seed` 或 `clean-records` 清除不確定的資料。

如果已經能看懂本頁，就可以開始閱讀 `HANDOFF.md`；不需要先懂所有 AI、FHIR 或資料庫術語。

最後更新：2026-09-13
