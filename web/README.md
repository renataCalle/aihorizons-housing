# web

Pencil It: React + TypeScript + Vite, with MapLibre for the map. Rules: `CLAUDE.md` here and at the repo root.

```bash
nvm use                 # Node 22, as in CI (.nvmrc at the repo root)
npm install
npm run dev             # proxies /api to the API on :8000
npm test                # Vitest
npm run gen:types       # after an API model change: openapi.json → src/api/types.gen.ts
```

Start the API from the repo root with `uv run uvicorn navigator_api.main:app --reload`.

Only `src/api/adapters.ts` imports the generated types (oxlint enforces it). Components use the
view models in `src/models/`, so a contract change only touches the adapter.
