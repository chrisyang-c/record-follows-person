# CONSOLIDATION — 唯一專案與來源去向

> 最後核對：2026-09-06。`D:\Health AI Bridge\record-follows-person` 是唯一正式開發目錄；只 clone 此 repo，不需要旁邊的參考專案。

## 1. 現在應留下什麼

```text
D:\Health AI Bridge\
├── record-follows-person\     唯一需要持續修改、提交及推送的專案
└── 三份後續加入的演講 PDF     本機閱讀原件，不是程式相依；未上傳

D:\Health AI Bridge Archive\20260906-consolidation\
├── README.md                  備份範圍與還原說明
├── docs\                     外層架構提案原件
└── health-ref\               參考專案完整工作樹、.git 與未提交修改
```

外層兩個資料夾已移出工作區，沒有永久刪除來源檔案。封存不是開發相依，不需上傳本 repo，也不要從封存目錄繼續開發本產品。個人 `.env`、執行期 `records/`、資料庫及工具仍須自行配置／備份，不屬於 Git 可攜性的承諾。

封存之後使用者又放入三份演講 PDF，原件保留原位。因此「唯一正式專案」不表示現在父目錄物理上只剩一個項目。私人閱讀筆記放在本機 repo 的 `local-notes/`，以 `.git/info/exclude` 排除，不隨 clone／push 傳送；公開 repo 只保存有公開來源的優化備忘。若重建 clone，私人筆記及其排除設定須另外備份。

### 本輪封存驗證

| 來源 → 封存 | 搬移前後核對 |
|---|---|
| 外層 `docs/` → 封存 `docs/` | 1 個檔案，51,619 bytes；原件 SHA-256 `7A62B214FC2B96F7D123E93233FECFA444993B23ABFDBD90653C744AEB3E1928` |
| `health-ref/` → 封存 `health-ref/` | 7,779 個檔案，196,928,057 bytes；排序後「相對路徑＋檔案大小」清單指紋相同：`F4AA5F148D065CD3AAEF6D8ED340382018DF642030F10F19A8AE4212AB685E3F` |
| 參考專案 Git | HEAD `877131da0c3358b680f184247d748debfda7dbb3`；搬移後仍有 18 個 tracked 檔案修改、5,528 行新增、485 行刪除 |

第二項是檔案清單／大小核對，不是逐檔內容雜湊；不把它寫成「逐位元驗證」。提案原文與 repo 版本去除新增頁首、統一換行後一致。

## 2. 來源整合清單

較早一輪的刪除與內容盤點沿用當時交接；本輪能核對的是目前 repo 與實際仍存在的封存。未留原件者不能重新證明完整性。

| # | 來源 | 現在的去向／狀態 | 驗收或剩餘工作 |
|---|---|---|---|
| 1 | `claude_healthcare/twin/baseline/` | `apps/api/baseline/`，已採用 | 正常帶門檻與禁止自動寫回 baseline 的測試 |
| 2 | detection 的「偵測不用 LLM」 | 本 repo `red_flags/rules.py` 已有同一原則 | 紅燈模組不得呼叫 LLM 的測試 |
| 3 | consent Zone 0–4 | 未直接搬碼；內容敏感度政策仍是候選 | 與現有 scope 可組合，不宣稱兩者天生互斥；見 ROADMAP M2 |
| 4 | `citation_gate.py` | 未搬碼；claim-level evidence 列入 M5 | provenance 與護理師批准不能替代逐句證據驗證 |
| 5 | core 斷言日誌／雙時間軸 | 未搬碼；保留 PersonRecord，版本與更正列入 M3 | `write_timeline` 不是完整 append-only/bitemporal 保證 |
| 6 | Event Packet | 目前保留 IncidentFile；通用事件封包待 M6 | 驗證跨事件、角色投影、證據引用，不能只因名稱近似視為完成 |
| 7 | 原四角色 web | 保留本 repo Next.js | 未逐頁移植；目前頁面可建置不代表功能完全等價 |
| 8 | `claude_healthcare` 其餘約 13,500 行 | 上輪交接稱已刪除、未保存 | 本輪未刪除；沒有原件，未調查 Git／磁碟／雲端復原可能性，不宣稱不可回復 |
| 9 | `gpt_healthcare` 的 5 份文件 | 上輪判定與 VISION 重疊後刪除 | 本輪無原件，不以該判定證明沒有獨有內容 |
| 10 | 外層 `…最終版.md` | 上輪判定與 VISION 重複後刪除 | 檔案大小相近不足以證明內容相同；本輪無原件可重新比對 |
| 11 | 外層 `docs/00-architecture.md` | repo `docs/proposals/00-architecture.md`；原件封存 | 原文保留，逐項採納；不是另一個必須維護的產品 |
| 12 | `health-ref` 通用 HealthEvent | 概念參考，M6 自行實作 | 內部 confidence/quality 可建模，受限的是臨床畫面的輸出，不是一概禁用 schema 欄位 |
| 13 | `health-ref` purpose／audit 想法 | `0ee23aa` 已補欄位、grant 必填、登入預設及 UI 顯示 | M2 尚需政策判斷與 request purpose，不能把字串欄位視為 Consent Engine 完成 |
| 14 | `health-ref` 其他內容 | 完整封存；`512a402` 已有獨立重寫的 UI 想法及特定模型資產 | 授權按資產核對，見 §3；不宣稱其全部能力已被本 repo 覆蓋 |
| 15 | Windows 開發與驗證入口 | `scripts/dev.ps1`、腳本回歸測試、runtime smoke | 完整前後端 gate 不靜默跳過；結果見 VALIDATION |

## 3. 外部來源與資產界線

`health-ref` 來源是 `chenni416/Healthcare`，目前沒有 repo 層級的 LICENSE 宣告。這不自動證明每份資產均不得使用，也不等於整份程式可以放入 Apache-2.0 專案。

- 沒有適用授權或明確許可的程式碼不直接複製；功能想法可獨立實作，保留來源註記。
- `apps/web/public/models/my_avatar.glb` 是例外的特定資產：`512a402` 已收錄，其許可與來源記於同目錄 `LICENSE.txt`。這份記錄不延伸為整個參考 repo 的授權；公開發布前仍應確認權利鏈及再散布條件。
- `apps/web/public/anatomy/` 另有自己的來源／授權，分開追蹤。
- 不修改封存的參考專案，不把它的 venv、未提交修改或 `.git` 併入本 repo。

## 4. 架構不是整包二選一

保留 Next.js、REST、LangGraph、PersonRecord 與批准閘門。未搬入另一套應用不代表拒絕 Health Graph、欄位級政策、claim-level evidence、版本／更正與正式儲存。

PersonRecord 可以逐步成為 domain abstraction；PostgreSQL 的關聯查詢可先承載 health graph 關係，不必一開始同時維運 Neo4j、TimescaleDB、向量資料庫。具體排序與 Done 在 [ROADMAP](ROADMAP.md)，目前問題證據在 [PROJECT_REVIEW](PROJECT_REVIEW.md)。

`0ee23aa` 已有 purpose 欄位與授權時非空檢查。Purpose 下一步仍要分清：grant 的允許目的、單次請求目的、政策結果、拒絕原因及 audit；還要處理舊資料遷移、撤銷後失效與 API 負向測試。本輪只完成整併與驗證，不宣稱已實作 Consent Engine。

## 5. 開發入口與驗證

Windows 使用 PowerShell 7：`.\scripts\dev.ps1 setup` 安裝鎖定的 API＋web 相依；`.\scripts\dev.ps1 check` 跑完整靜態與測試 gate。只有明確加 `-ApiOnly` 才跳過前端，輸出會標示範圍，不算完整驗收。

`check` 的 mock eval 使用臨時資料，不覆寫已保存的真模型報告；codegen `--check` 只比對、不重寫 TypeScript。`api` 正常操作會寫紀錄，`migrate` 會建立資料表，不能聲稱所有日常指令都不碰資料。`init/reset/seed/clean-records` 是會清資料的指令，保留確認提示。

可重現指令、測試數量與未涵蓋事項統一記在 [VALIDATION](VALIDATION.md)。
