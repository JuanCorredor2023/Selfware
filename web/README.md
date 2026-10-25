# Atlas dashboard (web/)

React + Vite dashboard for Atlas (repo name: Selfware). It shows the live
flat-vs-PARA toggle (A1), the provenance behind each answer (A2) and the cost
panel (A4). The design source of truth is [`DESIGN.md`](DESIGN.md).

## Run it

Requirements: Node 20+ and the API running (see the repo root).

```bash
# terminal 1, from the repo root
uv run uvicorn selfware.api.app:app --reload   # http://localhost:8000

# terminal 2
cd web
npm install
npm run dev                           # http://localhost:5173
```

No backend? Run the dashboard on its built-in mocks:

```bash
VITE_USE_MOCKS=true npm run dev
```

## Configuration

Both variables are optional. Copy `.env.example` to `.env.local` to set them.

| Variable | Default | Meaning |
| --- | --- | --- |
| `VITE_API_URL` | `http://localhost:8000` | Base URL of the FastAPI app. Set it to the deployed API URL when deploying. |
| `VITE_USE_MOCKS` | `false` | `true` makes the dashboard ignore the API and use `src/mocks/`. |

The API only allows the origins listed in `src/selfware/api/app.py` (CORS). Update that list
when the dashboard gets a public URL.

### Backend modes

The API answers from a mock unless told otherwise (no keys, no credits):

```bash
# real agent + retrieval + Token Factory (needs NEBIUS_API_KEY and an indexed Chroma folder)
SELFWARE_AGENT=real SELFWARE_CHROMA_PATH=chroma_data \
  uv run uvicorn selfware.api.app:app
```

`uv run python -m scripts.index_emails --demo` shows what indexing a dozen invented emails
would cost; add `--yes` to actually do it. The PARA tree on the dashboard is still mock data.

## Layout of `src/`

| Path | What lives there |
| --- | --- |
| `api/client.js` | The only place that talks to the API: `askQuestion`, `fetchPara`, `fetchCost`. Switches to mocks with `VITE_USE_MOCKS`. |
| `views/` | Screens. Today only `DashboardView`. |
| `components/` | UI pieces (`AskBox`, `AnswerCard`, `ProvenanceList`, `ParaTracker`, `CostPanel`, ...). |
| `lib/` | Pure helpers: confidence bands, cost aggregation, formatting, `useResource`. |
| `mocks/` | Fake data shaped exactly like the API's responses. |
| `styles/tokens.css` | Design tokens (colors, type, spacing). Components use only these variables. |

## Scripts

```bash
npm run dev      # dev server with hot reload
npm run build    # production build into dist/
npm run lint     # oxlint
```
