# 目錄與文件指南

> 審閱日期：2026-09-13。這份文件把正式 repo 的資料夾、文件用途與「哪一份才是目前真實狀態」集中說清楚。

## 先記住三件事

1. 唯一正式程式專案是本 repo：`record-follows-person`。
2. `docs/` 的文件不是同一種性質：有些是現行契約，有些是歷史證據，有些是長期願景或未採納提案。
3. 目前的實作狀態以 `docs/HANDOFF.md`、`docs/VALIDATION.md`、程式與同一 commit 的 CI 為準；不要只看舊的 demo 驗收紀錄。

---

## 閱讀順序與文件權威

| 順序 | 文件 | 主要用途 | 性質 |
|---:|---|---|---|
| 1 | [`docs/BEGINNER_GUIDE.md`](BEGINNER_GUIDE.md) | 白話版產品介紹、名詞、啟動方式與安全底線 | 初學者入口 |
| 2 | [`CLAUDE.md`](../CLAUDE.md)；`apps/web/AGENTS.md` | coding agent 規則、不可違反的安全與 UI 邊界 | 開工必讀的規則 |
| 3 | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) | 已採納的層級、資料流、Path A/B、人工閘門與 demo 範圍 | 架構契約 |
| 4 | [`docs/SECURITY.md`](SECURITY.md) | 本機帳號、session、病人／purpose／scope 授權、資料升級與安全限制 | 目前安全契約 |
| 5 | [`docs/HANDOFF.md`](HANDOFF.md) | 已完成主線、下一個里程碑、目前限制與接手方式 | 最新交接狀態 |
| 6 | [`docs/VALIDATION.md`](VALIDATION.md) | 可重現指令、實測結果、CI、runtime smoke 與未涵蓋項目 | 驗證證據 |
| 7 | [`docs/ROADMAP.md`](ROADMAP.md) | 分期、完成條件、暫緩項目與使用者驗證 | 下一步計畫 |
| 8 | [`docs/PROJECT_REVIEW.md`](PROJECT_REVIEW.md)；[`docs/KNOWN_ISSUES.md`](KNOWN_ISSUES.md) | 有程式證據的風險、剩餘缺口、繞法與優先序 | review／限制 |
| 9 | [`docs/OVERVIEW.md`](OVERVIEW.md)；[`docs/一份能跟著人走的紀錄_摘要與願景.md`](一份能跟著人走的紀錄_摘要與願景.md) | 給第一次接觸者的產品故事、角色與長照情境 | 敘事說明 |
| 10 | [`docs/VISION_personal_health_twin.md`](VISION_personal_health_twin.md) | Personal Health Twin 長期願景與未來平台方向 | 願景，不是完成清單 |
| 11 | [`docs/ACCEPTANCE.md`](ACCEPTANCE.md)、`docs/TRACE_*.md`、[`docs/UI_AUDIT.md`](UI_AUDIT.md) | 2026-09-05～09-12 的 demo、trace 與 UI 審查證據 | 歷史／補充證據 |
| 12 | [`docs/OPTIMIZATION_PLAN.md`](OPTIMIZATION_PLAN.md)；[`docs/proposals/00-architecture.md`](proposals/00-architecture.md) | 優化候選與外部提案 | 設計備忘；提案未採納 |

遇到文件互相矛盾時，不把舊數字或舊截圖當成現況；先回到 `HANDOFF`、`VALIDATION`、程式與 CI。`VISION` 和 `proposals` 不能直接當成已實作功能。

### 為什麼不是每個資料夾都各放一份 README？

目前採「一份集中目錄指南＋高風險目錄保留原生規則檔」的方式，避免 API、web、schema 各自複製一份會逐漸過期的說明。需要特別規則的地方才保留獨立檔案：repo 根目錄的 `CLAUDE.md`、web 的 `AGENTS.md`／`CLAUDE.md`、設計系統的 `MASTER.md`、以及 `docs/` 的各種契約與證據文件。這不是缺少文件；本頁就是所有資料夾的導覽入口。

---

## 根目錄與支援設定

| 資料夾／檔案 | 放什麼 | 使用規則 |
|---|---|---|
| `.claude/` | Claude Code 的本機啟動設定與 vendored `web-design-guidelines` skill | 只影響 agent 工作方式；修改 skill 前要確認來源與授權 |
| `.github/workflows/` | GitHub CI：API + PostgreSQL、web、Windows tooling 三個 job | 每次 push／PR 的自動驗收；以同一 commit 的結果為準 |
| `apps/` | 可執行的 API 與 web 應用程式 | 功能修改主要在這裡，依各子目錄說明操作 |
| `data/` | 可重建的 synthetic seed 輸入 | 不放真實病人資料；`seed` 會清除／重建 records |
| `design-system/` | 原始 UI 設計產物 | `design-system/.../MASTER.md` 已明確標示被 `docs/design.md` 與 `CLAUDE.md §7` 覆寫 |
| `docs/` | 架構、交接、驗證、設計、願景與歷史證據 | 先看本指南，再依閱讀順序選文件 |
| `local-notes/` | 本機私人閱讀筆記，目前為演講精讀筆記 | 由 `.git/info/exclude` 排除；不要公開、不要當成可 clone 的文件 |
| `packages/` | API 與 web 共用的資料 schema | Pydantic 是來源，TypeScript 由 codegen 產生 |
| `scripts/` | Windows 入口、資料備份、preflight、smoke 與腳本測試 | 優先使用 `scripts/dev.ps1`；破壞性指令先確認目標 |
| `.env.example`、`docker-compose.yml`、`Makefile` | 環境範本、PostgreSQL 服務與跨平台命令 | `.env` 不入 Git；設定與安全限制見 `SECURITY.md` |

以下是被 Git 忽略的執行期／產生物，不是要手動維護的產品目錄：`.git/`、`.venv/`、`node_modules/`、`.next/`、`__pycache__/`、`.pytest_cache/`、`.ruff_cache/`、`records/`、`apps/web/out/`。

---

## `apps/api/`：FastAPI 後端

`apps/api/main.py` 是 HTTP 入口；後端負責 API、LangGraph、個人 agent、資料寫入、授權、紅燈規則與背景 worker。Python 版本與套件鎖定在 `apps/api/pyproject.toml`／`uv.lock`。

| 資料夾 | 責任 | 代表內容 |
|---|---|---|
| `apps/api/agents/` | 每位住民的 personal deep agent 與比較器 | `personal.py`、`comparator.py`、`subagents/` |
| `apps/api/agents/subagents/` | 趨勢、熟悉化與 handoff 的結構化子代理 | `trend_analyzer.py`、`familiarization_writer.py`、`handoff_packager.py` |
| `apps/api/baseline/` | 讀取與計算臨床 baseline、vitals 正常帶 | `loader.py`、`stats.py`、`vitals_band.py`；測試在同一目錄 |
| `apps/api/core/` | 共用基礎：設定、LLM factory、session/security、policy、trace、usage、去識別化、ID | 任何模型呼叫先看 `llm.py` 與 `settings.py`；授權先看 `policy.py`／`security.py` |
| `apps/api/eval/` | 抽取評測資料、執行器、結果與 trace 轉換 | `results.md` 是保存的歷史真模型結果；`check` 使用 mock gate |
| `apps/api/graphs/` | LangGraph 流程與 checkpointer／registry／worker | `path_a.py` 急症、`path_b.py` 日常巡診、`talk.py` 對話、`worker.py` 追蹤派送 |
| `apps/api/ingest/` | 照護者語音／文字、醫囑、出院 PDF、vitals 與合成 FHIR Bundle 的輸入轉換 | `fhir_bundle.py` 是第一條合成外部資料切片，不是完整 FHIR server |
| `apps/api/record/` | PersonRecord 讀寫、timeline journal、provenance、Care Circle、事件與 FollowUp | `store.py` 是寫入可靠性核心；`timeline_write` 保持核准閘門 |
| `apps/api/red_flags/` | 純程式紅燈規則與測試 | 不呼叫 LLM；規則命中後交護理師確認，不是診斷 |
| `apps/api/tests/` | API、流程、授權、資料、重啟與安全回歸測試 | 新功能先補這裡；測試不得用真病人資料或真通知 |

### API 的資料邊界

- `records/{patient_id}/` 是每位住民的執行期資料，已被 `.gitignore` 排除，不應 commit。
- `apps/api/record/` 是目前的 domain／存取抽象；M3 已有 journal、原子替換、fsync、單程序病人鎖與恢復測試，但不等於完成跨程序交易或正式 DR。
- Postgres 主要保存 LangGraph checkpointer／thread registry；它不是把所有病歷欄位自動搬進關聯資料庫。

---

## `apps/web/`：Next.js 前端

前端使用 Next.js App Router、TypeScript strict、Tailwind 與 OMNI-TWIN 外殼。修改前先讀 [`apps/web/AGENTS.md`](../apps/web/AGENTS.md)；`apps/web/CLAUDE.md` 只是引用它。

| 資料夾 | 責任 |
|---|---|
| `apps/web/app/` | 路由與頁面；路由是 `/login`、`/me`、`/caregiver`、`/nurse`、`/doctor`、`/p/[id]`、`/twin`、`/trace`、`/about` 等 |
| `apps/web/app/me/` | 本人艙：首頁、timeline、events、Care Circle |
| `apps/web/app/nurse/` | 護理站與巡診頁 |
| `apps/web/app/twin/` | 活體數位孿生主頁與 aesthetics／emotion／wealth 子頁 |
| `apps/web/app/p/` | 病人頁路由的父目錄；實際頁面在 `p/[id]/`，空的父目錄不是遺漏功能 |
| `apps/web/components/` | 可重用 UI 與角色元件：patient、nurse、twin、shell、auth、ui |
| `apps/web/lib/` | API client、session、role、labels、format、polling 與共用前端邏輯 |
| `apps/web/public/anatomy/` | 解剖 SVG 與對應 license；視覺熱點是示意，不是臨床定位 |
| `apps/web/public/models/` | 3D avatar 與對應 license；模型較大且目前沒有完整 idle 動畫 |
| `apps/web/scripts/` | Playwright 截圖腳本；不是產品 runtime |

前端的 `lint`、Vitest、`build`、`typecheck` 都由 `scripts/dev.ps1 check` 與 CI 驗證。不要只靠隱藏頁籤判斷授權，後端 policy 才是資料邊界。

### Web 路由資料夾逐一對照

| 路由資料夾 | 入口 | 內容 |
|---|---|---|
| `app/about/` | `/about` | 專案說明／產品脈絡 |
| `app/login/` | `/login` | 個人帳號登入與用途選擇 |
| `app/caregiver/` | `/caregiver` | 照護者住民清單與今日入口 |
| `app/doctor/` | `/doctor` | 醫師巡診清單；詳細頁由 route link 進入 |
| `app/nurse/`、`app/nurse/round/` | `/nurse`、`/nurse/round` | Clinical Queue、事件審核與巡診準備 |
| `app/me/`、`app/me/timeline/`、`app/me/events/`、`app/me/circle/` | `/me`、`/me/timeline`、`/me/events`、`/me/circle` | 本人艙、終身時間軸、本人事件與 Care Circle |
| `app/p/`、`app/p/[id]/` | `/p/{id}` | 病人資料頁的父目錄與動態住民頁；`p/` 沒有獨立 page 是正常的 |
| `app/role/` | `/role` | 舊 demo 導航相容路徑；不可把它當成身分驗證入口 |
| `app/trace/` | `/trace` | 已授權的 agent／流程 trace 視圖 |
| `app/twin/`、`app/twin/aesthetics/`、`app/twin/emotion/`、`app/twin/wealth/` | `/twin` 及子頁 | 活體數位孿生與示意性擴充艙；不代表臨床預測 |

`components/` 的子目錄也有固定責任：`auth/` 登入與 session、`nurse/` 護理流程、`patient/` 病人頁分頁與資料投影、`shell/` 全站外殼、`twin/` 分身／趨勢視覺、`ui/` 基礎元件；沒有子目錄的元件檔是跨角色共用元件。

---

## `data/seed/`：合成資料

- `residents.json`：三位 demo 住民的 profile、baseline、歷史事件與關係資料。
- `seed.py`：清除並重新建立 `records/` 的 synthetic dataset；只適用於可丟棄的示範環境。
- seed 不是資料庫 migration，也不是既有資料升級工具。既有帳號／授權升級請看 `docs/SECURITY.md` 的管理腳本。

---

## `packages/schema/`：跨 API／web 的單一資料契約

- `record_schema/models.py`：Pydantic v2 的 Python 權威 schema。
- `codegen.py`：把 Python schema 產生為 TypeScript；`--check` 是唯讀同步檢查。
- `ts/index.ts`：產生的前端型別，不要只改產生檔而跳過 Python 來源。
- `record_schema/` 是 Python package；`ts/` 是產生的 TypeScript package。兩者都由 `packages/schema/pyproject.toml`／`codegen.py` 管理。
- 修改欄位時要一起更新測試、API 投影、前端使用處與 codegen，最後跑完整 `check`。

---

## `scripts/`：可重現的開發與維運入口

| 檔案 | 用途 |
|---|---|
| `dev.ps1` | Windows 主入口：setup、test、lint、check、api、web、worker、migrate、status 與明確標示的破壞性指令 |
| `backup_records.py` | 產生／驗證 SHA-256 manifest，並還原到空隔離目錄 |
| `preflight_security.py` | production 設定 fail-closed 檢查 |
| `manage_credentials.py` | 為既有本機帳號設定密碼；不在命令列放密碼 |
| `manage_consent.py` | 預覽／套用明確的病人授權、purpose、scope 與期限 |
| `smoke_runtime.py`、`smoke_browser.mjs` | 隔離 PostgreSQL、API 重啟與瀏覽器路徑驗證 |
| `check_eval.py` | 使用暫存輸出執行 mock extraction gate，不覆寫歷史真模型結果 |
| `scripts/tests/` | Windows tooling 的失敗傳播、ApiOnly、codegen 與清理邊界回歸測試 |

---

## `docs/`：文件逐一說明

| 文件 | 讀者與用途 | 目前應如何理解 |
|---|---|---|
| `BEGINNER_GUIDE.md` | 完全第一次接觸專案的人：產品、角色、資料流程、啟動與名詞 | 白話入口；先讀這份再看技術文件 |
| `OVERVIEW.md` | 第一次理解產品、四種角色、一次事件與安全紅線 | 敘事全貌；部分例子沿用 2026-09-05，現況回看 HANDOFF／VALIDATION |
| `ARCHITECTURE.md` | 產品架構、PersonRecord、Path A/B、agent、人工閘門與 demo 範圍 | 已採納架構；內文的日期狀態註記要一起看 |
| `CONSOLIDATION.md` | 外層資料夾整併、來源去向、封存驗證與獨立 clone 邊界 | 2026-09-13 的目錄整併證據 |
| `DECISIONS.md` | 每個重要決定的日期、理由與決策者 | 歷史決策 ledger；新決定應追加，不要改寫舊紀錄 |
| `HANDOFF.md` | 接手順序、完成主線、下一個里程碑與限制 | **目前最重要的交接文件** |
| `KNOWN_ISSUES.md` | 已知問題、影響、狀態與繞法 | 只保留仍有效的限制；已修項目必須標明修復版本 |
| `OPTIMIZATION_PLAN.md` | 來源品質、FHIR 切片、證據、通知與使用者驗收候選 | 設計備忘；不代表功能已實作 |
| `PROJECT_REVIEW.md` | 以程式證據整理的風險與補強優先序 | review 快照；完成狀態以 HANDOFF／VALIDATION 更新為準 |
| `ROADMAP.md` | M0–M7 分期、Done 條件、後續接入與暫緩項目 | 方向與驗收條件；不是已完成百分比 |
| `SECURITY.md` | 本機 session、授權、purpose、資料升級與 production 限制 | **目前安全邊界**；仍不是正式 IdP／醫療部署 |
| `VALIDATION.md` | 每次驗證的日期、指令、測試數、CI 與未驗證範圍 | **目前驗證證據**；歷史區段與最新區段分開看 |
| `ACCEPTANCE.md` | 早期 demo 完成定義、影片驗收、截圖與真模型評測 | 歷史紀錄；可能含會 reset／seed 的舊指令，不作為日常入口 |
| `UI_AUDIT.md` | web-design-guidelines 的 UI／可及性稽核與修正紀錄 | 2026-09-05／09-12 的審查證據；新 UI 仍須按 AGENTS 規則檢查 |
| `UIUX_OMNI_TWIN.md` | OMNI-TWIN 深色殼、角色艙、狀態與遷移規格 | UI 採納規格；執行細節仍以現行元件與 `design.md` 為準 |
| `design.md` | 現行白／深色 theme tokens、元件與 motion 約束 | UI token 的現行來源；覆寫舊 MASTER 部分內容 |
| `VISION_personal_health_twin.md` | 長期平台願景、Health ID、Health Graph、FHIR、Personal AI | 分母／方向，不是目前完成度 |
| `一份能跟著人走的紀錄_摘要與願景.md` | 比賽／簡報摘要、制度依據、三階段故事 | 對外敘事材料；不是工程規格 |
| `VIDEO.md` | ≤2 分鐘 demo 影片十幕與錄製操作 | 錄影腳本；使用 reset／seed 前確認是 disposable data |
| `TRACE_round.md`、`TRACE_talk_red.md` | 一次巡診與紅燈對話的 trace snapshot | 歷史執行證據；不代表每次 runtime 都完全相同 |
| `proposals/00-architecture.md` | 外部架構提案：Assertion Log、Health Graph、DID/OIDC 等 | **未採納提案**；不可描述成目前 repo 的架構 |
| `img/` | 31 個 UI 截圖與 A4 PDF，供驗收、簡報、設計比對 | 靜態證據資產，不是 runtime 輸入 |

`apps/api/eval/results.md` 是評測輸出，不在 `docs/` 內：它保存 46 句 zh-TW 合成語句的歷史真模型結果；`check` 產生的 mock 結果另寫暫存檔，避免覆蓋它。

---

## 交接時的檢查清單

- [ ] 目前目錄是 repo 根目錄，先執行 `git status`，保留既有 dirty changes。
- [ ] 先讀 `CLAUDE.md`、本指南、`HANDOFF.md`、`SECURITY.md`、`PROJECT_REVIEW.md`。
- [ ] 修改 schema 時確認 Python source、TypeScript codegen、API 投影與測試同步。
- [ ] 修改流程節點時同步檢查兩張 Mermaid 與 `test_mermaid_sync.py`。
- [ ] 修改 UI 時讀 `apps/web/AGENTS.md`、`docs/design.md`、`docs/UIUX_OMNI_TWIN.md`。
- [ ] 不使用真實病人資料，不把 demo mock／截圖／歷史小樣本說成臨床證據。
- [ ] 完成後執行 `.\scripts\dev.ps1 check`，再核對同一 commit 的 GitHub CI。
- [ ] 交接清楚寫出：改了什麼、通過什麼、沒驗什麼、是否碰到 `.env`／records／資料庫。

最後更新：2026-09-13
