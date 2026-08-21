# Phase 2 — Design system, primitives, navigation (§5.2)

**Goal:** the product must look like one considered thing, not eleven screens. Every screen built
after this sits on the primitives, so retrofitting later would be expensive.

**Constraint:** the navy/brand palette is NOT changed (that needs founder sign-off). Semantic tokens
are layered *on top* of it, exactly as §5.2 specifies.

## Step 1 — Tokens (`tailwind.config.js`, `src/index.css`)

Semantic colour tokens on top of the existing palette:
- `surface`, `surface-raised`, `surface-sunken`
- `border-subtle`, `border-strong`
- `text-primary` / `text-secondary` / `text-muted` / `text-inverted`
- clinical status: `status-good | status-watch | status-attention | status-critical` (+ `-bg` pairs)

Type scale (name → size/line-height):
`display` 32/40 · `h1` 24/32 · `h2` 20/28 · `body` 15/24 · `small` 13/20 · `caption` 12/16.
Tabular numerals on every reading via a `.tnum` utility.

Spacing: strict 4px grid (Tailwind's default scale already is; no arbitrary values in new code).
Elevation: **two levels only** — `shadow-card` (resting) and `shadow-raised` (overlay). The existing
`shadow-lifted` is folded into `shadow-raised`.
Radius: one family — `sm` 6 · `md` 8 · `lg` 12 · `xl` 14 · `2xl` 18.

## Step 2 — `lucide-react`

Added for icons. No emoji in product UI (audit confirms there are none today — keep it that way).

## Step 3 — `components/ui/` primitives

`Button, Input, Select, Textarea, Checkbox, Radio, Switch, Badge, Card, Modal, Drawer, Tabs,
Tooltip, Table, Pagination, EmptyState, Skeleton, Toast, Breadcrumb, Avatar, ProgressMeter,
StatTile, DateRangePicker` + an `index.ts` barrel.

These **absorb** the existing `components/common/{Badge,Card,Toast,Loading,ErrorBanner}.tsx` rather
than paralleling them — §7 of the brief is explicit that a second version of something that exists
means refactoring the original instead. `components/common/` is deleted once callers move.

Every control: 44px minimum hit target, real `<label>`, visible focus ring, `aria-invalid` +
`aria-describedby` on error, keyboard operable, `prefers-reduced-motion` respected.

## Step 4 — Navigation (`components/layout/AppShell.tsx`)

The current top-tab bar does not scale to the page count Phases 4–10 add. Replace with:
- **≥1024px:** collapsible left sidebar with grouped sections; top bar keeps search, notifications,
  account menu.
- **768–1023px:** sidebar collapses to icons.
- **<768px:** top bar + bottom tab bar for the 4 primary destinations.

Sidebar state persists in `localStorage`. Skip-link to `<main>`. `aria-current="page"` on the active
item.

## Step 5 — Refactor screens onto the primitives

All eleven existing screens plus the cards/forms/charts components. Every list and table gains a
loading skeleton, an empty state, and an error state with retry.

## Step 6 — Charts

One shared axis / gridline / tooltip / threshold-band treatment in
`components/charts/chartTheme.ts`, applied to `VitalsTrendChart` and reused by every later chart.

## Acceptance

- `npx tsc -p tsconfig.json --noEmit` clean, no `any`, no `@ts-ignore`
- `npm run build` clean · `npx vitest run` green
- Every screen verified at 375 / 768 / 1024 / 1440
- WCAG 2.1 AA: 4.5:1 contrast, visible focus, labelled controls, ARIA live regions for alerts and
  toasts, full keyboard operation, `prefers-reduced-motion` honoured

**Commit:** `feat(ui): design system tokens, primitives layer and sidebar navigation`
