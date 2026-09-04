# UI audit — web-design-guidelines (vercel-labs, rules-snapshot 2026-09-04) — run 2026-09-05 on apps/web

## apps/web/app/layout.tsx
✓ pass

## apps/web/app/globals.css
✓ pass

## apps/web/app/page.tsx
apps/web/app/page.tsx:29 - error `<p>` has no `role="alert"`/`aria-live` (other pages use `role="alert"` for the same case)
apps/web/app/page.tsx:30 - residents `<ul>` renders empty while `/residents` is loading and when it returns `[]`; only the error branch has copy. `useApi` already exposes `loading` — show "Loading…" and an empty state

## apps/web/app/(caregiver)/caregiver/page.tsx
apps/web/app/(caregiver)/caregiver/page.tsx:151 - page has no `<h1>`; first heading is a Card `<h2>` (:220) and the "speak" stage has no heading at all
apps/web/app/(caregiver)/caregiver/page.tsx:211 - send button disabled on `!composed()` (validation-gated); keep submit enabled until the request and show the reason inline
apps/web/app/(caregiver)/caregiver/page.tsx:212 - pending label is a bare "…" (also :246); use a localized verb ("傳送中…" / "Mengirim…" / "Đang gửi…")
apps/web/app/(caregiver)/caregiver/page.tsx:234 - follow-up `<Textarea>` has no `<label>`/`aria-label`/`aria-labelledby` (the question at :233 is a `<p>`), and every follow-up shares `name="answer"`
apps/web/app/(caregiver)/caregiver/page.tsx:264 - reset button is labelled `{t.send} ↺` ("送出") but it clears the form; give the action its own string
apps/web/app/(caregiver)/caregiver/page.tsx:271 - raw API error string (e.g. "Failed to fetch") shown to a caregiver with no next step; localize and add what to do ("請再試一次／告訴護理師")

## apps/web/app/(caregiver)/caregiver/notes/page.tsx
apps/web/app/(caregiver)/caregiver/notes/page.tsx:29 - every `error` (network down, 500) renders as the "還沒有本月注意事項" empty state; branch on `ApiError.status === 404`, otherwise show an error with a next step

## apps/web/app/(nurse)/nurse/page.tsx
apps/web/app/(nurse)/nurse/page.tsx:62 - `<Textarea name="edited_a">` has no label (placeholder only)
apps/web/app/(nurse)/nurse/page.tsx:65 - `<Textarea name="return_reason">` has no label
apps/web/app/(nurse)/nurse/page.tsx:138 - "立即掃描逾時" `await api(...)` has no pending state and no try/catch; a failed scan is an unhandled rejection with no UI feedback
apps/web/app/(nurse)/nurse/page.tsx:152 - Card title `<h2>` directly under section `<h2>` (:147; same at :168→:52) — card titles should be `<h3>` here (see card.tsx:37)

## apps/web/app/(nurse)/nurse/review/[thread]/page.tsx
apps/web/app/(nurse)/nurse/review/[thread]/page.tsx:114 - status Chip shows the raw interrupt key (`nurse_review`, `nurse_route_choice`…) without `translate="no"`; map through a label table (nurse/page.tsx:17 `TYPE_LABEL`)
apps/web/app/(nurse)/nurse/review/[thread]/page.tsx:146 - Chip renders raw enum keys `d.domain d.direction` ("intake up"); use `DIMENSION_LABELS` and a direction label
apps/web/app/(nurse)/nurse/review/[thread]/page.tsx:175 - `<Textarea name="return_reason">` has no label; placeholder "要照護者補充什麼？" is a question, not an example ending in "…"
apps/web/app/(nurse)/nurse/review/[thread]/page.tsx:178 - `sticky bottom-0` action bar: no `env(safe-area-inset-bottom)` and no scroll-padding, so it can sit over the focused A/R textarea when tabbing
apps/web/app/(nurse)/nurse/review/[thread]/page.tsx:185 - confirm button disabled until A, R and 意識 are filled with no inline message saying which is missing; keep enabled, validate on click, focus the first empty field
apps/web/app/(nurse)/nurse/review/[thread]/page.tsx:240 - `<Textarea name="family_content">` has no label (Card title is a heading, not a label)

## apps/web/app/(nurse)/nurse/round/page.tsx
apps/web/app/(nurse)/nurse/round/page.tsx:84 - Chip shows the raw interrupt key (`head_nurse_edit_list`…); reuse `TYPE_LABEL`
apps/web/app/(nurse)/nurse/round/page.tsx:98 - roster `<table>` has no `overflow-x-auto` wrapper; `max-w-64 truncate` on the `<td>` (:114) is not honored in auto table layout, so a long `reason` widens the table and the page scrolls horizontally
apps/web/app/(nurse)/nurse/round/page.tsx:121 - embedding `<RoundPageView>` adds a second `<h1>` (round-page-view.tsx:14) under the page `<h1>` at :83
apps/web/app/(nurse)/nurse/round/page.tsx:154 - placeholders from `ORDER_EXAMPLES` (:17-19) end with "。" not "…", and a full realistic order as placeholder reads as filled-in content
apps/web/app/(nurse)/nurse/round/page.tsx:159 - submit disabled until an order is typed; no inline hint
apps/web/app/(nurse)/nurse/round/page.tsx:202 - no pending label while `busy` (also :207); siblings at :91/:128/:160 use "…中"

## apps/web/app/(nurse)/nurse/incident/[patientId]/[docId]/page.tsx
apps/web/app/(nurse)/nurse/incident/[patientId]/[docId]/page.tsx:16 - error `<p>` has no `role="alert"`; replaces the whole page silently
apps/web/app/(nurse)/nurse/incident/[patientId]/[docId]/page.tsx:32 - `h.rule_id` identifier rendered without `translate="no"`
apps/web/app/(nurse)/nurse/incident/[patientId]/[docId]/page.tsx:43 - incident flags render raw enum keys (`fall`, `medication_issue`) in Chips; caregiver page uses `t[i]` labels
apps/web/app/(nurse)/nurse/incident/[patientId]/[docId]/page.tsx:66 - `IsbarView` Cards (`<h2>`) nested inside the "護理師區塊" Card (`<h2>` at :53) — same-level headings nested (see card.tsx:37)

## apps/web/app/(doctor)/doctor/page.tsx
apps/web/app/(doctor)/doctor/page.tsx:21 - any error (API down) renders as "尚未發布 RoundPage…"; branch on 404
apps/web/app/(doctor)/doctor/page.tsx:34 - `(residents ?? [])` → blank list while loading; no loading/empty copy

## apps/web/app/(doctor)/doctor/round/[patientId]/page.tsx
apps/web/app/(doctor)/doctor/round/[patientId]/page.tsx:23 - nothing rendered until the fetch resolves (no "Loading…" state), and the error `<p>` has no `role="alert"`

## apps/web/app/record/[patientId]/page.tsx
apps/web/app/record/[patientId]/page.tsx:82 - error `<p>` has no `role="alert"`
apps/web/app/record/[patientId]/page.tsx:111 - `e.valid_from` printed as a raw ISO string; use `fmtDay` (Intl) like every other date
apps/web/app/record/[patientId]/page.tsx:121 - whole append-only timeline rendered with `.map()`, no pagination/virtualization (14-day seed is already ~40–50 entries and it only grows)
apps/web/app/record/[patientId]/page.tsx:131 - `d.doc_type` raw key (`round_page`, `incident_file`) shown in a Chip

## apps/web/components/dimension-grid.tsx
apps/web/components/dimension-grid.tsx:31 - `aria-label={v.direction}` on a plain `<span>` (no role) is not reliably announced, and the value is the raw key (`up`/`down`); use visually-hidden text ("上升"/"下降") beside the arrow

## apps/web/components/isbar-editor.tsx
apps/web/components/isbar-editor.tsx:140 - editor `<Textarea>`s (:140, :143, :160, :163) have no `<label>`/`aria-labelledby`; Card titles are `<h2>`s, not labels — at least `aria-labelledby` the heading
apps/web/components/isbar-editor.tsx:160 - `required` (also :163) with no enclosing `<form>` is never enforced and yields no inline error; submission is gated by a disabled button instead (review page :185)

## apps/web/components/red-flag-banner.tsx
apps/web/components/red-flag-banner.tsx:6 - `sticky top-0` banner with no `scroll-padding-top` in globals.css; on long nurse pages a focused element scrolled into view can land under the banner

## apps/web/components/round-page-view.tsx
apps/web/components/round-page-view.tsx:14 - hard-coded `<h1>` in a reusable component → duplicate `<h1>` when embedded (nurse/round/page.tsx:121); accept a heading level prop
apps/web/components/round-page-view.tsx:36 - no empty-state copy when `page.changes` is `[]` (same for `page.questions` at :82; `order_followup` has one at :68)

## apps/web/components/sparkline.tsx
apps/web/components/sparkline.tsx:35 - `first.value`/`last.value` interpolated raw into `aria-label`; use `fmtNum` (Intl.NumberFormat)

## apps/web/components/ui/badge.tsx
✓ pass

## apps/web/components/ui/button.tsx
apps/web/components/ui/button.tsx:6 - transitions `background-color,color,border-color`; guideline (and design.md §5) allow `transform`/`opacity` only

## apps/web/components/ui/card.tsx
apps/web/components/ui/card.tsx:37 - `title` always renders `<h2>` regardless of nesting; produces same-level headings inside section `<h2>`s (nurse/page.tsx:147→152) and inside another Card (incident page :53→:66). Accept an `as`/`level` prop

## apps/web/components/ui/field.tsx
✓ pass

## Design contract (docs/design.md)

**Tokens — only CLAUDE.md §7**
- apps/web/app/globals.css:16-17 - `--ok-fill #e8f7f0`, `--warn-fill #fff4e0` are not in §7 or design.md (`--danger-fill #fbe9e9` is sanctioned by design.md §3). Record in DECISIONS.md or drop.
- apps/web/components/ui/button.tsx:10,11,13,14; apps/web/app/(doctor)/doctor/page.tsx:18; apps/web/app/(nurse)/nurse/page.tsx:158 - inline hover hexes `#1a62d3`, `#eef2f7`, `#188f60`, `#bf3c3c`. design.md §4 allows "hover 加深 6%", but the value should be a token (`--primary-hover`…); `#1a62d3` is now copy-pasted in three files.

**Fonts**
- apps/web/app/globals.css:51 - `--font-sans` lists Noto Sans TC before Inter, so Latin letters and digits in body text render in Noto's Latin glyphs, not Inter (contract: 拉丁與數字 Inter). Put Inter first; Noto still covers CJK via fallback. (`.num` at :78 already forces Inter.)

**Contrast ≥4.5:1 (design.md §1)** — WCAG ratios computed from the §7 hexes
- apps/web/components/ui/button.tsx:13 - `ok` variant: white on `--ok` #1FA971 = 3.0:1 — this is the primary confirm button (接受 / 確認 ISBAR / 確認更新基線)
- apps/web/components/ui/button.tsx:14 - `danger` variant: white on #D64545 = 4.4:1
- apps/web/components/ui/badge.tsx:30-33 - Chip text on fill, all `text-xs`: primary 4.1:1, ok 2.7:1, warn 2.5:1, danger 3.7:1
- apps/web/components/ui/badge.tsx:22 - author `text-ink-2/70` on `--surface` ≈ 2.9:1
- apps/web/components/ui/card.tsx:33 - "已確認" `text-ok` on `--ok-fill` = 2.7:1
- apps/web/components/red-flag-banner.tsx:10 - banner title `text-danger` on `--danger-fill` = 3.7:1 (contract: 紅燈維持高對比; body lines at :13 use `text-ink` and are fine)
- apps/web/components/round-page-view.tsx:35 - `text-warn` on `--warn-fill` = 2.5:1; :39 `text-danger` on white = 4.4:1
- apps/web/app/record/[patientId]/page.tsx:45, apps/web/app/(nurse)/nurse/page.tsx:58 - `text-warn` on white / `--ai-fill` ≈ 2.5–2.8:1
- apps/web/app/(nurse)/nurse/review/[thread]/page.tsx:223 - route hint `text-xs opacity-80` white on `--primary` ≈ 3.5:1
- Direction: keep §7 tokens for fills, borders and icons; set text on fills to `--ink`, or add darker text tokens (`--ok-ink`, `--warn-ink`) via a §7 change logged in DECISIONS.md.

**AI draft = 1.5px dashed `--primary` + `--ai-fill` + chip; confirmed = 1.5px solid `--ok` + 綠勾**
- apps/web/components/round-page-view.tsx:12 - reimplements the contract with Tailwind `border` (1px) `border-dashed border-primary` on `bg-bg` (no `--ai-fill`) and `border-ok` (1px); use `.ai-draft` / `.confirmed` from globals.css
- apps/web/app/(caregiver)/caregiver/page.tsx:258 - raw `.ai-draft` box without the "AI 草稿，請確認" chip (`Card variant="ai"` adds it)
- apps/web/components/round-page-view.tsx:19, apps/web/app/record/[patientId]/page.tsx:30, incident page :25, review page :114 - "已確認" markers outside `Card` have no check glyph and no time (contract: 綠勾＋已確認 · 姓名 · 時間)
- apps/web/app/record/[patientId]/page.tsx:39 - both ternary branches are `"confirmed p-2 text-sm"`; a nurse-authored A and an AI-drafted-then-accepted A are indistinguishable (dead conditional)
- apps/web/app/page.tsx:52 - "live channel" cards use `--ai-fill` + solid `--primary` border for non-AI content; keep `--ai-fill` meaning "AI draft" only

**Tap targets (≥44px; caregiver ≥56px)**
- Caregiver routes (<56px): apps/web/app/(caregiver)/caregiver/page.tsx:155,165 `<Select>` is `min-h-11` (44px); :277 and notes/page.tsx:50 are inline `text-sm` links (~20px); apps/web/app/layout.tsx:37 nav links are 44px on caregiver routes
- Nurse/doctor/record (<44px): pill links `px-3 py-1 text-sm` ≈31px at apps/web/app/page.tsx:38-40 and apps/web/app/(nurse)/nurse/round/page.tsx:140,220; inline text links at nurse/page.tsx:101 (`text-xs` Card meta), :185, review page :235,:254,:259, incident page :27, doctor/round page :17, record page :57,:133-135, round-page-view.tsx:45. Add `inline-flex min-h-11 items-center` (`min-h-14` on caregiver routes)

**Motion (design.md §5: opacity/transform only)**
- apps/web/components/ui/button.tsx:6 - color-property transitions (see guideline finding above); `prefers-reduced-motion` is honored globally ✓

**Checked and clean**
- Emoji as clinical status / gradients / glassmorphism / neumorphism / dark-by-default: none found (grep over app/ and components/) ✓
- Print CSS for RoundPage A4: `@page { size: A4; margin: 14mm }`, `.no-print`, `.print-page`, `break-inside: avoid`, sparkline preserved, `[id]` refs shown in print — apps/web/app/globals.css:100-108, round-page-view.tsx:12,46-49 ✓
- Caregiver hard specs: mic 96px (≥72), 不知道 / 跟平常不一樣 / 4 event buttons `size="lg"` (56px), ≤2 follow-ups, native-language prompts ✓
- Nurse hard specs: red banner sticky-top with `role="alert"`, AI ISBAR fields dashed + "AI 草稿，請確認", nurse A/R solid and blank, confirm buttons `size="lg"` (56px) ✓
- Card 12px / button 10px / chip 999px radii, single `--shadow-card`, `color-scheme` on `:root`, `theme-color` = `--bg` ✓

## Fix pass — 2026-09-05

Scope: apps/web only (+ docs/design.md §1 note, docs/DECISIONS.md row). API payload keys unchanged. Gate: `pnpm lint && pnpm typecheck && pnpm test && NEXT_PUBLIC_API_URL=http://localhost:8000 pnpm build` — all four pass.

### apps/web/app/page.tsx
- :29 error `<p>` no `role="alert"` — **fixed** (`role="alert"`, `text-danger-ink`)
- :30 blank list while loading / empty — **fixed** ("Loading…" while `loading`; "還沒有住民資料，先跑 make seed。" when `[]`)

### apps/web/app/(caregiver)/caregiver/page.tsx
- :151 no `<h1>` — **fixed** (`<h1 className="sr-only">{t.title}</h1>`; i18n key `title` in zh-TW / id / vi; stage Cards now `headingLevel={2}`)
- :211 send button disabled on `!composed()` — **fixed** (stays enabled; empty → inline `role="alert"` hint `t.needText` under the textarea, focus moves to the textarea via ref)
- :212/:246 bare "…" pending label — **fixed** (`t.sending`: 傳送中… / Mengirim… / Đang gửi…)
- :234 follow-up `<Textarea>` unlabeled, shared `name="answer"` — **fixed** (`aria-label={f.question}`, `name={`answer-${index}`}`)
- :264 reset button labelled `{t.send} ↺` — **fixed** (`t.again`: 再報一句 / Lapor lagi / Báo tiếp)
- :271 raw API error to caregiver — **fixed** (localized `t.errorRetry` with next step, raw message in `text-xs` below)

### apps/web/app/(caregiver)/caregiver/notes/page.tsx
- :29 every error rendered as empty state — **fixed** (`useApi` now returns `status`; 404 → empty-state copy, otherwise `role="alert"` "無法連線到 API，請確認 make api 已啟動。" + raw message)

### apps/web/app/(nurse)/nurse/page.tsx
- :62 `edited_a` unlabeled — **fixed** (`aria-label`, example placeholder ending in "…")
- :65 `return_reason` unlabeled — **fixed** (`aria-label`)
- :138 scan button no pending / no try-catch — **fixed** (busy label "掃描中…", `disabled` while scanning, error `<p role="alert">`)
- :152 Card `<h2>` under section `<h2>` — **fixed** (`Card` default `headingLevel` is now 3; nurse page cards render `<h3>`)

### apps/web/app/(nurse)/nurse/review/[thread]/page.tsx
- :114 raw interrupt key in status chip — **fixed** (`typeLabel()` from lib/labels.ts; when done, `ConfirmedChip` with nurse + `confirmed_at`)
- :146 raw `d.domain d.direction` — **fixed** (`DIMENSION_LABELS[d.domain]["zh-TW"]` + `DIRECTION_LABEL`)
- :175 `return_reason` unlabeled, question-style placeholder — **fixed** (`aria-label="退回原因"`, placeholder "例如：…喝了多少水…")
- :178 sticky bar without safe-area / scroll padding — **fixed** (`pb-[calc(0.5rem+env(safe-area-inset-bottom))]`; `html { scroll-padding-top: 96px }` in globals.css)
- :185 confirm button disabled with no message — **fixed** (stays enabled; on click validates 意識 / A / R, lists missing fields inline with `role="alert"`, focuses the first empty one via refs passed into `OnsiteFields` / `IsbarEditor`)
- :240 `family_content` unlabeled — **fixed** (`aria-label="家屬通知內容"`)
- :223 route hint `opacity-80` — **fixed** (removed)
- Raw ids (`review_log` node/action/by, handoff page id, incident file id) — **fixed** (`translate="no"`)

### apps/web/app/(nurse)/nurse/round/page.tsx
- :84 raw interrupt key chip — **fixed** (`typeLabel()`)
- :98 roster table no `overflow-x-auto` — **fixed** (wrapper div, `min-w-[560px]` on the table)
- :121 second `<h1>` from embedded `RoundPageView` — **fixed** (`headingLevel={2}`; sections become `<h3>`)
- :154 placeholders read as filled content — **fixed** (`ORDER_EXAMPLES` are short hints ending in "…"; `ORDER_FULL` holds the full text for "填入示範醫囑")
- :159 submit disabled with no hint — **fixed** (enabled; inline `role="alert"` "請至少輸入一位住民的醫囑。", focus to first order field)
- :202/:207 no pending label — **fixed** ("確認中…" on both baseline buttons)
- Also: "Loading…" while a `?thread=` is being fetched; baseline proposal chips show dimension labels instead of keys

### apps/web/app/(nurse)/nurse/incident/[patientId]/[docId]/page.tsx
- :16 error `<p>` no `role="alert"` — **fixed**
- :32 `h.rule_id` without `translate="no"` — **fixed**
- :43 raw incident flag keys — **fixed** (`INCIDENT_LABEL`)
- :66 same-level headings nested — **fixed** (top Cards `headingLevel={2}`, `IsbarView headingLevel={3}`)
- Also: `route_decision` → `ROUTE_LABEL`; header/nurse-section markers → `ConfirmedChip` (check + name + time)

### apps/web/app/(doctor)/doctor/page.tsx
- :21 any error shown as "尚未發布" — **fixed** (404 → 尚未發布; other → `role="alert"` "無法連線到 API…")
- :34 blank list while loading — **fixed** ("Loading…", empty state, error with `role="alert"`)

### apps/web/app/(doctor)/doctor/round/[patientId]/page.tsx
- :23 no loading state, error without `role="alert"` — **fixed** ("Loading…"; 404 vs. connection error both `role="alert"`)

### apps/web/app/record/[patientId]/page.tsx
- :82 error `<p>` no `role="alert"` — **fixed**
- :111 raw ISO `valid_from` — **fixed** (`fmtDay`)
- :121 whole timeline rendered — **fixed** (20 per page + "再顯示 20 筆"; `id` anchors kept; on mount the URL hash target is located and enough pages are shown to include it, then scrolled into view)
- :131 raw `doc_type` — **fixed** (`DOC_TYPE_LABEL`)
- :39 dead ternary on minimal SBAR — **fixed** (chip "護理師改寫" when `author === "nurse"`, else "護理師接受 AI 草稿")
- Also: shift → `SHIFT_LABEL`, incident kind chip via `INCIDENT_LABEL`, "已確認" → `ConfirmedChip`

### apps/web/components/dimension-grid.tsx
- :31 `aria-label` on plain span, raw key — **fixed** (arrow `aria-hidden`, visually-hidden `DIRECTION_LABEL` text beside it)

### apps/web/components/isbar-editor.tsx
- :140 editor textareas unlabeled — **left (already have `aria-label`; per instruction no `aria-labelledby` needed)**
- :160/:163 `required` without a `<form>` — **fixed** (removed; gating is on-click validation on the review page)

### apps/web/components/red-flag-banner.tsx
- :6 sticky banner without `scroll-padding-top` — **fixed** (`html { scroll-padding-top: 96px }`)

### apps/web/components/round-page-view.tsx
- :14 hard-coded `<h1>` — **fixed** (`headingLevel?: 1 | 2`, sections follow)
- :36 no empty-state for `changes` / `questions` — **fixed** ("自上次巡診沒有明顯變化。" / "沒有需要醫師確認的事。")

### apps/web/components/sparkline.tsx
- :35 raw numbers in `aria-label` — **fixed** (`fmtNum`)

### apps/web/components/ui/button.tsx
- :6 color transitions — **fixed** (`transition-[…]` removed; design.md §5)

### apps/web/components/ui/card.tsx
- :37 always `<h2>` — **fixed** (`headingLevel?: 2 | 3 | 4`, default 3; native `title` attr omitted from the prop type so titles may be JSX)

### Design contract
- Tokens not in §7 (`--ok-fill`, `--warn-fill`) — **fixed** (recorded as derived tokens in design.md §1 + DECISIONS.md 2026-09-05)
- Inline hover hexes — **fixed** (`--primary-hover`, `--surface-hover`, `--ok-fill-hover`, `--danger-fill-hover`; no hex left in app/ or components/)
- Fonts: Noto before Inter — **fixed** (Inter first in `--font-sans`)
- Contrast: `ok`/`danger` button white text — **fixed** (`bg-*-fill text-ink border-*`); Chip text — **fixed** (`text-ink` / `text-*-ink`); author `text-ink-2/70` — **fixed** (`text-ink-2`); Card "已確認" — **fixed** (`text-ok-ink`); banner title — **fixed** (`text-danger-ink`); round-page-view warn/danger text — **fixed**; record/nurse `text-warn` — **fixed** (`text-warn-ink`); route hint opacity — **fixed**
- AI/confirmed contract: round-page-view ad-hoc borders — **fixed** (`.ai-draft` / `.confirmed`); caregiver raw `.ai-draft` box — **fixed** (`<Card variant="ai">`); "已確認" markers without check/time — **fixed** (`components/confirmed-chip.tsx` used in round-page-view, record, incident, review, doctor list); record dead ternary — **fixed**; home "live channel" cards on `--ai-fill` — **fixed** (`border-primary bg-surface`)
- Tap targets: caregiver `<Select>` 44px, inline links — **fixed** (`min-h-14` on caregiver routes); nurse/doctor/record pills and inline links — **fixed** (`inline-flex min-h-11 items-center`); round-page-view evidence refs — **left as inline print refs, wrapped in `inline-flex min-h-6` (exempt)**
- Motion — **fixed** (see button.tsx)

### Left / notes
- Night-theme values for the four `*-hover` tokens were not specified; only the three `*-ink` night variants were added. Night theme has no toggle yet, so no visible effect today.
- `TenSecondConfirm` "修改並確認" / "退回照護者" and review-page "退回照護者" keep their `disabled` gating on empty text — not in the original findings; unchanged.
