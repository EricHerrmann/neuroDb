# Agent P5 Manual Test Plan — Learning Agent Enhancement

**Status:** Pending
**Tester:** Eric Herrmann
**Scope:** Mode-aware agent behavior, chapter context lookup, discovery suggestions, learning registry UI
**Date:** <!-- fill in on execution -->

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

```bash
git status        # confirm on main, clean working tree
uv sync
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
grep ANTHROPIC_API_KEY .env   # must return a non-empty value
```

Ensure baseline data is available:
```bash
uv run scripts/ingest.py --source openneuro --limit 10
uv run scripts/ingest.py --source dandi --limit 10
```

Start the app:
```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

Open `http://localhost:8501`.

---

## Test 1 — New tabs render

| # | Step | Expected |
|---|------|----------|
| 1.1 | Open the app | Five tabs visible: Dataset Browser, SQL Query, Study Log, Suggestions, Learning Registry |
| 1.2 | Open Suggestions | Page loads without error |
| 1.3 | Open Learning Registry | Page loads without error |

---

## Test 2 — Mode toggle is visible and persistent within session

| # | Step | Expected |
|---|------|----------|
| 2.1 | Open the sidebar | `learning` and `discovery` mode toggle visible above session controls |
| 2.2 | Switch from `learning` to `discovery` | Toggle updates immediately without app error |
| 2.3 | Send a message after switching mode | Agent responds normally in both modes |

---

## Test 3 — Chapter lookup and context setting

| # | Step | Expected |
|---|------|----------|
| 3.1 | Select `Neuroscience, 7th ed. — Augustine et al.` in the Textbook control | Book selector works |
| 3.2 | Enter `Ch12` in Current chapter | Confirmation block shows `Ch12 — Central Visual Pathways` |
| 3.3 | Inspect the confirmation block | Topics include `retinotopy` and `LGN` |
| 3.4 | Click `Set chapter context` | Active chapter caption appears in the sidebar |
| 3.5 | Click `Clear chapter context` | Active chapter caption disappears |

---

## Test 4 — Learning mode stays local-only

Start a session if one is not already active.

In chat, ask:
```text
Search OpenNeuro for retinotopy datasets and queue one for import
```

| # | Step | Expected |
|---|------|----------|
| 4.1 | Mode is set to `learning` | Sidebar shows `learning` selected |
| 4.2 | Agent responds | No crash or exception |
| 4.3 | Suggestions tab after the message | No new import suggestion created automatically from this request |

Expected behavior: in learning mode, the agent only has local DB tools and cannot use discovery tools.

---

## Test 5 — Discovery mode can create suggestions

Switch mode to `discovery`.

In chat, ask:
```text
Search OpenNeuro for retinotopy datasets and suggest one relevant to Ch12
```

| # | Step | Expected |
|---|------|----------|
| 5.1 | Agent responds without error | No API/tool failure shown |
| 5.2 | Open Suggestions tab | A pending item appears in Import Queue or Source Suggestions |
| 5.3 | Suggested item contains reasoning | Entry shows title/source and agent rationale |
| 5.4 | If chapter context was active | Suggested item reflects chapter context such as `Ch12` |

---

## Test 6 — Suggestions tab actions work

Use an item created in Test 5.

| # | Step | Expected |
|---|------|----------|
| 6.1 | Click `Dismiss` on a suggestion | Item disappears from the pending list |
| 6.2 | Create another suggestion in discovery mode | A new pending item appears |
| 6.3 | If a `Promote` button is available for a learning source | Clicking it succeeds and removes the item from pending suggestions |

Optional import test if a safe dataset candidate is available:
| # | Step | Expected |
|---|------|----------|
| 6.4 | Click `Import` on an import-queue item | Ingest completes or a clear error is shown; app does not crash |

---

## Test 7 — Learning Registry shows seeded textbook content

| # | Step | Expected |
|---|------|----------|
| 7.1 | Open Learning Registry | `Books` section is present |
| 7.2 | Expand the Augustine book entry | Chapters 1–15 are listed |
| 7.3 | Inspect Ch12 | Title is `Central Visual Pathways` |
| 7.4 | Inspect chapter topics | Topics include `retinotopy` |

---

## Test 8 — Learning Registry add/remove

| # | Step | Expected |
|---|------|----------|
| 8.1 | Add a manual paper entry with a unique key | Success message shown |
| 8.2 | Verify the new entry appears in Papers & Studies | Entry visible in the registry |
| 8.3 | Click `Remove` on that manual entry | Entry disappears from the registry |

Note: current implementation performs a hard delete because `learning_sources` has no soft-delete/status field.

---

## Pass Criteria

- [ ] `uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q` passes
- [ ] Suggestions and Learning Registry tabs load without error
- [ ] Mode toggle is visible and usable
- [ ] Chapter lookup for `Ch12` shows the correct title and topics
- [ ] Learning mode does not create discovery suggestions from an external-search request
- [ ] Discovery mode can create at least one pending suggestion
- [ ] Suggestions actions (`Dismiss`, and `Promote` if applicable) work without crashing
- [ ] Learning Registry shows the seeded Augustine textbook chapters
- [ ] Manual add/remove in Learning Registry works

**Sign-off:** _________________________________ Date: _____________
