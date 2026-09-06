# HANDOFF — 目前狀態與下一步

更新：2026-09-06。唯一正式工作目錄：`D:\Health AI Bridge\record-follows-person`。
Repo：https://github.com/chrisyang-c/record-follows-person

## 接手順序

1. 閱讀 `CLAUDE.md`、本頁、[PROJECT_REVIEW](PROJECT_REVIEW.md)。
2. 核對 `git status` 與遠端 main；保留既有未提交修改，避免覆蓋別人的同步工作。
3. [ARCHITECTURE](ARCHITECTURE.md) 管已採納規則，[ROADMAP](ROADMAP.md) 管分期；願景保留在 VISION。不得把外部提案當成已實作或已採納。

## 已完成的主線

- 原有 Path A/B、Care Circle、病人本人／照護者／護理師／醫師介面、來源與人工確認流程。
- 個人生理值統計正常帶與 RF13；臨床 baseline 不因統計更新而自動漂移。
- `512a402` 的 3D 分身、沙盤示意、合成穿戴每日指標、朗讀回答及本人自記已同步保留。
- `0ee23aa` 的正常帶 UI／API、Care Circle 與 access log purpose（授權必填、登入預設、UI 顯示）及六個整合測試已保留；用途政策尚未完成。
- 整併來源與封存去向見 [CONSOLIDATION](CONSOLIDATION.md)；主專案不依賴工作區旁邊的資料夾。
- Windows `setup/test/check` 預設 API＋web；缺工具或已執行指令失敗不算通過。只有明確 `-ApiOnly` 才跳過前端。
- codegen `--check` 唯讀；`check` 的 mock eval 使用暫存輸出，不覆寫已保存的真模型評測。
- 測試／runtime smoke 可明確指定合成資料的近期 14 天視窗，另測過期 wearable 不被當成 current；預設 seed 原始歷史日期不改。
- 公開 [OPTIMIZATION_PLAN](OPTIMIZATION_PLAN.md) 補上來源品質、TW Core 切片、規則治理及通知／追蹤驗收；是設計備忘，不代表已實作。

## 驗證入口

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

先做 ROADMAP M1，範圍為可信身分、病人隔離及所有讀寫入口的後端授權：
- 移除未提供身分時退回 nurse／預設角色的通路。
- 完整覆蓋 records、summary、conversation、threads/resume、授權／撤銷及 debug/trace。
- API 回應在後端依允許欄位投影，不能只回 allowed_tabs 再由 UI 隱藏。
- 病人或家屬的角色不等於可以管理任意病人的 Care Circle。
- 以跨病人、撤銷、過期、偽造角色與未授權寫入回歸測試驗收。

然後做 M2 purpose／政策與稽核；M3 存取契約與可回復性；其餘依 ROADMAP。
護理使用者的合成案例回饋並行，不作所有工程的前置。

## 已知限制與來源

目前仍是合成資料原型。登入與 API 權限尚未達到正式部署條件；詳細證據見 PROJECT_REVIEW，
較早的限制與修正歷史在 KNOWN_ISSUES。不要把 API 單元測試全綠當成正式安全或臨床驗證。

環境變數只以 `.env.example` 為範本；本頁不宣稱任何人的 key、資料庫或 Docker 已設定。
封存的外部來源不是安裝條件；已複製資產的來源與許可見 `apps/web/public/models/LICENSE.txt`。
