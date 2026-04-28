<div align="center">

# ⚡ Atlas BI — Visual Risk Intelligence

### Beyond Power BI: Real-Time Fleet Risk Correlation at a Glance

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/YOUR_USERNAME/atlas-bi)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178c6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![React](https://img.shields.io/badge/React-18-61dafb?logo=react&logoColor=black)](https://react.dev/)
[![D3.js](https://img.shields.io/badge/D3.js-7.9-f9a03c?logo=d3.js&logoColor=white)](https://d3js.org/)

</div>

---

## The Problem

Static dashboards lie by omission.

Power BI tells you **how many** accidents happened. It cannot show you **why**, **where the chain of causation started**, or **which driver+vehicle+route combination is about to blow up next**.

Fleet risk is a network problem. Treating it as a bar chart costs lives and money.

## The Solution

**Atlas BI** replaces static BI reports with a living, interactive intelligence layer:

| Capability | Power BI | Atlas BI |
|---|---|---|
| Driver ↔ Vehicle ↔ Route correlation graph | ✗ Not possible | ✓ D3 Force Simulation |
| Animated risk aura by entity score | ✗ | ✓ SVG glow filter |
| Sub-100ms filter response on 500+ incidents | Slow (DAX + render) | ✓ In-memory TS functions |
| Live incident streaming | Requires gateway license | ✓ WebSocket / SSE ready |
| AI-powered risk prediction | ✗ | ✓ Claude API integration (roadmap) |
| Deploy cost | Per-user license + infra | ~$0 on Vercel free tier |

---

## Demo

> **Screenshot / GIF goes here**
>
> *Replace this section with a screen recording of the Network Graph in action.
> Recommended tool: [ScreenToGif](https://www.screentogif.com/) (Windows) or [Kap](https://getkap.co/) (macOS).*

```
[ Network Graph Preview ]
  Motorista ──── Veículo ──── Rota
     D012    ────  V047  ────  R003
     (score 87)  (score 72)  (crítica)
      🔴 aura    🟠 aura     🔴 aura
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| UI Framework | **React 18** + Vite | HMR in dev, tree-shaking in prod |
| Language | **TypeScript 5** strict | Zero runtime surprises |
| Visualization | **D3.js v7** | Low-level SVG control — no chart limits |
| Styling | **TailwindCSS 3** | Consistent dark theme, zero CSS files |
| Data | In-memory mock → REST/Supabase | Swap `mockFleet.ts` for real API |
| Deploy | **Vercel** (zero config) | Edge CDN, preview URLs per PR |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/atlas-bi.git
cd atlas-bi

# 2. Install dependencies
npm install

# 3. Configure environment (optional — mock data works out of the box)
cp .env.example .env.local

# 4. Run
npm run dev
# → http://localhost:5173
```

**Build for production:**

```bash
npm run build      # outputs to /dist
npm run preview    # preview the production build locally
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Browser (React)                      │
│                                                          │
│  ┌──────────────┐    ┌─────────────────────────────┐    │
│  │  FilterPanel │───▶│     useFleetGraph (hook)     │    │
│  │  (Sidebar)   │    │  Filters incidents in-memory │    │
│  └──────────────┘    │  Builds GraphNode + GraphLink│    │
│                      └──────────────┬────────────────┘   │
│  ┌──────────────┐                   │                    │
│  │   KpiCard    │    ┌──────────────▼────────────────┐   │
│  │  (5 metrics) │    │      NetworkGraph (D3)         │   │
│  └──────────────┘    │  Force Simulation + SVG render │   │
│                      │  Zoom · Drag · Tooltip · Glow  │   │
│  ┌──────────────┐    └───────────────────────────────┘   │
│  │  RiskDash-   │                                        │
│  │  board.tsx   │◀── Orchestrates state + resize obs.    │
│  └──────────────┘                                        │
│                                                          │
│  Data Layer:  mockFleet.ts  (seed-deterministic RNG)     │
│               └── 50 drivers · 80 vehicles · 500 events  │
│               Replace with: Supabase REST / WebSocket    │
└─────────────────────────────────────────────────────────┘

DAX Measures → TypeScript equivalents (src/utils/riskMetrics.ts)
  DIVIDE([Acidentes], [KM], 0) * 1000  →  accidentRatePer1000km()
  AVERAGEX(Motoristas, [RiskScore])    →  avgRiskScore()
  COUNTROWS(FILTER(Veiculos, Ativo))   →  vehicles.filter(v => v.status === 'active').length
```

---

## Project Structure

```
atlas-bi/
├── src/
│   ├── components/
│   │   ├── RiskDashboard.tsx   # Top-level layout + state
│   │   ├── NetworkGraph.tsx    # D3 force graph (main visual)
│   │   ├── FilterPanel.tsx     # Sidebar filters
│   │   └── KpiCard.tsx         # Metric cards
│   ├── hooks/
│   │   └── useFleetGraph.ts    # Graph data with applied filters
│   ├── data/
│   │   └── mockFleet.ts        # Seeded mock: 500 incidents
│   ├── types/
│   │   └── fleet.ts            # All domain types (strict)
│   └── utils/
│       └── riskMetrics.ts      # DAX→TS pure functions + KPI aggregation
├── .github/workflows/
│   └── deploy.yml              # CI: typecheck + Vercel deploy
├── .env.example                # Environment variable template
├── CONTRIBUTING.md
└── LICENSE (MIT)
```

---

## Roadmap

| # | Feature | Status |
|---|---|---|
| 1 | **Animated Incident Heatmap** — D3 geographic heatmap with real-time pulse per risk zone | `planned` |
| 2 | **Brushable Timeline** — D3 brush selection on incident timeline, linked to all other charts | `planned` |
| 3 | **AI Risk Prediction** — Claude API integration scoring driver+vehicle+route combinations before incidents happen | `planned` |
| 4 | **GPS API Integration** — Live vehicle position overlay via HERE Maps or Google Maps Platform | `planned` |
| 5 | **Multi-tenant SaaS** — Supabase RLS per company, Stripe billing, white-label theming | `planned` |

---

## Connecting Real Data

Replace `src/data/mockFleet.ts` with a Supabase fetch:

```typescript
// src/data/fleetApi.ts
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
)

export const fetchIncidents = async (): Promise<Incident[]> => {
  const { data, error } = await supabase
    .from('incidents')
    .select('*')
    .order('date', { ascending: false })
    .limit(500)

  if (error) throw error
  return data
}
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, commit conventions, and PR checklist.

---

## License

[MIT](LICENSE) — use freely, build commercially, attribution appreciated.

---

<div align="center">

**Built to replace static BI with living intelligence.**

*If you're a fleet operator, logistics manager, or risk analyst looking to upgrade from Power BI —
[open an issue](https://github.com/YOUR_USERNAME/atlas-bi/issues) or reach out directly.*

</div>
