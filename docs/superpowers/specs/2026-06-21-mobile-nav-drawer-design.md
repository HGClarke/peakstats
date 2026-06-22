# Mobile navigation drawer — design

**Date:** 2026-06-21
**Status:** Approved (pending spec review)

## Problem

`frontend/src/components/app-shell/Sidebar.tsx` carries `max-[760px]:hidden`.
Below 760px wide, the sidebar — and with it every navigation link — disappears
entirely with no replacement. A user on a narrow viewport is stranded on
whatever page they're on, with no way to reach Overview, Activities, Segments,
Goals, or log out.

## Decision

Below the breakpoint, keep hiding the static sidebar (unchanged), but add a
hamburger button to the top bar. Tapping it opens the **same** navigation as a
slide-in overlay drawer with a dimmed backdrop. This is the standard mobile
pattern and lets the existing sidebar content be reused verbatim.

## Non-goals

- No change to navigation, layout, or behavior **at or above** the breakpoint —
  this is purely additive for small screens.
- No bottom tab bar, no icon-only collapsed rail, no top horizontal nav.
- No full tab-cycle focus trap in v1 (see Accessibility).
- No new nav items or routing changes; the drawer shows the existing
  `NAV_ITEMS`.

## Breakpoint

Replace the one-off `max-[760px]` magic number with a named Tailwind v4
breakpoint. Add to the `@theme` block in `frontend/src/index.css`:

```css
--breakpoint-nav: 760px;
```

This makes `nav:` (min-width 760px) and `max-nav:` (max-width 759.98px)
variants available. The breakpoint is then referenced in exactly three places,
all resolving to the single token:

- desktop sidebar column → `max-nav:hidden` (hidden below 760px)
- mobile drawer → `nav:hidden` (hidden at/above 760px)
- hamburger button → `nav:hidden`

Behavior at 760px is identical to today.

## Component structure

The nav markup (logo + nav list + athlete footer) is reused across the desktop
column and the mobile drawer, so it is extracted once and wrapped two ways.

### `Sidebar.tsx`

- Export a new `SidebarContent` presentational component containing the current
  inner markup (logo, `NAV_ITEMS` nav, athlete footer with logout). Props:
  `navActive`, `athlete`, `syncLabel`, `onLogout`, and an optional
  `onNavigate?: () => void` called when a nav link is clicked.
- Keep exporting `Sidebar` as the **desktop column**: the existing outer
  `<div className="w-[236px] … max-nav:hidden">` wrapper that renders
  `<SidebarContent … />`. It does **not** pass `onNavigate` (no drawer to close).
- `NAV_ITEMS` stays here.

### `MobileNav.tsx` (new, in `components/app-shell/`)

The drawer. Shown only below the breakpoint (`nav:hidden` on its root).
Conditionally rendered — returns `null` when `!open` (see Rendering below).
Props: `open: boolean`, `onClose: () => void`, plus the same content props
(`navActive`, `athlete`, `syncLabel`, `onLogout`).

Renders:

- a fixed full-screen backdrop using the existing `--color-overlay` token
  (`bg-overlay`), which calls `onClose` on click;
- a fixed left-anchored panel (same `w-[236px]`, `bg-surface-sidebar`,
  `border-r border-line2`) that slides in from the left;
- a header row inside the panel with a close (✕) button (lucide `X`,
  `aria-label="Close navigation"`) that calls `onClose`;
- `<SidebarContent … onNavigate={onClose} />` so tapping any nav link closes
  the drawer after navigating.

### `Topbar.tsx`

- Add an optional `onMenuClick?: () => void` prop.
- When provided, render a hamburger button (lucide `Menu`) to the **left of the
  title**, visible only below the breakpoint (`nav:hidden`).

### `AppShell.tsx`

- Owns the open state: `const [navOpen, setNavOpen] = useState(false)`.
- Renders `<Sidebar … />` (desktop, unchanged props).
- Passes `onMenuClick={() => setNavOpen(true)}` to `<Topbar />`.
- Renders `<MobileNav open={navOpen} onClose={() => setNavOpen(false)} … />`
  with the same content props it already receives.
- No changes required in `AppHome`, `ActivitiesPage`, or `SyncPage` — they only
  pass through `AppShell`'s existing props.

## Rendering & animation

- The drawer is **conditionally rendered only when `open` is true.** Rationale:
  (1) keeps the DOM clean so existing tests that query nav text by string don't
  suddenly match two copies (desktop + drawer); (2) avoids off-screen but
  focusable/tabbable elements when closed.
- Enter animation: slide-in from the left via an `animate-` keyframe added to
  `index.css` in the same style as the existing `pkrise`/`pkpulse` keyframes
  (e.g. a `pkslidein` translating from `-100%` to `0`). The backdrop fades in.
- No exit animation in v1 (the drawer unmounts on close); acceptable trade-off
  for the test-cleanliness and a11y benefits above.

## Behavior — closing

The drawer closes (calls `onClose`) on any of:

- tapping a nav link (`onNavigate` → `onClose`);
- clicking the backdrop;
- clicking the ✕ button;
- pressing **Esc** (keydown listener attached while open).

While open, body scroll is locked (toggle `overflow: hidden` on
`document.body` in an effect, restored on close/unmount).

## Accessibility

- Hamburger button: `aria-label="Open navigation"`, `aria-expanded={navOpen}`,
  `aria-controls` referencing the drawer panel id.
- Drawer panel: `role="dialog"`, `aria-modal="true"`,
  `aria-label="Navigation"`, with the id referenced by `aria-controls`.
- On open, focus moves into the drawer (the ✕ / close button); on close, focus
  returns to the hamburger button.
- Esc closes; backdrop click closes.
- A full tab-cycle focus trap is **out of scope for v1** — Esc, backdrop
  dismissal, and return-focus cover the core need.

## Testing

Vitest + Testing Library, co-located, following repo conventions.

- **`MobileNav.test.tsx`** (new, TDD — write failing first):
  - renders nothing when `open` is false;
  - renders the nav items when `open` is true;
  - calls `onClose` on Esc keydown;
  - calls `onClose` on backdrop click;
  - calls `onClose` on a nav-link click;
  - calls `onClose` on the ✕ button click.
- **`Topbar`** coverage (via `AppShell.test.tsx` or a Topbar test): a hamburger
  button is present, and clicking it opens the drawer (nav becomes queryable).
- **Existing `AppShell.test.tsx`** stays green: because the drawer is unmounted
  while closed, `getByText("Overview")` / `getByText("Activities")` still match
  the single desktop copy. Tests that open the drawer must use `getAllByText`
  or scope queries to the dialog.

## Definition of done

`npm test && npm run lint && npm run build` all pass, and below 760px a
hamburger opens a working nav drawer that navigates and dismisses correctly.
