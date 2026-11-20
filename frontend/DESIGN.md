# Whitespace design system

For small exporters and importers who are not trade experts, often on phones. Every screen
answers one question in plain words first, then shows the evidence on demand.

## Principles

1. **Verdict first, evidence on demand.** Lead with the answer and 3–4 numbers; details go in tabs.
2. **Orange means "you and your next move"**, as the logo's single orange tile: the primary
   button, your country on maps and charts. Never a status colour.
3. **Words beat colour.** Every status has an icon and a label; chart titles state the takeaway.
4. **Phone-first.** 44px touch targets, bottom tabs, skeletons while loading, nothing hover-only.
5. **Plain word first, term second.** Explain jargon in place with `<InfoTip>`.
6. **Your language, your money.** Local currency (lakh/crore) beside USD; chat replies in the
   user's language (`dir="auto"` on user-written and model-written text).
7. **Calm density.** Lists and tables over walls of cards; one primary action per view.
   No box inside a box inside a box: inside a card use rows with dividers or a
   `bg-surface-2` well, not more bordered cards. A row of numbers is one `<StatGroup>`.
8. **Orange once per view.** The one orange `<Button>` is the next business step (deal
   sheet, draft, check). Everything else is `secondary` or `ghost`; AI helpers don't get
   orange just for being AI.

## Tokens (src/app/globals.css)

Never write hex colours in components; use the semantic utilities. Light is the default; dark
follows the device or the user's choice (Settings → Appearance), via `data-theme` on `<html>`.

| Use                                 | Utility                                                                      |
| ----------------------------------- | ---------------------------------------------------------------------------- |
| Page / card / hover well            | `bg-canvas` / `bg-surface` / `bg-surface-2`                                  |
| Borders (decorative / inputs)       | `border-line` / `border-line-strong`                                         |
| Text primary / secondary / tertiary | `text-fg` / `text-muted` / `text-subtle`                                     |
| Links, active nav, focus            | `text-brand`, `bg-brand-soft`, `ring-brand/…`                                |
| Primary button (orange)             | `<Button>` (uses `bg-action`) — don't hand-roll                              |
| "You" marks in charts               | `var(--chart-exporter)`, `text-accent-strong` for small text                 |
| Status                              | `positive`, `caution`, `negative` (+ `-soft` backgrounds) via `<Badge tone>` |
| Map shades                          | `var(--map-1)` … `var(--map-5)`, `var(--map-empty)`                          |
| Elevation                           | `shadow-card` (cards), `shadow-pop` (menus, dialogs)                         |

Verdict tones (`VERDICT_TONE` in components/markets/verdict.tsx): go/grow → positive,
test/defend → caution, care/hard → negative. Use `<VerdictBadge>`; don't restyle verdicts.

## Type, shape, motion

- Geist. Page title `text-2xl sm:text-3xl font-semibold tracking-tight`; section title
  `text-base/lg font-semibold`; body `text-sm`/`text-[15px]`; **never below `text-xs` (12px)**.
  Numbers `tabular-nums`.
- Radius: chips `rounded-full`, inputs/buttons `rounded-xl`, cards `rounded-2xl`, dialogs `rounded-3xl`.
- Motion: hover 120–200ms; menus `pop-in`; first paint of a page section may use `rise-in`
  with `--delay` (≤ 250ms total stagger). No looping animation inside the app. Everything is
  disabled under `prefers-reduced-motion` (handled in globals.css).

## Building blocks (src/components/ui)

`Page`, `PageHeader`, `Card`, `CardHeader` (card.tsx) · `Button`, `ButtonLink`, `buttonClass`
(button.tsx) · `Badge`, `Callout`, `toneClass` (badge.tsx) · `Stat` (stat.tsx) · `InfoTip`
(info-tip.tsx) · `Tabs` (tabs.tsx) · `EmptyState`, `Skeleton` (empty.tsx) · `Field`,
`inputClass` (field.tsx) · `Popover`, `MenuItem` (menu.tsx). Charts: `WorldMap`
(components/charts). Icons: `lucide-react`, 16/20px, `strokeWidth` 1.75–2, always with a label.

Need something new? Add a new file in `components/ui` rather than changing an existing
component's API.

## Patterns

- **Layout grids:** always start with `grid-cols-1` (and give flex/grid children that hold
  truncated text `min-w-0`), or one long word widens the page on phones.
- **List + detail:** for many records (pipeline), a compact list on the left and the chosen
  record on the right; on phones the list, then the record full width with a back link.

- **Page:** `<Page>` → `<PageHeader title description actions>` → content sections.
- **Headline numbers:** a row of `<Stat>` (2 columns on phones, 4 on desktop).
- **Ranked lists:** rank · name · verdict badge · size · growth; the whole row is a link.
- **Detail pages:** verdict + next step → numbers → `<Tabs>` for the evidence.
- **States:** every data section has a skeleton (shaped like the content), an empty state
  (why + one action), and an error message with what to do.
- **Numbers:** `money()`, `signedPercent()`, `percent()`, `points()` (lib/format.ts); local money
  with `localMoney()`, prices with `perKg()` (lib/money.ts). State the data year on every page.
- **Product names:** titles use `product.name` (everyday, e.g. "towels"); the official
  description (`shortProductName(description)`) is the subtitle.

## Data hooks

TanStack Query hooks live in `src/lib/api/`. Generic ones in `queries.ts`; a new feature gets
its own file (import `api`, `unwrap`, `keys` helpers) instead of growing `queries.ts`.
Types come from the backend's OpenAPI spec: `make gen-client` after API changes.
