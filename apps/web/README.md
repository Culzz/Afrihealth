# AfriHealth Web — design system & frontend

React 18 + TypeScript + Vite. Served by FastAPI in the Docker image and by
Vercel in production (built to `dist/`, alongside the `api/` serverless entry).

## Design language

**Vintage editorial + iOS glass** on warm paper:

| Token | Value | Purpose |
| --- | --- | --- |
| `--paper / --paper-deep / --paper-card` | `#f7f3ec` / `#efe8db` / `#fbf8f2` | canvas, recesses, card fallbacks |
| `--ink / --muted / --faint` | `#221b10` / `#6f6455` / `#94897a` | hierarchy of text |
| `--accent` | `#2e5339` deep green | brand, primary actions, moderate risk |
| `--terra` | `#c05a2e` terracotta | negative SHAP bars, warm accents |
| `--glass` family | `rgba(255,255,255,.55–.72)` | frosted panels (`backdrop-filter: blur + saturate`) |
| risk ramp | green `#2e5339` → gold `#ca8a04` → orange `#b45309` → brick `#7c2d12` | semantic severity, warm-tuned |

- **Type:** `Fraunces` (variable serif) for display/headlines, italic accents for
  editorial pulls; `Instrument Sans` for UI/body. Both via Google Fonts
  (`display=swap`, preconnected).
- **Icons:** `lucide-react`, inline, 13–20 px, stroke 2.2.
- **Grain:** fixed SVG `feTurbulence` noise overlay at 5% multiply — cheap,
  texture-only, no image request.
- **Glass fallback:** `@supports not (backdrop-filter…)` swaps glass panels to
  solid `--paper-card` with hairline borders.

## Performance choices

- **Plotly is lazy.** `loadPlotly()` (`src/api/client.ts`) injects the CDN script
  only when the Atlas map or a country chart is actually rendered — the landing
  page never downloads the ~4 MB chart library; first paint carries ~64 KB
  gzipped JS + 10 KB CSS.
- **Photos are local.** `public/img/*.jpg` (Wikimedia Commons, CC BY-SA
  4.0 — credited on the landing page), resized ≤1400 px, quality 78,
  82–304 KB each, `loading="lazy"` + explicit `aspect-ratio` (no layout shift).
- Fonts preconnect before stylesheet fetch; `font-display: swap`.

## Responsiveness

Mobile-first CSS in `src/styles.css`: single-column defaults, `@media
(min-width: 900px)` unlocks the 2–3 column grids (`grid2`, `grid3`, `stats4`),
hero splits into text/photo at ≥990px. Fluid type via `clamp()`; interactive
targets stay ≥36 px tall; the health chip hides under 560 px.

## Routes (HashRouter)

| Route | Page | Notes |
| --- | --- | --- |
| `#/` | `LandingPage` | story + live stats from `/api/v1` (atlas, NGA forecast) |
| `#/atlas` | `AtlasPage` | Plotly choropleth; risk ↔ data-confidence toggle |
| `#/country/:iso3` | `ForecastPage` | series+forecast chart, interval table, SHAP bars |
| `#/methodology` | `MethodologyPage` | live model card + invariants |

## Commands

```bash
npm install
npm run dev        # vite dev server (proxies /api → :8000 via vite.config)
npm run build      # tsc && vite build → dist/
npx vite preview   # serve dist/ locally
```

## Crediting photos

Landing-page imagery is CC BY-SA 4.0 from Wikimedia Commons (midwife —
Vhikman Gee; vaccination session — Marcellin yao; tomato market — David
Oduut/Linkedug; school children — Godot13; fetching water — Meritkosy).
Keep the footer credit block if photos are added or replaced.
