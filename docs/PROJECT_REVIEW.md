# 專案 review — 整併後的優先補強

## 2026-09-13 複核：接下來最值得補的內容

本次複核後已完成下列第一版切片：`RecordStore` timeline 交易 journal／恢復與程序內併發鎖、可持久化 follow-up task/outbox、帶時間窗與同義詞的 evidence retrieval、合成 FHIR Bundle 匯入／匯出，以及 production preflight。這些是可驗收的骨架，不代表已完成機構 IdP、真正通知或完整 FHIR server；正式部署缺口仍見 SECURITY。

1. **M3 第一版已完成，下一步是跨程序備份／還原。** `record/store.py` 以 journal、原子替換、fsync 與程序內鎖保護 timeline＋provenance；仍不是多程序資料庫交易，也尚未提供排程備份。
2. **M6 第一版已完成，下一步是真通知與通用 HealthEvent。** `record/followups.py` 會去重、到期 queue、寫 outbox、保留 attempts，並提供 nurse-only follow-up read API；目前 delivery 是 `displayed_only`，尚未接 LINE／push retry。
3. **M5 已補時間窗、常見中文同義詞與 evidence status。** Ask 回答現在帶 `evidence_status`／`query_window`；仍是 deterministic lexical retrieval，尚未做 embeddings、claim-level contradiction engine。
4. **M4 已完成合成 FHIR collection/batch/transaction Bundle slice。** `ingest/fhir_bundle.py` 保存 raw bundle、代碼／單位／時間正規化、bundle 去重與可解析匯出；身份不確定或 observation subject 不符時停在 review，不自動寫 timeline。
5. **M7 已加入 fail-closed preflight。** `scripts/preflight_security.py --production` 會檢查真模型、資料庫、Secure cookie、HTTPS origins、停用 demo 與 memory fallback；OIDC／MFA、KMS、DR、完整 proxy hardening 仍待完成。

近期建議先交付第 1 項的小範圍資料契約與故障恢復測試，再補第 2 項追蹤派送。若要對外部署或接真資料，第 5 項是前置條件，不可因排在此清單最後而延後。

## 2026-09-10 修復狀態

以下 9/6 的證據保留為歷史快照，不代表目前程式仍有相同通路。§1–4 已加入本機個人 session、集中式 HTTP 授權、實際資料投影、每病人管理資格、固定用途及拒絕稽核；程式與回歸測試見 `core/security.py`、`core/policy.py`、`test_security.py`、`test_http_policy.py`。限制與不清資料的升級步驟見 [SECURITY](SECURITY.md)，實測狀態見 [VALIDATION](VALIDATION.md)。這不是 P0 全部解除或正式部署核准。

接下來進入 M3–M7 的第二階段：跨程序／Postgres 儲存與備份、真正通知 provider／retry、HealthEvent 泛化、完整 claim-level contradiction evaluation，以及 OIDC／MFA／KMS／staging E2E。不要因已有本機登入、FHIR slice 或 preflight 就直接接真實病人。

> **本節以下的讀法（2026-09-13）**：第 1–4 節保留 9/6 的 P0／P1 問題證據，方便理解修復前後差異；其中「補強」與「驗收」描述的是當時待辦。現在已完成的是本機 M1/M2 第一版，並非正式身分治理。最新已完成切片與剩餘缺口以本頁開頭、[HANDOFF](HANDOFF.md) 和 [VALIDATION](VALIDATION.md) 為準。

## 9/6 歷史檢查基準

日期：2026-09-06。應用程式檢查基準：`0ee23aa`（含夥伴最新合流的正常帶 UI、purpose 欄位與六個整合測試）；本輪修正開發工具與文件，沒有把下列產品缺口宣稱為已修復。驗證證據見 [VALIDATION](VALIDATION.md)，實作順序見 [ROADMAP](ROADMAP.md)。

目前已形成一個有病人主體、照護流程、人工審核與來源資料的合成原型。下一步的重點是可信存取、可回復的紀錄與真正跨來源的資料能力。3D 分身與 UI 不是平台完整性的衡量方式。

## 優先度

P0：在真實資料或對外部署前必須處理的存取問題。P1：進一步開發平台時的可靠性與核心能力。P2：需要合作方或產品證據再擴充。以下是 review 與待辦，不是安全認證或臨床驗證。

## 1. P0 歷史基線（本機 M1 第一版已修，正式 IdP 尚未完成）— 身分未驗證，讀寫與人工審核入口未一致保護

證據：`apps/api/main.py::_authorize` 在沒有 `X-Who` 時使用角色預設 scope，沒角色則回 nurse；`/records/{patient_id}`、`/patients/{id}/conversation`、`/threads/{thread_id}/resume` 等路徑沒有一致的認證檢查。web 傳入 `X-Who`／`X-Role` 的方式見 `apps/web/lib/api.ts::roleHeader`。

影響：身份與角色可以由請求宣告；有人工確認欄位不表示請求實際來自有權確認的護理師。只修 `/role` 網頁不足以堵住直接 API 請求。

補強：共用後端身分驗證 dependency；伺服器簽發／驗證 session，權限從可信身分與該病人的有效關係取得；逐一覆蓋讀取、修改、流程 resume、模擬器、debug 與 trace 入口。先建立 session 契約，之後可接 OIDC。

驗收：未登入、偽造 header、過期 session、跨病人、無護理角色 resume 全部拒絕；合法流程仍通過。以 HTTP 層測試，不只直接呼叫 Python 函式。

## 2. P0 歷史基線（本機 M1/M2 第一版已修，細粒度政策仍待完成）— scope 需要在後端限制實際回傳內容

證據：`apps/api/main.py::patient_summary` 回傳 `allowed_tabs`，同時組裝 profile、baseline、timeline、documents、conversation；部分來源篩選含 `or True`。`/records/{patient_id}` 也能整份載入。

影響：前端隱藏 tab 不會移除 HTTP 回應已傳送的內容，可能超出成員被授權的資料範圍。

補強：先以 resource/action 判定授權，再用角色與 scope 對應的回應型別投影。列表、摘要、下載、搜尋、trace 都需沿用相同規則，檢索前也要限制可讀來源。

驗收：僅有 talk 的成員拿不到 timeline/docs；限制影響回應 JSON 本身。拒絕結果及存取決策也需記錄，且日誌不能洩漏被拒絕的內容。

## 3. P0 歷史基線（本機 M2 第一版已修，正式代理治理仍待完成）— 病人的代理資格不能只看全域角色

證據：`apps/api/record/care_circle.py::role_of` 找不到該病人的圈內關係時會退回 identity 的全域角色；`main.py` 的 grant/revoke 以 patient/family 角色判斷。

影響：某人的 patient 或 family 角色，不代表可以管理另一個人的授權。

補強：明確區分本人、具有有效代理權的家屬與其他關係；授權／撤銷必須檢查 actor 與目標病人的關係及可委派上限。

驗收：A 的本人或家屬不能授權讀 B；已撤銷／到期的代理不能再建立授權；所有授權變更保留 actor、目標、原因及版本。

## 4. P1 歷史基線（本機 M2 第一版已修，完整同意生命週期仍待完成）— purpose 要有政策語意與舊資料遷移

證據：`0ee23aa` 已在 CareCircleMember、AccessLogEntry 補 purpose，grant 要求非空、登入依角色預設、UI 顯示用途。`record/care_circle.py::log_access` 取既有 grant 的 purpose 或角色預設；沒有 per-request purpose 的比對／拒絕。沒有 who 時直接返回，並非每次請求都有稽核。這是已完成基礎欄位、尚未完成用途政策，不再列為「缺欄位」。

補強：授權的 allowed purposes 與每次宣告的 purpose 分開；後端檢查是否相符。用途不應只是一個使用者任填的字串。補上 decision、reason、request_id、grant/version reference，稽核授權修改與拒絕。

驗收：允許和不允許的用途各有 HTTP 案例；過期、撤銷及舊資料的未指定用途不自動擴權；歷史記錄能讀取且明確標示當時用途未知。

## 5. P1 — PersonRecord 存取層還不是完整的交易與儲存抽象

證據：`record/store.py::write_timeline` 現在先寫 transaction journal，再以原子替換＋fsync 寫 timeline，最後逐筆寫 provenance；讀／寫會恢復未完成 journal，並以 per-patient 程序內鎖防止同程序競爭。`scripts/backup_records.py` 可產生 manifest 並還原到隔離目錄。事件、對話、Care Circle 仍直接組合目錄路徑；跨程序資料庫交易尚未完成。`graphs/checkpointer.py` 只有明確設定 `ALLOW_MEMORY_CHECKPOINT_FALLBACK=true` 才允許 DB 失敗降級。

影響：第一版已涵蓋 timeline＋provenance 的單程序故障／重送／併發契約，但不等於全系統多檔案原子交易，也不等於加密異地 DR。只替換 store.py 不能完成全系統資料庫遷移。

補強：下一步列出所有檔案直接存取點，建立 repository 介面、版本／更正／冪等鍵；把目前 manifest backup 擴充為加密異地備份與還原演練，逐步接 Postgres 權威儲存及原件儲存。正式模式對 DB 不可用會明確失敗，不能仍宣稱已持久化。

驗收：寫入途中失敗可恢復、重送不重複、併發不遺失；紀錄與來源一致；備份還原可核對。workflow checkpoint 與病歷儲存分開驗證。

## 6. P1 — 通知、追蹤與事件生命週期要真正閉環

證據：目前 SensorEvent、`record/events.py` 與 Path A/B 共存。`schedule_follow_up` 讀護理 review 的 `follow_up_hours`（預設 4），保存 due_at/question/set_by 並建立去重的 `FollowUpTask`；`graphs/worker.py::scan_once` 現在會將到期 pending task 轉為 queued 並寫 JSON outbox，`/records/{patient_id}/follow-ups` 與 ack endpoint 供護理師查看／回覆。delivery 仍明確是 `displayed_only`，不是實際送達。

補強：把目前 FollowUp outbox 泛化成 HealthEvent 與 care task 的關係、角色轉換、誤報／取消／重開；接真正 provider 時加入 retry／DLQ／delivery receipt。護理師設定時間、到期 queue、收回回覆與關閉的第一版已完成。

驗收：除跌倒外至少一種合成事件走完；通知失敗重試不重複送；追蹤跨重啟仍到期執行；非授權角色不能推進人工節點。不得用單一路徑強迫所有事件先驗證再通知。

## 7. P1 — 長期查詢需要時間、矛盾與逐句證據檢查

證據：Ask My Record 仍是 lexical bigram，但已加入常見中文同義詞、近 N 天／週／月時間窗、`evidence_status` 與來源片段重疊核對；這不等於 embeddings、structured graph 或完整跨來源衝突評測。

補強：接著加入結構化 query、原件 anchor 與真正 hybrid retrieval；目前已分開標記無資料／未找到／指定期間外／簡單矛盾，仍需 medication state、否定與跨來源 contradiction engine。找不到證據的措辭不能暗示事件確定沒發生。

驗收：病人／scope 預過濾、時間範圍、停藥與現用藥、矛盾、提示注入與跨病人案例；來源不只存在，還必須支持該句。評測應分開報 mock、真模型與人工裁決。

## 8. P1 — 缺少一條真正可驗收的外部資料匯入／匯出

證據：`ingest/discharge_pdf.py` 仍是固定合成摘要；新增 `ingest/fhir_bundle.py` 支援合成 Patient + Observation collection/batch/transaction Bundle，保存 raw bundle、來源、時間、單位與 normalized observations，FHIR-like 命名以外的第一條 adapter 已可執行。

補強：把目前 adapter 的 import version、錯誤報告與更正流程補齊，再評估 TW Core 資源與真正來源。重點仍是查到來源與可重播，不一次建立所有資料庫。

驗收：支援範圍明確；重複匯入冪等；未知代碼與不確定同人不自動合併；更正不抹去歷史；能匯出另一套程式可解析的資料。

## 9. P2 — Twin 的目前狀態、裝置品質與 3D 示意要分開

證據：`512a402` 的 WearableDaily 來自 seed；`main.py::twin` 取最近指標，分身 mood 由變化／紅燈決定，外觀是規則示意。`apps/web/components/twin/avatar-model.tsx` 不是經驗證的生理或心理預測模型。

補強：建立 latest observation 時間、freshness、missing、device/source、資料品質與校正 metadata。真裝置先接一款，處理 pairing、時鐘偏移、缺值、重送和離線；UI 準確區分模擬、示意與實測。

驗收：過期／缺資料不顯示成正常即時數值；新裝置資料進入既有授權及來源流程；外觀不暗示診斷或因果預測。

## 10. P1/P2 — 營運與驗收證據需能持續重現

本輪已修 check 失敗傳遞、格式檢查與唯讀 codegen；加入腳本回歸、PostgreSQL 重啟 smoke，仍不等於 production hardening。

補強：版本化 migration、環境隔離、secret 管理、速率限制、可查詢稽核、備份／還原、workers 與通知監控；資產逐項保留來源及使用許可證據。文件中舊的測試數、模擬範圍與機器環境要以當次驗證取代。

驗收：CI 失敗不能偽裝成跳過；staging 使用固定版本與合成案例可重現；能回答當時用了哪個資料／模型／規則版本，以及故障後如何恢復。

## 建議下一個可交付版本

在保留現有 UI 與臨床人工閘門的前提下，優先完成 M3–M7 第二階段：跨程序儲存／備份還原、真正通知與 retry、通用 HealthEvent、claim-level contradiction evaluation，以及 OIDC／MFA／KMS／staging E2E。使用者訪談可並行調整優先序，但不取代上述工程驗收。

來源封包、台灣 FHIR 最小切片、規則治理、家屬溝通、Twin freshness 及效益評測的候選契約，見 [OPTIMIZATION_PLAN](OPTIMIZATION_PLAN.md)。它補充設計細節，不另開一條互相競爭的 roadmap。
