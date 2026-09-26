# Handoff: web and API workstream

Unzip this at the root of `aihorizons-housing`, on your branch (`git checkout -b feat/web-api` from `scaffold/monorepo`). Nothing here overwrites your teammate's files: the root `CLAUDE.md`, `contracts/`, `engine/`, `pipeline/`, `research/` and `fixtures/golden/` are untouched.

## Where things land

| Path | What it is |
|---|---|
| `web/CLAUDE.md` | Rules for the React app; Claude Code reads it when working in `web/` |
| `api/CLAUDE.md` | Rules for the FastAPI service; read when working in `api/` |
| `docs/01-product-spec.md` | Screens, flows, states, copy rules |
| `docs/02-design-system.md` | Tokens, components, map style |
| `docs/03-architecture-and-api.md` | How web, api and the engine connect; endpoints |
| `docs/04-contracts.md` | How the UI aligns with `navigator_contracts` |
| `docs/05-ai-search.md` | Plain-language search to filters |
| `docs/06-mock-data.md` | Mock data in three stages |
| `docs/07-build-plan.md` | Milestones and the prompts to paste into Claude Code |
| `docs/proposals/` | Additive search models and UI field requests for your teammate to review |
| `docs/design/` | Mockup sources; add the exported PNGs to `docs/design/screens/` |
| `fixtures/mock/ui-draft/` | Illustrative fixtures matching the mockups |
| `fixtures/eval/nl_search_eval.jsonl` | 41 prompts for the AI search eval |

## Three small manual steps

1. **Add one section to the root `CLAUDE.md`** (append, don't replace):

```markdown
## Web and API workstream

Product, design and API specs for the web app and the API are in `docs/`
(start with `docs/07-build-plan.md`). `web/CLAUDE.md` and `api/CLAUDE.md` add
rules for those folders. Mockups: `docs/design/screens/`.
```

2. **Export the mockup PNGs** from the design canvas (Share › Export) into `docs/design/screens/` with the names in `docs/design/README.md`.

3. **Check `.gitignore`** includes `.env` and `fixtures/mock/generated/`, and commit an `.env.example` with empty values.

Then commit these docs on their own ("docs: web and API spec, design references") before any code, and start Claude Code with the first prompt in `docs/07-build-plan.md`.
