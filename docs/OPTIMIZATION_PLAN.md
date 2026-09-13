# 優化設計備忘：可信資料與可驗收的照護協作

日期：2026-09-13。本文件仍是待採納的設計細節，補充 [PROJECT_REVIEW](PROJECT_REVIEW.md) 與 [ROADMAP](ROADMAP.md)，不取代 ARCHITECTURE 或當前工作佇列 HANDOFF。M1/M2 本機版本與 M3–M7 第一版切片已有實作；本文後續欄位、路徑與 API 仍是候選契約，不代表已存在；實作時先記 DECISIONS，再改 schema／codegen／測試。

> **給初學者：** 這份文件是「可以怎麼變得更好」的設計備忘，不是目前功能清單。看到「候選」、「建議」或「待採納」時，代表尚未承諾要做；目前做到哪裡請以 [HANDOFF](HANDOFF.md) 和 [VALIDATION](VALIDATION.md) 為準。完整名詞說明在 [入門指南](BEGINNER_GUIDE.md)。

本文只引用公開標準、研究與 repo 程式。不收錄非公開教材、內部案例數字、圖像或逐字稿。

## 1. 優化的主軸

讓使用者只輸入一次、資料可追溯、AI 主張有證據、照護任務有人接且能收尾。保留現有 PersonRecord、Path A/B、人工批准、個人生理正常帶與 UI，不用整套重寫換取抽象上的完整性。

順序維持 M1 身分與病人隔離 → M2 用途／投影／稽核 → M3 紀錄契約 → M4 首個外部來源 → M5 證據問答 → M6 通知及追蹤閉環。以下七項按此依賴落地，並行的合成案例研究不需要等待全部平台建好。

## 2. 來源封包與品質：先解決資料是否可用（M3/M4）

候選 `SourceEnvelope` 作為 ingest 接口，不另建第二份可修改的病歷：

- `source_system`、`external_id`、來源版本／內容雜湊、原件 reference。
- `observed_at`（何時發生）、`received_at`（何時收到）、時區／時鐘品質。
- 原始 code／unit／value 與正規化值分開，保存 mapping 版本。
- `quality_flags`、缺值原因、驗證結果與人工修正 reference。
- `identity_link_status`、病人 reference、ingestion 冪等鍵。

內部品質 metadata 不自動顯示為臨床分數，不放寬 CLAUDE 的角色輸出限制。接入端驗證來源身分；身份不確定的資料隔離待確認，不能先掛到猜測的病人再交給 AI。

候選位置：`apps/api/ingest/`、`packages/schema/record_schema/`、`apps/api/record/`。驗收涵蓋錯誤單位、未來時間、晚到／亂序、缺值、同來源重送、更正、同名不同人。錯誤結果要可處理，不只寫 log 後當成功。

## 3. 第一條 FHIR 資料鏈：台灣合成量測 Bundle（M4）

建議釘住 FHIR R4 4.0.1 與 TW Core package 1.0.0。官方發布頁提供此版本結構及範例，實作需逐個核對所選 profile 的約束，不能只驗 resourceType。[衛福部 TW Core 下載頁](https://twcore.mohw.gov.tw/ig/twcore/downloads.html)

第一版只選合成 `Patient`、`Encounter`、`Observation` 與本地來源紀錄；支援清單明確，之後再擴檢验報告、藥物與文件。病人主鍵不直接以外部 FHIR id 取代；使用來源 namespace＋外部識別碼的 mapping。

候選 adapter：`apps/api/ingest/fhir_r4.py`；測試 fixtures：`data/fhir/`；候選 API 為受 M1/M2 保護的匯入／查詢／匯出，具體路由由契約設計決定。第一版採明定的 Bundle 型態與大小上限，不冒充完整 FHIR transaction server。

Done：profile 驗證、錯誤回報、未知欄位保存策略、references 可解析、單位及代碼映射、冪等匯入、更正不抹歷史、來源可查、重新匯出可驗證；未知或不支援的 resource 不靜默丟失。首版不連醫院，不用真病人。

## 4. 資料、授權與規則分層，不混成一個 FHIR Epic

| 元件 | 處理什麼 | 本專案採用條件 |
|---|---|---|
| FHIR／TW Core | 資料交換與 profiles | M4 的明定 resources、版本及驗證 |
| SMART App Launch | OAuth-based 授權、應用啟動及病人情境 | 有合作 sandbox，且 M1/M2 已完成；token 不取代本地病人關係政策 |
| CQL | 可交換的臨床／品質邏輯表達 | 確認跨系統規則需求後，才評估 engine |
| CDS Hooks | 在既有醫療工作流事件呼叫服務 | 有可對接的 client、明確 hook 與失敗／回覆行為 |

這些職責來自 [SMART App Launch](https://hl7.org/fhir/smart-app-launch/STU2.2/app-launch.html)、[CQL 規格](https://cql.hl7.org/) 與 [CDS Hooks](https://cds-hooks.hl7.org/)；不表示本 repo 已相容這些標準，也不保證任何院所可直接連線。

眼前可做的是既有純程式紅燈規則的版本化目錄：rule id、版本、負責角色、適用族群／情境、輸入單位、缺值處理、證據、邊界案例、發布／停用時間。保留現有門檻及人工確認，不在此輪自動新增醫療規則或改寫 baseline。

## 5. 將家屬摘要與 FollowUp 變成可完成的任務（M6）

目前 `path_a.py::schedule_follow_up` 讀護理 review 的 `follow_up_hours`（預設 4），保存 due_at/question/set_by，接著設 done 並清 deadline；`graphs/worker.py` 掃描的是逾時中斷流程，不是這份 FollowUp 的到期派送。這是具體缺口，不只是欠一個頁面。

候選 care task 契約含任務 id、patient、event、assignee、due_at、狀態、版本、確認及結案理由；通知 attempt 與 task 狀態分開。由護理師確認的追蹤時間不等於系統已排程。

建議流程為草稿 → 人工批准 → scope 投影 → 待發送 → 送達狀態 → 回覆／需要追問；可失敗、取消或重開。需辨別平台接受發送、裝置送達與本人確認，不宣稱通道可提供它不支援的 receipt。

Done：兩種合成事件、到期跨重啟仍執行、重送冪等、取消不再發送、失敗可重試、撤銷授權後不能再發敏感內容、逾期任務有可查負責人。UI 沿用 Clinical Queue，不先新增另一套 worklist。

LINE Notify 已於 2025-03-31 停用；現有 repo 使用 Messaging API，保留這個方向，工作重點是上述狀態與失敗處理，不是換回舊服務。[LINE 官方公告](https://developers.line.biz/en/news/2025/04/01/line-notify/)

## 6. Twin 與問答共用證據，但不共用錯誤推論（M4/M5）

Twin current-state 候選欄位包含 observation 時間、as-of 時間、source reference、freshness、missing reason 及 projection 版本。歷史事件可以永久保存，但不能一直當成目前指標。3D 外觀維持示意，不等同生理預測。

問答先按病人與權限篩來源，再做時間／結構化查詢與文字檢索。每一項事實主張需引用支持它的原件片段；區分「來源明確否定」「未取得資料」「沒找到」「資料過期」「互相衝突」。不得將時序共現或 graph 的關聯改寫成原因。

Done：過期穿戴值不回為 current，停藥與現用藥可區別，否定與未知不混用，矛盾來源可並列，惡意文件指示不能覆蓋系統規則；評測包含跨病人／scope、source support 與拒答，而不只看引用 id 是否存在。

## 7. 效益評測：先量流程，不承諾固定省時百分比（並行）

首個合成案例研究可以選「照護者回報 → 護理確認 → 家屬摘要」。記錄完成時間、重打次數、人工改動率、關鍵資訊遺漏、確認負擔、通知或追蹤未完成率，保存分母、角色、案例難度與失敗例。小樣本只用來找問題，不能宣稱臨床安全或療效。

2026 年 JAMIA 的隨機交叉研究以門診使用者比較兩個 AI scribe，評估文件時間、工作流滿意度和 burnout；不是所有時間指標都改善。這支持使用多種實際工作指標，而非單憑模型 accuracy；不能外推成長照會得到相同收益。[原始研究](https://academic.oup.com/jamia/article/33/5/990/8494986)

模型與規則需保存版本、適用範圍、已知限制、評測樣本、變更審查、停用與回退機制。FDA 的 2025 lifecycle 文件目前仍為草案，只作國際治理方向參考，不當成台灣適用法規或本產品合規證明。[FDA 草案頁](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/artificial-intelligence-enabled-device-software-functions-lifecycle-management-and-marketing)

## 8. 未來預留，但暫不實作

專用影像、ECG 或傷口模型可經有界 adapter 接入：輸入品質、適用範圍、模型版本、輸出與原件 anchor、拒算／失敗、人類覆核彼此獨立。沒有合作資料、責任人及獨立驗證前，不新增自動診斷，不由 LLM 假造專用模型結果。

Health Graph 可先用有來源的關聯表；不以買齊圖庫、向量庫、時序庫作為 Done。基因風險、醫療影像推論、藥物發現與預測式 avatar 均不列入下一版。

## 9. 給下一位實作者的第一個工作包

從 HANDOFF 的 M1 開始：盤點所有 HTTP 入口 → 定義可信 session／actor → 逐病人 resource/action 授權 → 後端回應投影 → 負向測試。保留既有 UI 路由、正常帶與臨床圖。不得把本備忘一次拆成全部開工的七個重寫專案。
