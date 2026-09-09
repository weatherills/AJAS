# AJAS Frontend (React + TypeScript + Vite)

Web UI for the AI Job Application System. Feature screens (resume library,
review, auto-apply, settings, job feed, email, learning) are implemented per
`.codespring/CURSOR_RUNBOOK.md`.

## Develop

Prerequisites (provided by the Cloud Agent environment): Node.js 22.

```bash
cd frontend
npm install
npm run dev      # http://localhost:3000
```

## Build & check

```bash
npm run build    # type-checks (tsc -b) and builds
npm run lint
npm run preview
```
