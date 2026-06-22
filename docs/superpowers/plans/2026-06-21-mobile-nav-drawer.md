# Mobile Navigation Drawer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Below 760px, replace the hidden sidebar with a hamburger button in the top bar that opens the same navigation as a slide-in overlay drawer, so narrow-screen users can still navigate.

**Architecture:** Extract the sidebar's inner markup into a shared `SidebarContent` piece. The existing `Sidebar` wraps it as the desktop column (hidden below the breakpoint). A new `MobileNav` wraps it as a conditionally-rendered overlay drawer (shown only below the breakpoint). `AppShell` owns the open/close state, passing an `onMenuClick` handler to `Topbar` (which renders the hamburger) and `open`/`onClose` to `MobileNav`. The 760px breakpoint becomes a named Tailwind v4 token.

**Tech Stack:** React 19, Vite, TypeScript, Tailwind v4, react-router v8, lucide-react, Vitest + Testing Library + jsdom.

## Global Constraints

- Tailwind v4 only; use token utilities, never raw hex (see `frontend/CLAUDE.md`). Backdrop uses the existing `bg-overlay` token.
- `erasableSyntaxOnly` is on: no enums, no namespaces, no constructor parameter properties.
- Imports use the `@/` alias for cross-folder paths; relative imports are fine within the `app-shell/` folder.
- Icons come from `lucide-react`; decorative icons are `aria-hidden`.
- Co-locate `*.test.tsx` next to the unit. TDD for new logic: failing test first.
- `npm test && npm run lint && npm run build` must all pass before the work is done. (`npm test` = `vitest run`; targeted run = `npx vitest run <path>`.) All commands run from `frontend/`.
- The breakpoint value is exactly `760px` (unchanged from today).
- The drawer panel id `mobile-nav-drawer` is referenced by the hamburger's `aria-controls`; the two literals must stay in sync (Tasks 2 and 3).

---

### Task 1: Breakpoint token + extract `SidebarContent`

Add the named `nav` breakpoint and split `Sidebar` into a reusable `SidebarContent` (used later by the drawer) plus the desktop column wrapper. Add an `onNavigate` callback fired when a built nav link is clicked.

**Files:**
- Modify: `frontend/src/index.css` (add breakpoint token to the `@theme inline` block)
- Modify: `frontend/src/components/app-shell/Sidebar.tsx`
- Test: `frontend/src/components/app-shell/Sidebar.test.tsx`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `SidebarContent(props: { navActive: string; athlete: Athlete | null; syncLabel: string; onLogout: () => void; onNavigate?: () => void }): JSX.Element` — exported from `Sidebar.tsx`. Renders logo + nav + athlete footer as a fragment (caller supplies the flex-column container). `onNavigate` is called when a built nav `<Link>` is clicked.
  - `Sidebar(props: { navActive: string; athlete: Athlete | null; syncLabel: string; onLogout: () => void }): JSX.Element` — unchanged public signature; desktop column, hidden below the `nav` breakpoint.

- [ ] **Step 1: Add the breakpoint token**

In `frontend/src/index.css`, inside the existing `@theme inline { … }` block, add a breakpoint line near the top of that block (right after the opening `@theme inline {` line, before `--color-background`):

```css
  /* Layout breakpoints */
  --breakpoint-nav: 760px;
```

This generates the `nav:` (min-width 760px) and `max-nav:` (max-width) variants.

- [ ] **Step 2: Write the failing test for `onNavigate`**

Replace the contents of `frontend/src/components/app-shell/Sidebar.test.tsx` with:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { Sidebar, SidebarContent } from "./Sidebar";

const athlete = {
  id: 1, name: "Ada Lovelace", avatar_url: null,
  settings: { units: "metric", theme: "dark", default_period: "week" },
};

function renderSidebar() {
  render(
    <MemoryRouter>
      <Sidebar navActive="Activities" athlete={athlete} syncLabel="Up to date"
        onLogout={() => {}} />
    </MemoryRouter>,
  );
}

describe("Sidebar", () => {
  it("links built routes and leaves unbuilt ones inert", () => {
    renderSidebar();
    expect(screen.getByRole("link", { name: /activities/i }))
      .toHaveAttribute("href", "/activities");
    expect(screen.getByRole("link", { name: /overview/i }))
      .toHaveAttribute("href", "/home");
    expect(screen.queryByRole("link", { name: /segments/i })).toBeNull();
  });
});

describe("SidebarContent", () => {
  it("calls onNavigate when a built link is clicked", () => {
    const onNavigate = vi.fn();
    render(
      <MemoryRouter>
        <SidebarContent navActive="Overview" athlete={athlete}
          syncLabel="Up to date" onLogout={() => {}} onNavigate={onNavigate} />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("link", { name: /activities/i }));
    expect(onNavigate).toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `npx vitest run src/components/app-shell/Sidebar.test.tsx`
Expected: FAIL — `SidebarContent` is not exported from `./Sidebar`.

- [ ] **Step 4: Refactor `Sidebar.tsx` to extract `SidebarContent`**

Replace the contents of `frontend/src/components/app-shell/Sidebar.tsx` with:

```tsx
import { LogOut } from "lucide-react";
import { Link } from "react-router";
import { Logo } from "@/components/Logo";
import type { Athlete } from "@/types/athlete";

const NAV_ITEMS: { label: string; to?: string }[] = [
  { label: "Overview", to: "/home" },
  { label: "Activities", to: "/activities" },
  { label: "Segments" },
  { label: "Goals" },
];

function initials(name: string): string {
  return name.split(" ").map((p) => p[0]).filter(Boolean).slice(0, 2).join("").toUpperCase();
}

type SidebarProps = {
  navActive: string;
  athlete: Athlete | null;
  syncLabel: string;
  onLogout: () => void;
};

/** Logo + nav + athlete footer. Shared by the desktop column and the mobile drawer.
 *  Renders a fragment; the caller provides the flex-column container. */
export function SidebarContent({
  navActive,
  athlete,
  syncLabel,
  onLogout,
  onNavigate,
}: SidebarProps & { onNavigate?: () => void }) {
  return (
    <>
      <div className="px-2 mb-[30px]">
        <Logo />
      </div>
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ label, to }) => {
          const active = label === navActive;
          const className = `flex items-center gap-[11px] px-[11px] py-[9px] rounded-[9px] transition-colors ${
            active ? "bg-strava-soft" : "hover:bg-surface-inset"
          }`;
          const inner = (
            <>
              <span
                className={`w-[6px] h-[6px] rounded-full ${active ? "bg-strava" : "bg-muted5"}`}
              />
              <span
                className={`text-[14px] font-medium ${active ? "text-ink2" : "text-subtle"}`}
              >
                {label}
              </span>
            </>
          );
          return to ? (
            <Link key={label} to={to} className={className} onClick={onNavigate}>
              {inner}
            </Link>
          ) : (
            <div key={label} className={className}>
              {inner}
            </div>
          );
        })}
      </nav>
      <div className="flex-1" />
      <div className="border-t border-line2 pt-4 flex items-center gap-[11px]">
        {athlete?.avatar_url ? (
          <img
            src={athlete.avatar_url}
            alt=""
            aria-hidden
            className="w-9 h-9 rounded-full object-cover flex-none"
          />
        ) : (
          <div className="w-9 h-9 rounded-full flex-none flex items-center justify-center font-display font-semibold text-[14px] text-white bg-gradient-to-br from-strava to-strava-deep">
            {athlete ? initials(athlete.name) : "--"}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-medium text-ink2 truncate">
            {athlete?.name ?? "…"}
          </div>
          <div className="font-mono text-[10px] text-faint flex items-center gap-[5px]">
            <span className="w-[6px] h-[6px] rounded-full bg-strava" />
            {syncLabel}
          </div>
        </div>
        <button
          title="Log out"
          aria-label="Log out"
          onClick={onLogout}
          className="w-8 h-8 flex-none rounded-[8px] bg-transparent border border-line text-body cursor-pointer flex items-center justify-center transition-colors hover:text-strava hover:border-strava/40"
        >
          <LogOut size={16} aria-hidden />
        </button>
      </div>
    </>
  );
}

/** Desktop sidebar column. Hidden below the `nav` breakpoint — the mobile drawer
 *  (see MobileNav) takes over there. */
export function Sidebar(props: SidebarProps) {
  return (
    <div className="w-[236px] flex-none border-r border-line2 flex flex-col p-[22px_16px] bg-surface-sidebar max-nav:hidden">
      <SidebarContent {...props} />
    </div>
  );
}
```

Note: the desktop wrapper now uses `max-nav:hidden` in place of the previous `max-[760px]:hidden` — same 760px breakpoint, now from the shared token.

- [ ] **Step 5: Run the test to verify it passes**

Run: `npx vitest run src/components/app-shell/Sidebar.test.tsx`
Expected: PASS (both `Sidebar` and `SidebarContent` describes green).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/index.css frontend/src/components/app-shell/Sidebar.tsx frontend/src/components/app-shell/Sidebar.test.tsx
git commit -m "refactor(nav): extract SidebarContent and add nav breakpoint token"
```

---

### Task 2: `MobileNav` drawer

Build the overlay drawer: conditionally rendered, slides in, dimmed backdrop, closes on link/backdrop/✕/Esc, locks body scroll, and focuses the close button on open.

**Files:**
- Modify: `frontend/src/index.css` (add slide-in + fade-in keyframes)
- Create: `frontend/src/components/app-shell/MobileNav.tsx`
- Test: `frontend/src/components/app-shell/MobileNav.test.tsx`

**Interfaces:**
- Consumes: `SidebarContent` from `./Sidebar` (Task 1); `Athlete` from `@/types/athlete`.
- Produces:
  - `MobileNav(props: { open: boolean; onClose: () => void; navActive: string; athlete: Athlete | null; syncLabel: string; onLogout: () => void }): JSX.Element | null` — exported from `MobileNav.tsx`. Returns `null` when `!open`. The root element carries `id="mobile-nav-drawer"`.

- [ ] **Step 1: Add the drawer animation keyframes**

In `frontend/src/index.css`, in the `── Sync + skeleton animations ──` section, add two keyframes after the existing `@keyframes pkrise … ` line:

```css
@keyframes pkslidein { from { transform: translateX(-100%); } to { transform: translateX(0); } }
@keyframes pkfadein { from { opacity: 0; } to { opacity: 1; } }
```

and add their utility classes after the existing `.animate-pkrise { … }` line:

```css
.animate-pkslidein { animation: pkslidein 0.22s ease both; }
.animate-pkfadein { animation: pkfadein 0.2s ease both; }
```

- [ ] **Step 2: Write the failing test**

Create `frontend/src/components/app-shell/MobileNav.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { MobileNav } from "./MobileNav";

const athlete = {
  id: 1, name: "Ada Lovelace", avatar_url: null,
  settings: { units: "metric", theme: "dark", default_period: "week" },
};

function renderNav(open: boolean, onClose: () => void = () => {}) {
  return render(
    <MemoryRouter>
      <MobileNav open={open} onClose={onClose} navActive="Overview"
        athlete={athlete} syncLabel="Up to date" onLogout={() => {}} />
    </MemoryRouter>,
  );
}

describe("MobileNav", () => {
  it("renders nothing when closed", () => {
    renderNav(false);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByText("Activities")).toBeNull();
  });

  it("renders the nav when open", () => {
    renderNav(true);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /activities/i })).toBeInTheDocument();
  });

  it("calls onClose when Escape is pressed", () => {
    const onClose = vi.fn();
    renderNav(true, onClose);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when the backdrop is clicked", () => {
    const onClose = vi.fn();
    const { container } = renderNav(true, onClose);
    const backdrop = container.querySelector("#mobile-nav-drawer > [aria-hidden]");
    expect(backdrop).not.toBeNull();
    fireEvent.click(backdrop as Element);
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when a nav link is clicked", () => {
    const onClose = vi.fn();
    renderNav(true, onClose);
    fireEvent.click(screen.getByRole("link", { name: /activities/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when the close button is clicked", () => {
    const onClose = vi.fn();
    renderNav(true, onClose);
    fireEvent.click(screen.getByRole("button", { name: /close navigation/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it("moves focus to the close button when opened", () => {
    renderNav(true);
    expect(screen.getByRole("button", { name: /close navigation/i })).toHaveFocus();
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `npx vitest run src/components/app-shell/MobileNav.test.tsx`
Expected: FAIL — cannot find module `./MobileNav`.

- [ ] **Step 4: Implement `MobileNav`**

Create `frontend/src/components/app-shell/MobileNav.tsx`:

```tsx
import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import type { Athlete } from "@/types/athlete";
import { SidebarContent } from "./Sidebar";

// Must match the hamburger's aria-controls in Topbar.tsx.
const DRAWER_ID = "mobile-nav-drawer";

/** Slide-in navigation drawer for screens below the `nav` breakpoint.
 *  Conditionally rendered: returns null when closed. */
export function MobileNav({
  open,
  onClose,
  navActive,
  athlete,
  syncLabel,
  onLogout,
}: {
  open: boolean;
  onClose: () => void;
  navActive: string;
  athlete: Athlete | null;
  syncLabel: string;
  onLogout: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const prevFocused = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      prevFocused?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div id={DRAWER_ID} className="fixed inset-0 z-50 nav:hidden">
      <div
        aria-hidden
        onClick={onClose}
        className="absolute inset-0 bg-overlay animate-pkfadein"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        className="absolute left-0 top-0 bottom-0 w-[236px] border-r border-line2 flex flex-col p-[22px_16px] bg-surface-sidebar animate-pkslidein"
      >
        <div className="flex justify-end mb-1">
          <button
            ref={closeRef}
            type="button"
            aria-label="Close navigation"
            onClick={onClose}
            className="w-8 h-8 flex-none rounded-[8px] bg-transparent border border-line text-body cursor-pointer flex items-center justify-center transition-colors hover:text-strava hover:border-strava/40"
          >
            <X size={16} aria-hidden />
          </button>
        </div>
        <SidebarContent
          navActive={navActive}
          athlete={athlete}
          syncLabel={syncLabel}
          onLogout={onLogout}
          onNavigate={onClose}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `npx vitest run src/components/app-shell/MobileNav.test.tsx`
Expected: PASS (all 7 cases).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/index.css frontend/src/components/app-shell/MobileNav.tsx frontend/src/components/app-shell/MobileNav.test.tsx
git commit -m "feat(nav): add MobileNav slide-in drawer"
```

---

### Task 3: Hamburger button + `AppShell` wiring

Add the hamburger to `Topbar` (shown only below the breakpoint) and wire the open/close state in `AppShell`, rendering `MobileNav`.

**Files:**
- Modify: `frontend/src/components/app-shell/Topbar.tsx`
- Modify: `frontend/src/components/app-shell/AppShell.tsx`
- Test: `frontend/src/components/app-shell/AppShell.test.tsx`

**Interfaces:**
- Consumes: `MobileNav` from `./MobileNav` (Task 2); `Sidebar` from `./Sidebar` (Task 1).
- Produces:
  - `Topbar` gains optional `onMenuClick?: () => void` and `menuOpen?: boolean`. When `onMenuClick` is set, a hamburger button (`aria-label="Open navigation"`, `aria-controls="mobile-nav-drawer"`, `aria-expanded={menuOpen}`) renders left of the title, hidden at/above the `nav` breakpoint.
  - `AppShell` public signature unchanged; internally owns `navOpen` state.

- [ ] **Step 1: Write the failing test**

Replace the contents of `frontend/src/components/app-shell/AppShell.test.tsx` with:

```tsx
import { fireEvent, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/providers";
import { AppShell } from "./AppShell";

const athlete = {
  id: 99, name: "Ada Lovelace", avatar_url: null,
  settings: { units: "metric", theme: "dark", default_period: "week" },
};

function renderShell(onLogout: () => void = () => {}) {
  renderWithProviders(
    <MemoryRouter>
      <AppShell navActive="Overview" athlete={athlete} syncLabel="Up to date"
        onLogout={onLogout} title="Home">
        <div>body</div>
      </AppShell>
    </MemoryRouter>,
  );
}

describe("AppShell", () => {
  it("renders nav, title, and the athlete name", () => {
    renderShell();
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Activities")).toBeInTheDocument();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("body")).toBeInTheDocument();
  });

  it("calls onLogout when the logout button is clicked", () => {
    const onLogout = vi.fn();
    renderShell(onLogout);
    fireEvent.click(screen.getByRole("button", { name: /log out/i }));
    expect(onLogout).toHaveBeenCalled();
  });

  it("opens the mobile nav drawer when the menu button is clicked", () => {
    renderShell();
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /open navigation/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
```

Note: with the drawer closed, only the desktop `SidebarContent` is in the DOM, so `getByText("Overview")` and the single `/log out/i` button still resolve uniquely — the existing assertions stay valid.

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx vitest run src/components/app-shell/AppShell.test.tsx`
Expected: FAIL — no button named "Open navigation" / no dialog.

- [ ] **Step 3: Add the hamburger to `Topbar`**

Replace the contents of `frontend/src/components/app-shell/Topbar.tsx` with:

```tsx
import type { ReactNode } from "react";
import { Menu } from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";

export function Topbar({
  title,
  subtitle,
  right,
  onMenuClick,
  menuOpen,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
  onMenuClick?: () => void;
  menuOpen?: boolean;
}) {
  return (
    <div className="h-[70px] flex-none border-b border-line2 flex items-center justify-between px-8">
      <div className="flex items-center gap-[14px]">
        {onMenuClick ? (
          <button
            type="button"
            aria-label="Open navigation"
            aria-controls="mobile-nav-drawer"
            aria-expanded={menuOpen ?? false}
            onClick={onMenuClick}
            className="w-[38px] h-[38px] flex-none rounded-[10px] bg-surface-inset border border-line text-subtle flex items-center justify-center cursor-pointer transition-colors hover:text-ink hover:border-strava/40 nav:hidden"
          >
            <Menu size={18} aria-hidden />
          </button>
        ) : null}
        <h1 className="font-display font-semibold text-[22px] m-0 tracking-[-0.01em] text-ink">
          {title}
        </h1>
        {subtitle ? (
          <span className="font-mono text-[11px] text-faint">{subtitle}</span>
        ) : null}
      </div>
      <div className="flex items-center gap-[14px]">
        {right}
        <ThemeToggle />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Wire state into `AppShell`**

Replace the contents of `frontend/src/components/app-shell/AppShell.tsx` with:

```tsx
import { useState, type ReactNode } from "react";
import type { Athlete } from "@/types/athlete";
import { MobileNav } from "./MobileNav";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell({
  navActive,
  athlete,
  syncLabel,
  onLogout,
  title,
  subtitle,
  headerRight,
  children,
}: {
  navActive: string;
  athlete: Athlete | null;
  syncLabel: string;
  onLogout: () => void;
  title: string;
  subtitle?: string;
  headerRight?: ReactNode;
  children: ReactNode;
}) {
  const [navOpen, setNavOpen] = useState(false);
  return (
    <div className="relative flex min-h-screen h-screen bg-surface-page text-ink overflow-hidden">
      <Sidebar navActive={navActive} athlete={athlete} syncLabel={syncLabel} onLogout={onLogout} />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar
          title={title}
          subtitle={subtitle}
          right={headerRight}
          menuOpen={navOpen}
          onMenuClick={() => setNavOpen(true)}
        />
        <div className="flex-1 min-h-0 relative overflow-hidden">{children}</div>
      </div>
      <MobileNav
        open={navOpen}
        onClose={() => setNavOpen(false)}
        navActive={navActive}
        athlete={athlete}
        syncLabel={syncLabel}
        onLogout={onLogout}
      />
    </div>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `npx vitest run src/components/app-shell/AppShell.test.tsx`
Expected: PASS (all 3 cases).

- [ ] **Step 6: Full verification**

Run: `npm test && npm run lint && npm run build`
Expected: all pass — full Vitest suite green, no ESLint errors, build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/app-shell/Topbar.tsx frontend/src/components/app-shell/AppShell.tsx frontend/src/components/app-shell/AppShell.test.tsx
git commit -m "feat(nav): hamburger menu opens mobile nav drawer"
```

---

## Manual verification (after all tasks)

1. `cd frontend && npm run dev`, open the app, log in / reach a dashboard page (Overview, Activities, or Sync).
2. Narrow the browser below 760px (or use device toolbar): the sidebar disappears and a hamburger appears in the top bar, left of the title.
3. Click the hamburger: the drawer slides in from the left over a dimmed backdrop, showing logo, nav, and the athlete footer.
4. Click a nav link (e.g. Activities): the app navigates and the drawer closes.
5. Reopen, then dismiss via (a) the ✕ button, (b) the backdrop, and (c) the Esc key — each closes the drawer.
6. While the drawer is open, confirm the page behind does not scroll.
7. Widen the viewport above 760px: the hamburger is gone and the static sidebar is back; no drawer.
