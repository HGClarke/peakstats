# Landing Page — Design Spec

**Date:** 2026-06-20
**Status:** Approved
**Source design:** Claude Design project "Ride Analytics Platform" → `Peakstrider Landing.dc.html`

## Overview

A self-contained landing/login page that replaces the current `App.tsx` placeholder.
Ports the Claude Design file faithfully. No backend connection; the CTA is a plain
`href="#"` stub until the auth phase wires up Strava OAuth.

The page lives in `src/LandingPage.tsx` and is the only thing rendered by `App.tsx`
for now. Routing (`/login` route) is deferred to the auth phase.

## Tech stack additions (project-wide)

These libraries are introduced here and used throughout the rest of the project:

- **Tailwind CSS v4** (`tailwindcss`, `@tailwindcss/vite`) — utility-first styling
- **shadcn/ui** (`npx shadcn@latest init`) — accessible component library
- **Recharts** (`recharts`) — all charts in the app
- **Leaflet** (`leaflet`, `@types/leaflet`) — route maps (first used in ride detail; installed now to avoid later config churn)

## Visual design

**Accent color:** Strava orange `#fc4c02` — primary CTA, chart line/fill, logo mark,
eyebrow label, ride dot accents.

**Fonts (Google Fonts):**
- Space Grotesk 600 — logo wordmark, headlines, large numbers
- Archivo 400/500/600 — body copy, ride names
- JetBrains Mono 400/500 — labels, unit suffixes, badges, timestamps

**Theming:** `.dark` class on `document.documentElement` (shadcn convention).
Default is dark. Toggle button in the nav adds/removes the class. Tailwind `dark:`
variants drive per-element dark mode styles.

Dark background: `#0b0d11`. Light background: `#f4f3ee`.

**Background decor:** 44px grid pattern (color differs light/dark) + top-right orange
radial gradient blur blob (640×640px, `rgba(252,76,2,0.18)`).

**Max-width:** 1240px centered. Responsive breakpoints at 900px (single-column hero)
and 560px (tightened padding).

## File changes

| File | Change |
|---|---|
| `frontend/index.html` | Add Google Fonts preconnect + stylesheet; add `class="dark"` to `<html>` |
| `frontend/vite.config.ts` | Add `@tailwindcss/vite` plugin |
| `frontend/src/index.css` | Replace with `@import "tailwindcss"` + shadcn init output + custom `@theme` tokens + grid background classes |
| `frontend/src/lib/utils.ts` | Created by shadcn init |
| `frontend/src/components/ui/button.tsx` | Added by `shadcn add button` |
| `frontend/src/LandingPage.tsx` | New component — Tailwind classes, shadcn Button, Recharts AreaChart |
| `frontend/src/App.tsx` | Replace placeholder with `<LandingPage />` |

## Component: LandingPage

Single React component. State: `isDark: boolean`, default `true`. `useEffect` syncs
`isDark` to `document.documentElement.classList`.

**Nav** (74px, bottom border):
- Left: 30×30 rounded logo mark (SVG polyline chart, `#fc4c02` + grey baseline) +
  "peakstats" in Space Grotesk 600 18px
- Right: icon-only theme toggle button (sun/moon SVG) + "POWERED BY STRAVA" mono badge

**Hero** (2-column grid `1.02fr 1.12fr`, 56px gap, 80px vertical padding;
single-column below 900px):

Left column:
- Eyebrow: "Ride analytics for everyday riders" — JetBrains Mono 12px, orange,
  uppercase
- H1: "Make sense of every mile you ride." — Space Grotesk 600 54px (42px at 900px,
  31px at 560px)
- Body: 18px Archivo, muted color, max-width 455px
- CTA: shadcn `<Button>` styled with `bg-strava` + hover lift, `href="#"` stub
- Privacy note: JetBrains Mono 11.5px, muted3 color

Right column (dashboard preview card):
- Card: white/`#13161c` panel bg, border, 18px radius, drop shadow
- Header: "THIS WEEK" label + "142.6 km" Space Grotesk 40px + green "+18% vs last" pill
- Area chart: Recharts `AreaChart` with static mock week data, orange fill + stroke,
  day-of-week X axis, no Y axis
- Stat tiles: 3-column grid — ELEVATION 1,240 m · MOVING TIME 6h 12m · AVG SPEED 24.8 km/h
- Recent rides: 2 rows (Morning commute / River loop) with colored dot, name, time, distance

## Out of scope

- Strava OAuth wiring (`href="#"` stub only)
- Routing (`/login` route deferred to auth phase)
- Unit toggle (always shows metric on landing)
- Any backend calls
- Leaflet usage (installed but not used until ride detail phase)
