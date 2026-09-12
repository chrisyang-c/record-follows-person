# 驗證紀錄

## 2026-09-12 — 本機身分與病人隔離

本輪只使用 mock 與合成資料，未清空主專案 records、未修改使用者 `.env`、未呼叫付費模型或外部通知。個人 session、用途／scope、後端投影及遷移契約見 [SECURITY](SECURITY.md)。下方 9/6 表格保留歷史，不是這輪結果。

- API 全套：190 個測試通過（含 35 個 HTTP policy、12 個 credential/session 測試）；有一則上游 Starlette/AnyIO deprecation warning，無測試失敗。
- `.\scripts\dev.ps1 check` 全套 exit 0：API 190、web 11、Windows tooling 12 個測試通過，Ruff／ESLint／codegen 同步、正式 Next.js build（20 頁產生）與 `tsc --noEmit` 通過。mock eval 為 46 句、多抽 2/46、漏抽 0/46、來源子字串 46/46、誘導句 5/5；不代表真模型品質。
- 隔離 PostgreSQL 17／mock HTTP 驗證通過：session 與待審核 interrupt 跨 API 重啟保留；護理師核准後再次重啟，approved timeline 與 provenance 仍存在；未登入及照護者核准被拒絕。
- Headless Edge 正式版驗證通過：偽造舊 cookie 無效、個人密碼登入 P003、取得自身 health ID／14 天 wearable、跨病人 P001 回 403、不洩露其 health ID、登出後 protected page 轉登入且 API 回 401。登入後相對跳轉沒有切換 localhost／127.0.0.1。
- GitHub CI 與 fresh clone：尚未以本輪提交驗收，提交後另記實際結果。
- UI 程式稽核與未驗項目見 [UI_AUDIT](UI_AUDIT.md)。本輪不包含真模型品質、所有角色完整臨床流程或正式安全評估。

## 歷史：整併驗證 — 2026-09-06

應用程式基準 `512a402`，加上本輪工具／文件修正；精確交付版本以包含本文件的 Git commit 為準。只用合成資料與 mock provider，不呼叫付費模型、不發 LINE、不重設原專案 records 或資料庫。

## 已完成

| 檢查 | 本輪結果 |
|---|---|
| 鎖定相依安裝 | API `uv sync --frozen`、web pnpm 10.12.1 `install --frozen-lockfile` 成功 |
| API ruff check／format | 通過；71 個檔案格式一致 |
| API pytest | 134 個通過 |
| web eslint／Vitest | 通過；2 個 test files、3 個測試 |
| Windows 開發工具回歸 | 12 個通過；包含缺 pnpm、執行失敗、API-only、check 順序與不覆寫 dirty codegen |
| mock extraction gate | 46 句；多抽 2/46、漏抽 0/46、來源子字串 46/46、誘導句 5/5；結果寫暫存，不覆寫歷史真模型報告 |
| codegen `--check` | 與 Pydantic 同步；唯讀比對 |
| Next.js production build → TypeScript | 通過 |
| 真實 API＋PostgreSQL | 獨立 PostgreSQL 17、HTTP Path B 到護理師確認 interrupt；API 重啟後仍可讀取與批准；再次重啟仍能讀到 done 與 approved timeline／provenance |
| 真實瀏覽器讀取 | Headless Edge 載入正式版 `/twin?pid=P003`，收到 API 的合成病人 health_id 與 14 天 wearable 資料 |
| 工作區移除旁邊相依 | `D:\Health AI Bridge` 只剩主 repo；封存檔案核對見 CONSOLIDATION |

此處的瀏覽器測試使用現有 demo cookie，只證明頁面與 API 接線；不驗證登入安全，不宣稱全頁視覺、語音、3D 動畫或所有角色流程已驗收。

## 可重現指令

Windows 使用 PowerShell 7、Python 3.12／uv、Node 24／pnpm 10.12.1：

```powershell
git clone https://github.com/chrisyang-c/record-follows-person.git
Set-Location record-follows-person
.\scripts\dev.ps1 setup
.\scripts\dev.ps1 check
```

完整 check 缺 pnpm 或任何已執行步驟失敗必須非零退出。`check -ApiOnly` 會明確標示前端未驗證，不能取代上面指令。macOS/Linux 可在安裝相依後用 `make check`；Windows 工具測試在非 Windows 跳過，另由 CI 的 windows-tooling job 執行。

### 隔離啟動驗證（需要 Docker；勿使用真資料庫）

以下只建立新的一次性容器，port 15432、8000、3000 必須空閒。密碼只供此一次性本機測試；不讀取正式服務的 secrets。

```powershell
docker run --detach --rm --name rfp-smoke --publish 127.0.0.1:15432:5432 --env POSTGRES_USER=rfp --env POSTGRES_PASSWORD=rfp_smoke_only --env POSTGRES_DB=rfp_smoke postgres:17-alpine
# 等 pg_isready 回報 accepting connections 再繼續
docker exec rfp-smoke pg_isready -U rfp -d rfp_smoke
$env:RFP_SMOKE_DATABASE_URL = 'postgresql://rfp:rfp_smoke_only@127.0.0.1:15432/rfp_smoke'
Push-Location apps/api
try {
    uv run --frozen python ../../scripts/smoke_runtime.py --web
} finally {
    Pop-Location
    docker stop rfp-smoke
    Remove-Item Env:RFP_SMOKE_DATABASE_URL
}
```

`--web` 需要先完成 web build，以及已安裝 Edge（或以 `RFP_BROWSER_CHANNEL` 指定已安裝的 Playwright channel）。不加 `--web` 只驗 API／Postgres。腳本拒絕非 localhost 或資料庫名稱不以 `rfp_smoke` 開頭的連線；這只是防誤用，仍須由操作者確認它是可丟棄的獨立資料庫。

## 全新 clone 與遠端 CI

上表是合流前 `512a402` 的實測。提交前又收到夥伴 `0ee23aa`，已保留其正常帶 UI、purpose 與新增測試；交付前以合流版本在工作區外 fresh clone 重跑，結果會補記於此。GitHub CI 分 API、web、Windows tooling；本機通過不代表遠端通過，需核對相同 commit 的 workflow run。

## 未驗證／尚未完成

- 真模型本輪未重跑；README 保存的 2026-09-05 模型比較是歷史小樣本，不是本次結果。
- 沒有連接醫院、真裝置、真通知或真實病人；沒有臨床有效性／安全性驗證。
- 不是完整 Path A、巡診、護理追蹤、列印與每個角色的瀏覽器端到端套件。
- PostgreSQL 可用時的流程持久化通過，不代表資料庫故障降級、多程序併發或正式備份還原已完成。
- 認證、跨病人授權、用途政策、claim-level evidence 等仍未修；見 [PROJECT_REVIEW](PROJECT_REVIEW.md)。
- 沒有執行 `init/reset/seed/clean-records` 去清理主專案資料；自訂 DB／RECORDS_ROOT 的破壞性指令限制見 KNOWN_ISSUES #47。
