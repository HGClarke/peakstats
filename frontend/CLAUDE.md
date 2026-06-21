# Frontend — architecture & conventions

React 19 + Vite + TypeScript + Tailwind v4 + shadcn/ui. This file is the
contract for how code is organized here. Follow it for every change; if a change
needs to break a rule, say so explicitly in the PR/description.

## Folder structure

```
src/
├── main.tsx                  # entry — mounts <App/>
├── App.tsx                   # providers + router only; no page markup
├── index.css                 # Tailwind import + design tokens (@theme) + base
│
├── app/                      # app-wide wiring
│   ├── providers/            # context providers (Theme, future: Auth, Query…)
│   └── router.tsx            # route table (react-router) — exports `routes` + `router`
│
├── pages/                    # route-level screens, one folder per page
│   └── <page>/
│       ├── <Page>.tsx        # composition only — lays out section components
│       ├── <Page>.test.tsx
│       └── components/       # components used ONLY by this page (presentational)
│
├── components/               # components shared across 2+ pages
│   └── ui/                   # shadcn primitives (generated — see below)
│
├── lib/                      # framework-agnostic helpers
│   ├── config.ts             # env access (import.meta.env) — the ONLY place for it
│   └── utils.ts              # cn() and small pure utils
│
├── api/                      # typed data layer: fetch client + per-resource
│   │                         #   fetch fns and React hooks (e.g. useWeeklySummary)
│   ├── client.ts             # apiFetch<T>() wrapper + ApiError
│   └── <resource>.ts         # fetch fn + hook for one resource
│
└── types/                    # shared domain types (e.g. ride.ts)
```

## The one rule that prevents merge wars

**Where does a component go?**

- Used by exactly one page → `pages/<page>/components/`
- Used by 2+ pages → `src/components/`
- A shadcn primitive → `src/components/ui/` (don't hand-edit; re-add via CLI)

Start page-local. Promote to `src/components/` only when a second consumer
appears. Don't pre-emptively "generalize".

## Conventions

- **Imports:** always use the `@/` alias (`@/components/...`), never deep
  relative paths like `../../../`. Within a page folder, relative is fine.
- **Pages compose, components render.** A `pages/<page>/<Page>.tsx` should be
  layout + composition only. If it grows logic or large markup blocks, extract a
  component into its `components/` folder.
- **Data stays out of JSX.** Content comes from the `api/` layer via a hook
  (e.g. `useWeeklySummary()`); the page passes it down as props. Presentational
  components take props/read context — they don't hardcode content or import data
  modules. Today the api layer resolves a typed mock; wiring real `fetch` is a
  one-file change with no component edits.
- **TS that emits runtime code is banned** (`erasableSyntaxOnly` is on): no
  constructor parameter properties, no `enum`, no namespaces. Declare class
  fields explicitly and assign in the constructor; use union types / `as const`
  objects instead of enums. `tsc -b` (part of `npm run build`) enforces this.
- **Icons:** use `lucide-react` (`<Sun />`, `<ArrowLeft />`, …), not hand-rolled
  inline `<svg>`. Brand marks (the `Logo` glyph, the Strava CTA mark) stay custom
  since lucide has no equivalent. Keep decorative icons `aria-hidden`.
- **Theme / cross-cutting state lives in `app/providers/`,** never inside a page.
  Read it with the provider's hook (`useTheme()`), don't re-implement.
- **Context files:** a provider component and its hook/context go in *separate*
  files (`ThemeProvider.tsx` exports only the component; `theme-context.ts`
  exports the context + `useTheme`). This satisfies the `react-refresh`
  only-export-components lint rule without `eslint-disable`.
- **Env vars:** access `import.meta.env` only through `lib/config.ts`. Vite
  requires the `VITE_` prefix for client exposure.

## Styling & design tokens

- Tailwind v4. Tokens live in `src/index.css`: per-theme CSS vars in the
  `:root` / `.dark` blocks, exposed as utilities via `@theme inline`.
- **Use token utilities — never raw hex, and never `text-[#..] dark:text-[#..]`
  pairs.** The brand palette is fully tokenized; each token already resolves to
  the right value per theme, so one class covers light + dark:

  | Purpose | Utility |
  |---|---|
  | Primary text | `text-ink` |
  | Body / secondary text | `text-body` |
  | Muted labels | `text-subtle` |
  | Faint mono / meta | `text-faint` |
  | Page background | `bg-surface-page` |
  | Card surface | `bg-surface-card` |
  | Inset tile / control | `bg-surface-inset` |
  | Raised chip (logo) | `bg-surface-elevated` |
  | Standard border | `border-line` |
  | Subtle divider | `border-line-subtle` |
  | Brand accents | `text-strava`, `bg-strava`, `text-ride-green` |

- Need a new color? Add a var to **both** `:root` and `.dark` in `index.css` and
  map it under `@theme inline` (`--color-<name>`). That keeps a rebrand a
  one-file change. Don't reach for raw hex in a component.
- Exceptions that may stay literal: SVG `stroke`/`fill` attributes, and colors
  that are genuinely theme-invariant (identical in light + dark). Chart colors
  inside `WeekChart` are passed as JS values (Recharts needs literals) — keep
  them there.
- Dark mode is class-based (`.dark` on `<html>`), driven by `ThemeProvider`.

## Testing

- Vitest + Testing Library + jsdom. Co-locate `*.test.tsx` next to the unit.
- `npm test` must pass before any change is considered done.
- **TDD for new logic** (hooks, providers, utils): write the failing test first.
  Pure markup refactors are covered by the existing page test — keep it green and
  keep rendered output identical.
- Components that consume a provider must be wrapped in it when rendered in tests
  (see `pages/landing/LandingPage.test.tsx` wrapping in `<ThemeProvider>`).

## Adding things

- **New page:** create `pages/<page>/` with `<Page>.tsx`, a test, and a
  `components/` folder; add a route to the `routes` array in `app/router.tsx`
  pointing at it. Routing is react-router v8 in data mode: `routes` is a plain
  array (so tests can mount it with `createMemoryRouter`) and `App.tsx` feeds
  `router` to `<RouterProvider>` (imported from `react-router/dom`). The `path: "*"`
  catch-all renders `NotFoundPage` — keep it last. Use `<Link>`/`<NavLink>` from
  `react-router` for in-app navigation, never raw `<a>`.
  Note: SPA deep-link fallback is handled by the `rewrites` rule in `vercel.json`.
- **shadcn component:** `npx shadcn@latest add <name>` — lands in
  `components/ui/`. Config in `components.json` (alias `@`, icon lib `lucide`).
- **New data:** add `types/<domain>.ts` for the shape, then `api/<resource>.ts`
  with a `fetch<Resource>()` fn (mock-resolved at first) and a `use<Resource>()`
  hook exposing `{ data, isLoading, error }`. Consume the hook in a page/section
  component. When the backend is ready, switch the fetch fn to `apiFetch<T>(path)`
  and delete the mock — components don't change.

## Before you finish

Run all three and confirm they pass — don't claim done otherwise:

```
npm test && npm run lint && npm run build
```
