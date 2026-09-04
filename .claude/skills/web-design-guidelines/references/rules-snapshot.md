# Web Interface Guidelines — 2026-09-04 snapshot
Source: https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md
(The SKILL.md fetches the live version; this snapshot is for offline audits.)

## Accessibility
- Icon-only buttons need `aria-label`
- Form controls need `<label>` or `aria-label`
- Interactive elements need keyboard handlers
- `<button>` for actions, `<a>`/`<Link>` for navigation (not `<div onClick>`)
- Images need `alt` (or `alt=""` if decorative)
- Decorative icons need `aria-hidden="true"`
- Async updates need `aria-live="polite"`
- Use semantic HTML before ARIA
- Hierarchical headings `<h1>`–`<h6>`; include skip link
- `scroll-margin-top` on heading anchors
- Meaningful media needs captions/transcripts/descriptions

## Focus States
- Interactive elements need visible focus: `focus-visible:ring-*`
- Never `outline-none` without focus replacement
- Use `:focus-visible` over `:focus`
- Sticky headers/footers/overlays must not cover focused element

## Forms
- Inputs need `autocomplete` and meaningful `name`
- Correct `type` and `inputmode`
- Never block paste
- Labels clickable (`htmlFor` or wrapping control)
- Checkboxes/radios: label + control share single hit target
- Submit button stays enabled until request; spinner during request
- Errors inline next to fields; focus first error on submit
- Placeholders end with `…` showing example pattern
- Warn before navigation with unsaved changes

## Animation
- Honor `prefers-reduced-motion`
- Animate `transform`/`opacity` only
- Never `transition: all`
- Animations interruptible

## Typography
- Use ellipsis `…` not `...`
- Curly quotes
- Non-breaking spaces for unit pairs
- Loading states: `"Loading…"`, `"Saving…"`
- `font-variant-numeric: tabular-nums` for number columns
- `text-wrap: balance` / `text-pretty` on headings

## Content Handling
- Text containers handle long content: `truncate`, `line-clamp-*`, `break-words`
- Flex children need `min-w-0` for truncation
- Handle empty states gracefully

## Images
- `<img>` needs explicit `width` and `height`
- Below-fold: `loading="lazy"`; above-fold critical: `priority`

## Performance
- Large lists (>50 items): virtualize
- No layout reads in render
- Prefer uncontrolled inputs
- `<link rel="preconnect">` for CDN/asset domains
- Critical fonts preloaded with `font-display: swap`

## Navigation & State
- URL reflects state (filters, tabs, pagination, panels via query params)
- Links use `<a>`/`<Link>`
- Deep-link all stateful UI
- Destructive actions need confirmation or undo window

## Touch & Interaction
- `touch-action: manipulation`
- `-webkit-tap-highlight-color` set intentionally
- `overscroll-behavior: contain` in modals/drawers/sheets
- Gestures need tap/click and keyboard alternatives
- `autoFocus` sparingly — desktop only, single input

## Safe Areas & Layout
- Full-bleed layouts: `env(safe-area-inset-*)`
- Avoid unwanted scrollbars
- Flex/grid over JS measurement

## Dark Mode & Theming
- `color-scheme` on `<html>`
- `<meta name="theme-color">` matches background
- Native `<select>`: explicit `background-color` and `color`

## Locale & i18n
- Dates/times: `Intl.DateTimeFormat`
- Numbers: `Intl.NumberFormat`
- Wrap brand names, code, identifiers with `translate="no"`

## Hydration Safety
- Inputs with `value` need `onChange` (or `defaultValue`)
- Guard date/time rendering against mismatch

## Hover & Interactive States
- Buttons/links need `hover:` state; interactive states increase contrast

## Content & Copy
- Active voice; specific button labels; error messages include fix/next step; second person

## Anti-patterns (Flag These)
- `user-scalable=no` or `maximum-scale=1`
- `onPaste` with `preventDefault`
- `transition: all`
- `outline-none` without focus-visible replacement
- Inline `onClick` navigation without `<a>`
- `<div>`/`<span>` with click handlers
- Images without dimensions
- Large arrays `.map()` without virtualization
- Form inputs without labels
- Icon buttons without `aria-label`
- Hardcoded date/number formats
- `autoFocus` without justification
- Gesture-only action without alternatives

## Output Format
```
## <filename>
<file>:<line> - <issue>
## <filename>
✓ pass
```
