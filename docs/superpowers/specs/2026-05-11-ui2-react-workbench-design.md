# UI-2 React Workbench Design

**Date:** 2026-05-11
**Status:** Approved
**Author:** Eric Herrmann

---

## Goal

Migrate the NeuroDb UI from Streamlit to a Vite + React SPA consuming the FastAPI backend, preserving the current two-column layout (chat left, tabbed panels right) with all 7 panels functional. No layout redesign in this phase — infrastructure migration only. Layout changes (activity rail, resizable panes) are deferred.

---

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Build tool | Vite | Fast HMR, simple proxy config, straightforward WSL2 support |
| UI framework | React 18 | Component model fits tabbed workbench; large ecosystem |
| Routing | React Router v7 (SPA mode) | URL-based panel switching, `createBrowserRouter` + `RouterProvider` |
| Server state | TanStack Query v5 | Eliminates per-panel loading/error/refetch boilerplate across 7 panels |
| HTTP | native `fetch` | Sufficient for JSON routes and ReadableStream SSE |
| Language | TypeScript | Type safety across API boundary |

---

## Architecture

### Directory Layout

```
neuroDb/
├── frontend/                    ← Vite + React project (new)
│   ├── src/
│   │   ├── api/                 ← typed fetch wrappers, one file per route group
│   │   ├── hooks/
│   │   │   └── useChat.ts       ← SSE streaming hook
│   │   ├── pages/               ← one file per panel
│   │   └── main.tsx             ← QueryClientProvider + RouterProvider root
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
│
└── src/neurodb/api/
    ├── routes/
    │   ├── status.py            ← exists
    │   ├── preferences.py       ← exists
    │   ├── research.py          ← exists
    │   ├── chat.py              ← exists
    │   ├── study_log.py         ← new
    │   ├── suggestions.py       ← new
    │   ├── datasets.py          ← new
    │   ├── registry.py          ← new
    │   ├── knowledge_library.py ← new
    │   └── sql.py               ← new
    └── app.py                   ← add StaticFiles mount for production
```

### Dev Workflow

Two terminals during development:
- `vite dev` on port 5173
- `uv run uvicorn neurodb.api.app:app_factory --factory --port 8001`

Vite proxies all `/api/*` requests to `http://localhost:8001`. No CORS configuration needed. The React app is always fetching from its own origin.

```ts
// vite.config.ts (key excerpt)
server: {
  proxy: { '/api': { target: 'http://localhost:8001', changeOrigin: true } },
  watch: { usePolling: true, interval: 100 }  // required for WSL2
}
```

### Production

`vite build` outputs to `frontend/dist/`. `app.py` mounts that directory as `StaticFiles(html=True)` at `/`. Single `uvicorn` process serves both the API and the React bundle.

```python
# app.py addition (production only, guarded by dist existence)
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")
```

---

## New FastAPI Routes

| Panel | Method | Path | Description |
|-------|--------|------|-------------|
| Study Log | GET | `/api/study-log` | Session list with topic, date, turn count |
| Suggestions | GET | `/api/suggestions` | Active study recommendations |
| Datasets | GET | `/api/datasets` | Ingested studies/datasets from DB |
| Registry | GET | `/api/registry` | Connector registry entries |
| Knowledge Library | GET | `/api/knowledge-library` | Sources (approved + pending review) |
| Knowledge Library | POST | `/api/knowledge-library/{id}/approve` | Approve pending source |
| Knowledge Library | POST | `/api/knowledge-library/{id}/reject` | Reject pending source |
| SQL | POST | `/api/sql/execute` | Execute ad-hoc SQL, return rows as JSON |

Existing routes (status, preferences, research, chat/SSE) are unchanged.

---

## Components

```
App
├── Sidebar                    ← agent mode dropdown, session list
├── ChatPanel                  ← always rendered, left column
│   ├── MessageList
│   ├── MessageBubble
│   └── ChatInput
└── PanelArea                  ← right column
    ├── PanelNav               ← tab bar, each tab is a <NavLink>
    └── <Outlet />             ← React Router renders active panel
        ├── /suggestions       → SuggestionsPanel
        ├── /study-log         → StudyLogPanel
        ├── /datasets          → DatasetsPanel
        ├── /registry          → RegistryPanel
        ├── /knowledge-library → KnowledgeLibraryPanel
        ├── /research          → ResearchPanel
        └── /sql               → SqlPanel
```

`ChatPanel` renders outside the router outlet — it stays mounted while the user switches panels. `PanelNav` uses `<NavLink>` for active-tab highlighting.

---

## Data Flow

### Panel Reads (TanStack Query)

```ts
// Any panel — standard pattern
const { data, isLoading, isError, error } = useQuery({
  queryKey: ['datasets'],
  queryFn: () => fetch('/api/datasets').then(r => r.json()),
});
```

TanStack caches results and re-fetches on window focus. Each panel owns one query — no shared state manager needed.

### Chat Streaming (`useChat` hook)

```
ChatInput.onSubmit
  → fetch POST /api/chat with { message, session_id, agent_mode }
  → ReadableStream reader loop
  → text_delta event → append chunk to last message in state
  → done event       → mark message complete, re-enable input
  → network error    → show inline error bubble, re-enable input
```

`useChat` is plain React state (`useState` + `useRef`). It does not go through TanStack Query because SSE is not a cacheable request.

### Mutations (TanStack Query)

```ts
const approveMutation = useMutation({
  mutationFn: (id: string) =>
    fetch(`/api/knowledge-library/${id}/approve`, { method: 'POST' }),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['knowledge-library'] }),
});
```

Pattern is identical for reject, SQL execute, and metrics snapshot.

### Session Continuity

`session_id` is React state, initialized from `GET /api/preferences` on app load. Clicking a session in the sidebar sets `session_id` in state; the `useChat` hook reads it on the next send. The study-log panel uses `useQuery(['study-log'])` — `useChat` calls `queryClient.invalidateQueries({ queryKey: ['study-log'] })` after each completed assistant turn so the session list stays current.

---

## Error Handling

- Panel query errors: each panel renders an inline error message (`isError` + `error.message`). Other panels are unaffected.
- Chat errors: failed message bubble with error text inline in the conversation.
- SQL errors: the API returns the DB error string in the response body; the SQL panel surfaces it directly below the query input (useful for syntax errors).
- Mutation errors: inline near the triggering action (e.g., "Approve failed" beside the source row).

---

## Testing

### Backend (pytest)

New route files follow existing patterns (`TestClient(create_app(engine))`, SQLite fixture, assert status + response shape). SSE chat route: assert `content-type: text/event-stream` header, parse streamed lines, assert `text_delta` and `done` events. Target: ~60–80 new automated tests (10 routes × ~6 cases each).

### Frontend (Vitest + React Testing Library)

- `useChat`: mock `fetch`, synthesize ReadableStream with `text_delta` + `done` chunks, assert `messages` state
- Panel components: pre-load TanStack `QueryClient` cache with fixture data, assert rendered rows
- `KnowledgeLibraryPanel` mutation: mock `fetch`, fire approve, assert `invalidateQueries` called

No E2E (Cypress) in UI-2 — deferred to UI-3 when Streamlit retirement begins.

### Manual Test Plan

Written before implementation begins (per CLAUDE.md). Ten tests:

| Test | What |
|------|------|
| T1 | `uv run pytest tests/ -q` — no new failures |
| T2 | `vite dev` + `uvicorn app_factory` start; Vite proxy resolves `/api/status` |
| T3 | Chat panel streams a response from the research agent |
| T4 | Suggestions panel loads data |
| T5 | Study Log panel shows session history |
| T6 | Datasets panel loads ingested studies |
| T7 | Registry panel loads connector entries |
| T8 | Knowledge Library panel loads sources; approve/reject fire and list updates |
| T9 | Research panel loads metrics, questions, hypotheses |
| T10 | SQL panel executes a query and renders rows |

---

## Out of Scope (UI-2)

- Activity rail navigation
- Resizable panes
- Monaco editor for SQL
- Streamlit retirement
- E2E / Cypress tests
- Provider selection UI (deferred per Config Control epoch plan)
