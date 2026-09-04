# design.md — 白色未來感醫療

> 由 ui-ux-pro-max（`design-system/record-follows-person/MASTER.md`）產出骨架，**tokens 段落整段以 CLAUDE.md §7 覆寫**。
> ui-ux-pro-max 原建議的 cyan 色系、Figtree 字體、GSAP 動效一律不採用。任何畫面都從本檔長。

## 0. 定位
- 產品：住宿式長照機構的「一份能跟著人走的紀錄」。三個介面：照護者手機（語音優先）、護理師平板／桌面（10 秒確認、ISBAR 編輯）、醫師唯讀（RoundPage，可列印 A4）。
- 風格：Minimalism / Swiss（白底、留白、高對比、幾何、網格）。**白色未來感醫療**，不是消費型 App。
- 一句話的差異化：**AI 與人的東西長得不一樣**。AI 草稿＝虛線＋淡藍；人確認＝實線＋綠勾。醫師一眼分得出誰說的。

## 1. Tokens（CLAUDE.md §7，唯一來源；覆寫 MASTER.md）
```css
:root {
  --bg: #FFFFFF;
  --surface: #F7F9FC;
  --line: #E3E8EF;
  --ink: #0F1B2D;
  --ink-2: #5B6B7F;
  --primary: #1F6FEB;
  --ok: #1FA971;
  --warn: #D98A00;
  --danger: #D64545;
  --ai-fill: #EAF2FF;          /* AI 草稿底色，配虛線框 */
  --radius-card: 12px;
  --shadow-card: 0 1px 2px rgba(15, 27, 45, .06);
  --space: 8px;                /* 8pt grid：8/16/24/32/48/64 */
}
/* 夜班深色變體（非預設）：background #0F1B2D；紅燈維持高對比 */
[data-theme="night"] {
  --bg: #0F1B2D; --surface: #16233A; --line: #2A3A55; --ink: #F5F7FA; --ink-2: #AEB9C9;
  --ai-fill: #1C2E4A;
}
```
- 字體：中文 **Noto Sans TC**；拉丁與數字 **Inter**；等寬 **JetBrains Mono**（`font-variant-numeric: tabular-nums` 用在所有數字欄）。
- 字級：正文 16px / 行高 1.5；照護者介面正文 18px；標題 20 / 24 / 32。
- 對比：正文 ≥ 4.5:1（`--ink` on `--bg` = 15.3:1；`--ink-2` on `--bg` = 5.6:1；`--primary` on `--bg` = 4.6:1）。
- 圓角：卡片 12px；按鈕 10px；chip 999px。陰影只有一種（`--shadow-card`）。

## 2. 三個介面的硬規格
| 介面 | 裝置 | 規格 |
|---|---|---|
| 照護者 | 手機 | 一顆 ≥72px 麥克風鍵置中；最少文字；母語提示（zh-TW / id / vi）；追問最多兩題；「不知道」是大按鈕（≥56px）；「跟平常不一樣」與四個事件快捷（跌倒／用藥／嗆咳／行為）為 ≥56px 大鍵；tap target ≥56px。 |
| 護理師 | 平板／桌面 | 一屏看完：紅燈 banner 置頂（`--danger`，白字）；異常優先＋趨勢小圖；ISBAR 編輯器中 AI 欄位＝虛線框＋`--ai-fill`＋標籤「AI 草稿，請確認」；A / R 欄空白待填（實線框）；確認鍵 ≥56px；tap target ≥44px。 |
| 醫師 | 唯讀 | RoundPage 一頁：四段固定；`@page { size: A4; margin: 14mm }`；print CSS 隱藏導覽、保留趨勢圖；每行可連回 timeline id（印出來以 `[obs_…]` 顯示）。 |

## 3. AI vs 人：樣式契約（不可混用）
| 狀態 | 邊框 | 底色 | 標記 |
|---|---|---|---|
| AI 草稿（`status=draft`, `author=ai`） | 1.5px **dashed** `--primary` | `--ai-fill` | 左上 chip「AI 草稿，請確認」 |
| 人確認（`status=approved`, `confirmed_by` 有值） | 1.5px **solid** `--ok` | `--bg` | 綠勾＋「已確認 · 姓名 · 時間」 |
| 護理師輸入中 | 1.5px solid `--line`（focus: `--primary` ring 2px） | `--bg` | 無 |
| 紅燈 | 2px solid `--danger` | `#FBE9E9` | 置頂 banner「觀察到的事實 → 建議聯絡護理師」（無等級、無分數） |

## 4. 元件（shadcn/ui 風格，實作在 `apps/web/components/ui`）
- `Button`：variants `primary | secondary | ghost | danger | ok`；sizes `md(44px) | lg(56px) | xl(72px, 麥克風)`；`focus-visible:ring-2`；`touch-action: manipulation`；hover 為顏色加深 6%。
- `Card`：白底、`--line` 1px、12px 圓角、`--shadow-card`；`variant="ai"` 為虛線＋淡藍；`variant="confirmed"` 為綠實線。
- `Badge`：provenance 六種來源各一個中性灰 chip，文字寫來源（`照服員原話 / AI 抽取 / 護理師評估 / 護理師確認 / 醫囑 / 系統推導`），不用顏色代表臨床狀態。
- `DimensionGrid`：八格 2×4（手機）／4×2（平板）；有值亮起（`--primary` 邊框），未知灰；不用 emoji。
- `Sparkline`：inline SVG，`--primary` 線、`--ink-2` 軸；印刷時保留。
- `RedFlagBanner`：sticky top，`role="alert"`，`aria-live="assertive"`。

## 5. 動效
- 只動 `opacity` / `transform`；120–200ms；`prefers-reduced-motion` 時全部關閉。
- 沒有 GSAP、沒有滾動動畫、沒有 skeleton shimmer 之外的 loading 動畫。

## 6. 禁止（違反即 PR 退回）
通用 AI 漸層、紫色光暈、neon、玻璃擬態（glassmorphism）、neumorphism、emoji 當臨床狀態、深色為預設、Figtree／Space Grotesk 等「AI 味」字體、任何未經 §7 的顏色。

## 7. 稽核
每個畫面完成後跑 `.claude/skills/web-design-guidelines`（vercel-labs），結果寫進 `docs/UI_AUDIT.md` 並貼進 PR。
