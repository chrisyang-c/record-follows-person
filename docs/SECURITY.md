# 本機身分與用途授權契約

更新：2026-09-10。這是 M1/M2 的本機帳號實作，不是 OIDC、正式醫療部署或安全認證。只使用合成資料；不要公開暴露服務。

## 已實作邊界

- 每個既有 identity 使用自己的密碼；PBKDF2-HMAC-SHA256、獨立隨機 salt、600,000 次。伺服器簽發 8 小時 opaque session；SQLite 只存 token 雜湊，瀏覽器以 HttpOnly cookie 傳送。改密碼撤銷所有舊 session，登出撤銷當前 session。
- 每次請求重查 identity 的角色／停用狀態及該病人尚有效的 grant。`me`／`role` cookie、`X-Who`／`X-Role`、body 的護理師名字都不能建立身分；矛盾的 actor 欄位會被拒絕。
- HTTP middleware 明列可用路由，未列入的路由預設拒絕。病人授權在載入臨床資料、讀取 graph snapshot 或執行 agent 前檢查；原始 records、graph state、trace 只供具有必要完整授權的護理師。
- `allowed_purposes` 是固定 enum：`self-care`、`caregiving`、`treatment`、`care-management`；原本自由文字 `purpose` 保留為授權理由。請求使用 session 用途，或明確指定 `X-Purpose`，仍須符合該病人的有效授權。
- summary 只載入有 scope 的資料區塊；非護理師 JSON／串流活動另外移除結構化 confidence 與原始感測欄位，不更動儲存的 provenance。尚無安全投影的事故／後送原件暫不給非護理師；本人／醫師可見 RoundPage 和照護注意事項，家屬／照護者可見照護注意事項。
- 目前 talk／Ask／Twin 等組合功能會讀多類資料，保守要求完整 scope；不是授予單一 talk 就可間接讀全部紀錄。巡診必須有整份名單授權，resume 重查原始 cohort，不能偷偷縮小名單繞過撤銷。未登記可信 cohort 的舊巡診拒絕 HTTP 操作。
- Care Circle 管理須有該病人的明確 `can_manage` 授權。代理不能再委派管理權、擴大自己的 scope／期限或替自己與本人重新授權；全域 family 角色不代表代理所有病人。
- 非唯讀請求檢查 CSRF，提供 Origin 時須在允許清單。登入依帳號及 peer 限流。驗證錯誤不回傳輸入密碼／臨床 body。所有受保護請求記錄決策、用途、request ID；有病人目標時記錄 grant IDs，拒絕記錄原因。
- `POST /worker/scan` 不開放 HTTP；內部排程不變。跌倒模擬器須明確 `ENABLE_DEMO_SIMULATION=true` 並以有權限的護理師操作。

## 瀏覽器與設定

前端使用同源 `/api`，Next 透過 `API_INTERNAL_URL` 連後端；伺服器驗證 session，layout 只是畫面狀態來源，不是唯一授權閘門。登入後採站內相對跳轉，避免 localhost／127.0.0.1 的 host-only cookie 不相通。API 私人回應設 `Cache-Control: no-store`。

`.env.example` 的 `AUTH_COOKIE_SECURE=false` 只供本機 HTTP。部署 HTTPS 時必須開啟 Secure cookie、限制 `AUTH_ALLOWED_ORIGINS`，並先完成下列尚缺的部署安全工作。不要把 demo 的公開密碼用於任何真資料。

## 既有資料升級：不需要重跑 seed

舊的病人共用密碼不再可登入，也不會因登入自動入圈。舊 grant 若沒有 `allowed_purposes` 會拒絕存取，**不自動推定用途或管理權**。

由有權管理本機資料的操作者，在互動式 PowerShell 執行：

```powershell
Set-Location 'D:\Health AI Bridge\record-follows-person\apps\api'
# 僅為已存在的帳號設定自己的密碼；隱藏輸入，不把密碼放指令列
uv run python ../../scripts/manage_credentials.py --who nurse_lin

# 先預覽一筆明確授權；不修改紀錄
uv run python ../../scripts/manage_consent.py --patient P001 --member nurse_lin --scopes who timeline docs talk --purposes treatment --reason '本機合成照護測試' --days 7
# 確認對象、scope、用途與期限後，才在同一命令加 --apply 並輸入 yes
```

若需要本人管理入口，可明確對本人 identity（例如 P001）重新授予 `self-care` 與 `--can-manage`，不要替所有成員批次開啟。兩個工具都支援 `--records-root` 指定確切資料目錄，不建立新 identity、不重設病歷。設定密碼會撤銷該帳號既有 session；重新授權保留已撤銷的舊 grant 並建立新 grant ID。

只有全新的可丟棄示範資料才使用 seed。seed 建立公開合成帳號密碼 `demo-{identity_id}-2026!`，例如 `demo-P003-2026!`；它不是既有資料的升級命令。

## 仍未解決

- 身分 registry 仍由本機可信操作者維護；沒有機構資格驗證、OIDC／MFA、帳號復原、完整管理員治理或網路層濫用防護。
- SQLite 與 JSON 檔依賴檔案權限，未加密、未接 KMS。audit 是 append 介面，不是不可竄改 ledger；整體備份／還原與保留政策仍待完成。
- 病歷／consent JSON 仍缺跨檔案與多程序交易。授權撤銷會影響下一次請求，但不是對正在執行的長任務提供原子中止保證；SQLite session 不解決臨床寫入一致性。
- 回應的結構化欄位移除不代表能證明任意自由文字完全不含敏感資訊。尚需逐端點安全 DTO、文字輸出評測、提示注入與完整端到端角色測試。
- 目前限流是本機帳號／peer 層，不是完整分散式流量防護；反向代理信任、請求大小／工作量限制與部署 hardening 仍需設計。
- Purpose 驗證代表宣告用途符合授權，不是驗證人的真正使用意圖，也不代表符合所有法規。緊急存取、法定代理、組織政策與完整同意生命週期尚未建立。

測試與 runtime 證據見 [VALIDATION](VALIDATION.md)。密碼成本選擇參考 [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)；此實作不宣稱 FIPS 認證。
