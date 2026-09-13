# HANDOFF — 目前狀態與下一步

更新：2026-09-13。唯一正式工作目錄：`D:\Health AI Bridge\record-follows-person`。
Repo：https://github.com/chrisyang-c/record-follows-person

## 接手順序

1. 閱讀 `CLAUDE.md`、本頁、[PROJECT_REVIEW](PROJECT_REVIEW.md)。
2. 核對 `git status` 與遠端 main；保留既有未提交修改，避免覆蓋別人的同步工作。
3. [ARCHITECTURE](ARCHITECTURE.md) 管已採納規則，[ROADMAP](ROADMAP.md) 管分期；願景保留在 VISION。不得把外部提案當成已實作或已採納。

## 已完成的主線

- 原有 Path A/B、Care Circle、病人本人／照護者／護理師／醫師介面、來源與人工確認流程。
- 個人生理值統計正常帶與 RF13；臨床 baseline 不因統計更新而自動漂移。
- `512a402` 的 3D 分身、沙盤示意、合成穿戴每日指標、朗讀回答及本人自記已同步保留。
- `0ee23aa` 的正常帶 UI／API、Care Circle 與 access log purpose（授權必填、登入預設、UI 顯示）及六個整合測試已保留；本輪接續實作用途政策。
- M1/M2 本機版本：個人 credential、可撤銷 server-side session、CSRF／登入限流、病人／用途／scope HTTP 授權、後端資料投影、每病人代理管理與拒絕稽核。原始 clinical record/provenance 不因回應投影而被改寫。
- 舊紀錄升級使用個別設定密碼／明確重新授權工具，不重跑 seed、不替舊 grant 自動補用途；步驟與保守功能限制見 [SECURITY](SECURITY.md)。
- 整併來源與封存去向見 [CONSOLIDATION](CONSOLIDATION.md)；主專案不依賴工作區旁邊的資料夾。
- Windows `setup/test/check` 預設 API＋web；缺工具或已執行指令失敗不算通過。只有明確 `-ApiOnly` 才跳過前端。
- codegen `--check` 唯讀；`check` 的 mock eval 使用暫存輸出，不覆寫已保存的真模型評測。
- 測試／runtime smoke 可明確指定合成資料的近期 14 天視窗，另測過期 wearable 不被當成 current；預設 seed 原始歷史日期不改。
- 公開 [OPTIMIZATION_PLAN](OPTIMIZATION_PLAN.md) 補上來源品質、TW Core 切片、規則治理及通知／追蹤驗收；是設計備忘，不代表已實作。
- M3 第一版：timeline 寫入使用 transaction journal、原子替換、fsync、程序內 per-patient lock；下次讀／寫會恢復 provenance，並有途中失敗、重送、併發測試。
- M3 備份第一版：`scripts/backup_records.py` 產生 SHA-256 manifest、可驗證並預設還原到空隔離目錄；不取代加密異地 DR。
- M6 第一版：Path A 的 follow-up 同時建立去重的 `FollowUpTask`；`graphs.worker.scan_once()` 會將到期項目持久化為 `queued` 並寫 JSON outbox，保留 attempts 與 acknowledged 狀態。現在仍是 `displayed_only`，沒有假裝已送出 LINE。
- M4 第一版：`ingest/fhir_bundle.py` 支援合成 Patient + Observation Bundle 的 identity check、代碼／單位／時間正規化、bundle id 去重與可解析 export；不確定身份一律 `identity_unresolved`／`pending_review`，不直接寫 timeline。
- M5 第一版：Ask retrieval 加入常見中文同義詞、近 N 天／週／月時間窗與 `evidence_status`，回答仍逐句綁定 retrieve source id。
- M7 第一版：`scripts/preflight_security.py --production` 會在部署前阻擋 mock provider、缺 DB、非 Secure cookie、非 HTTPS origins、demo simulation 或 memory checkpoint fallback。

## 驗證入口

目前 HEAD `ef18b1cabb9208a70cf212d88567e5c5838db1b2` 已推送並通過本機全套、全新 clone 全套、PostgreSQL／Edge 登入隔離驗收及 GitHub 三個 CI job；詳細數據與限制見 [VALIDATION](VALIDATION.md)。舊帳號不會自動新增密碼或用途授權，使用前依 SECURITY 做明確設定，不使用 seed 當升級。

```powershell
.\scripts\dev.ps1 setup
.\scripts\dev.ps1 check
# 只做後端工作時可明確縮小範圍
.\scripts\dev.ps1 check -ApiOnly
```

`check` 驗證程式與型別，不等於 API/web/Postgres 的實際啟動或真模型效能。
當次結果、環境、重啟驗收與限制統一記在 [VALIDATION](VALIDATION.md)。
初始化及 seed/reset 會改變示範資料；請在獨立測試環境執行，不用來做日常「檢查」。

## 下一個工程里程碑

接續 ROADMAP 的 M3–M7 第二階段：跨程序／Postgres 寫入與備份還原、真正通知 provider 與 retry、HealthEvent 泛化、claim-level contradiction evaluation、OIDC／MFA／KMS／staging E2E。上述第一版切片只建立可驗收骨架，不把本機檔案、`displayed_only` 或 synthetic FHIR 說成 production。

後續工程要保留護理師設定與確認邊界，不擅自決定臨床追蹤次數。M1/M2 的 OIDC／MFA、組織身分、不可竄改稽核及多程序授權／寫入交易仍是部署前缺口，不因本輪通過而消失。
護理使用者的合成案例回饋並行，不作所有工程的前置。

## 已知限制與來源

目前仍是合成資料原型。本機 session／API 授權第一版已完成，但尚未達到正式部署條件；詳細證據見 PROJECT_REVIEW，
較早的限制與修正歷史在 KNOWN_ISSUES。不要把 API 單元測試全綠當成正式安全或臨床驗證。

環境變數只以 `.env.example` 為範本；本頁不宣稱任何人的 key、資料庫或 Docker 已設定。
封存的外部來源不是安裝條件；已複製資產的來源與許可見 `apps/web/public/models/LICENSE.txt`。
