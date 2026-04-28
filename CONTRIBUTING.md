# Contributing to Atlas BI

Thank you for your interest in contributing. This guide covers the conventions we use so that the project stays consistent and easy to review.

## Development Setup

```bash
git clone https://github.com/YOUR_USERNAME/atlas-bi.git
cd atlas-bi
npm install
cp .env.example .env.local   # fill in any values you need
npm run dev
```

## Branch Naming

| Purpose | Pattern | Example |
|---|---|---|
| Feature | `feat/<short-description>` | `feat/heatmap-animation` |
| Bug fix | `fix/<short-description>` | `fix/network-graph-drag` |
| Docs | `docs/<short-description>` | `docs/api-integration` |
| Chore | `chore/<short-description>` | `chore/upgrade-d3-v8` |

## Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/).

```
<type>(optional scope): <short imperative description>

[optional body]
[optional footer]
```

**Types:** `feat` · `fix` · `docs` · `style` · `refactor` · `test` · `chore`

## Pull Request Checklist

- [ ] `npm run build` passes with zero errors
- [ ] TypeScript strict mode: `npx tsc --noEmit` passes
- [ ] No hardcoded secrets or API keys
- [ ] New visual components have at least one screenshot in the PR description

## Code Style

- **TypeScript strict** — all props and return types must be explicit
- **No `any`** — use `unknown` and narrow properly
- **Tailwind only** for styling — no inline `style={}` except D3 SVG attributes
- **D3 mutations stay inside `useEffect`** — never mutate DOM outside hooks

## Reporting Issues

Open an issue with the label `bug`, `enhancement`, or `question`. Include browser + OS version for visual bugs.
