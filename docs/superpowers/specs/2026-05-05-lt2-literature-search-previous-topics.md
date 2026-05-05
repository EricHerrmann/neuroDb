# LT-2: Literature Search + Previous Topics — Design Spec

**Date:** 2026-05-05
**Epoch plan:** `docs/ClaudeLearnEpochPlan.md`
**Status:** Approved — ready for implementation planning
**Dependency:** The Pre-LT-2 sidebar migration must be implemented before LT-2 begins. The fixed-pane layout portion failed manual testing in Streamlit and is deferred to a post-LT-3 UI shell architecture phase; LT-2 proceeds in the existing Streamlit UI with accepted manual-testing friction.

---

## Goal

Replace the `search_literature` stub with live PubMed and Semantic Scholar API calls. Surface a persistent, user-browsable Previous Topics panel that auto-loads the most recent session at startup. Polish the Knowledge Library review UX and add connector request visibility. Extend the sidebar configuration panel with new sections.

---

## Overview

LT-2 has six work areas, all building on the agent architecture and knowledge library established in LT-1. The literature search client is the central new module — it gives `search_literature` a real implementation while keeping the agent-facing interface unchanged. Previous Topics turns the `chat_sessions` table (populated since LT-1) into a visible, navigable session history. Knowledge Library polish and connector visibility are targeted UX improvements from the LT-1 test log.

---

## 1. LiteratureSearchClient

### 1.1 Module

New file: `src/neurodb/literature_client.py`

`LiteratureSearchClient` is a standalone class that wraps PubMed E-utilities and Semantic Scholar APIs behind a single interface. Neither API requires a key for basic access. Keys are optional: if present, they raise rate limits and unlock higher-volume queries. The client uses whichever sources have available keys, always returning a normalized result list.

### 1.2 Result Schema

Every result, regardless of source, is normalized to:

```python
{
    "title": str,
    "doi": str | None,
    "abstract": str | None,      # truncated to ~300 chars
    "source_type": str,          # "paper", "review", "preprint"
    "year": int | None,
    "citation_count": int | None, # Semantic Scholar only
    "source": str,               # "pubmed" | "semantic_scholar"
}
```

### 1.3 API Details

**PubMed (NCBI E-utilities):**
- `esearch.fcgi` to get PMIDs for a query (up to 10 results)
- `efetch.fcgi` to retrieve abstracts and metadata
- Rate limit: 3 requests/second without key, 10/second with `NCBI_API_KEY`
- Key injected as `api_key` parameter when present

**Semantic Scholar:**
- `/graph/v1/paper/search` endpoint
- Returns relevance score, citation count, open-access status
- Rate limit: 100 requests/minute without key, higher with `SEMANTIC_SCHOLAR_API_KEY`
- Key injected as `x-api-key` header when present

Both sources are queried with the same query string. Results are deduplicated by DOI before returning (DOI exact match). If a source's API is unavailable or times out (5-second timeout), it is skipped gracefully — the other source still returns results.

### 1.4 Observability Hook — `literature_searches` Table

Every `search()` call logs one row to a new `literature_searches` SQLite table before returning:

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `query` | Text | The query string sent |
| `pubmed_count` | Integer | Results fetched from PubMed |
| `semantic_scholar_count` | Integer | Results fetched from Semantic Scholar |
| `results_json` | Text | Full normalized result list (all fetched, not just queued) |
| `searched_at` | String(32) | ISO timestamp |

No UI in LT-2. The table accumulates silently for future monitoring. When the agent's filtering behavior needs auditing (LT-3+), the full result set vs. the `knowledge_sources` pending queue reveals what was filtered and why.

### 1.5 `search_literature` Tool Update

`NeuroTutorAgent._execute_search_literature()` is updated to call `LiteratureSearchClient.search(query)`. The tool returns the normalized result list as JSON — same structure as before, now backed by live data instead of an empty list. The agent reads the results, judges relevance, and calls `queue_source` for each relevant entry. The agent's filtering judgment is intentional — the log captures what it had to work with.

### 1.6 `.env.example` Additions

```
# Literature search API keys (optional — falls back to unauthenticated if absent)
NCBI_API_KEY=
SEMANTIC_SCHOLAR_API_KEY=

# Knowledge Library near-duplicate warning threshold (cosine distance, 0.0–1.0)
# Lower = stricter match required before warning is shown. Default: 0.15
NEURODB_DEDUP_THRESHOLD=0.15
```

---

## 2. Previous Topics Panel

### 2.1 Behavior

**App startup:** The most recent `ChatSession` row is retrieved and its summary is injected as `prior_context` into the agent before the first message. This replaces the LT-1 auto-session mechanic of waiting for the first message to trigger context retrieval. If no sessions exist (cold start), the agent starts with no prior context.

**Session list:** The Previous Topics section in the sidebar lists past sessions in reverse chronological order (most recent at top). Each entry shows: inferred topic label, date, mode badge (Local DB / External DB / Neuro-Tutor), turn count.

**Load on demand:**
1. User clicks a session in the list
2. If current conversation has ≥3 user turns: auto-save runs (same path as Clear — generates summary, stores in `AgentContextStore`, writes `ChatSession` row)
3. Current transcript clears, `api_messages` resets, `session_id` cleared
4. Selected session's summary is loaded as `prior_context` into the agent
5. UI reflects the newly loaded context (sidebar shows selected topic label)

If current conversation has <3 user turns: transcript clears immediately with no save.

**Editable topic labels:** Each session entry in the list has an inline edit affordance. Clicking the label opens an inline text input. Pressing Enter or clicking away saves the updated label back to `ChatSession.inferred_topic`. The edit is immediate — no confirmation dialog.

### 2.2 Sidebar Section

The Previous Topics section is added to the sidebar below the Agent and Context sections (established in pre-LT-2). It is a collapsible `st.expander` expanded by default. Shows the 10 most recent sessions; a "Show all" expander reveals the full list.

### 2.3 Auto-Load Change to Session Manager

`SessionManager` gains a `get_most_recent_context()` method that reads the most recent `ChatSession` row and retrieves its summary from `AgentContextStore` by `session_id`. Called once at app startup in `app.py`. If the collection is empty or the session's summary is not found, returns an empty string.

---

## 3. Sidebar Configuration Panel Extensions

The pre-LT-2 sidebar structure (`Agent`, `Context`) gains two new sections in LT-2:

### 3.1 Previous Topics Section
Described in §2.2 above.

### 3.2 Connections Section

A collapsed `st.expander` labeled **Connections**. Contains:

**API key status indicators:**
```
NCBI (PubMed):          ● present / ○ not set
Semantic Scholar:        ● present / ○ not set
```
Status is read from `os.environ` at render time. No key entry from the UI — keys live in `.env` only. This is a read-only visibility surface.

**Connector requests:**
```
Pending connector requests: N  [→ Suggestions tab]
```
Count is a live query against `source_suggestions` where `status = "pending"` and `suggestion_type = "new_source"`. Clicking "Suggestions tab" is a caption pointing the user to the Suggestions workspace tab where the full list lives — not a navigation action (Streamlit doesn't support tab deep-linking easily).

**Reserved slots (not rendered in LT-2):**
- Model selection (LT-3+)
- User preference rules (LT-3+)
- Config file management UI (LT-3+, pending config file architecture decision)

### 3.3 Full Sidebar Structure (LT-2 end state)

```
▼ Agent
   Mode: [Local DB] [External DB] [Neuro-Tutor]

▼ Context  (only when mode ≠ neuro_tutor)
   Textbook: [dropdown]
   Chapter: [text input]
   Active: Ch12 — ...
   [Clear chapter context]

▼ Previous Topics
   [Topic label] · 2026-05-05 · Neuro-Tutor · 7 turns
   [Topic label] · 2026-05-04 · Local DB · 12 turns
   ...

▼ Connections  (collapsed by default)
   NCBI (PubMed):        ● present
   Semantic Scholar:     ○ not set
   Pending connectors: 2  → see Suggestions tab

DB: neurodb.duckdb
Session: active / none
```

---

## 4. Semantic Near-Duplicate Detection

Before the Approve button renders on a pending Knowledge Library source, the page runs a ChromaDB similarity query against the `knowledge_library` collection (approved sources only).

**Threshold:** Read from `NEURODB_DEDUP_THRESHOLD` env var, defaulting to `0.15`. If cosine distance between the pending source's title+topic_context and any approved entry is ≤ threshold, an inline warning is shown:

> *"Similar to approved source: [title] — you can still approve."*

The user can approve anyway. The warning is informational — it does not block the Approve button.

**Config file architecture** for persistent threshold editing is deferred to LT-3, logged in decisions log.

---

## 5. Knowledge Library Card Polish

Addresses LOG-004 and LOG-005 from the test log.

**Pending source cards (before approval):**
- Title renders as normal-weight text (`st.markdown` with `**bold**` for the title, not `st.subheader`)
- Source type and topic context visible at card level without expanding
- DOI renders as a clickable hyperlink: `https://doi.org/{doi}` — opens in new tab
- URL (if present) renders as a clickable hyperlink
- Near-duplicate warning (§4) appears between the metadata and the Approve/Reject buttons
- Card layout (top to bottom): title · source type · topic context · DOI/URL links · [dedup warning if applicable] · [Approve] [Reject]

**Approved source cards (library browser):**
- Same title/metadata treatment as pending cards
- Summary displayed in an `st.expander` ("Show summary") rather than inline, to keep the list scannable
- DOI/URL links present

---

## 6. Connector Request Visibility

The `source_suggestions` table (populated by `suggest_new_source` tool in External DB mode) gains a clearer surface:

**Sidebar Connections section:** Count of pending connector requests as described in §3.2.

**Suggestions workspace tab:** The existing Suggestions tab gains a visual section divider separating:
- **Dataset Import Requests** — `import_queue` rows (existing)
- **Connector Requests** — `source_suggestions` rows with `suggestion_type = "new_source"` (existing data, new section header and visual separation)

No schema changes. No new tools. This is purely a UI organization improvement making existing data more discoverable.

**CF-1 (Connector Framework Architecture)** — logged in `projectStatus.md` as a planned post-LT-2 sprint. Scope: connector plugin system so adding a new connector is a single file + registration step, with no changes to the ingest pipeline, schema, or UI.

---

## 7. Schema Additions

| Table | Change |
|-------|--------|
| `literature_searches` | New table — observability log for all `search_literature` calls |

```python
class LiteratureSearch(Base):
    __tablename__ = "literature_searches"

    id: Mapped[int] = mapped_column(Integer, Sequence("literature_searches_id_seq"), primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    pubmed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    semantic_scholar_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    results_json: Mapped[str] = mapped_column(Text, nullable=False)
    searched_at: Mapped[str] = mapped_column(String(32), nullable=False)
```

No other schema changes. `ChatSession` (LT-1) and `KnowledgeSource` (LT-1) are already in place.

---

## 8. Testing

**Unit tests:**
- `LiteratureSearchClient` with mocked `requests` calls — PubMed response parsing, Semantic Scholar response parsing, dedup by DOI across sources, graceful degradation when one source times out, log row written per call
- `get_most_recent_context()` — returns context when sessions exist, returns empty string on cold start
- Auto-save threshold — save triggered at ≥3 turns, not triggered at <2 turns
- Dedup threshold read from env var; default applied when env var absent
- Knowledge Library card: dedup warning shown at threshold, not shown above threshold
- `LiteratureSearch` table auto-created by `init_db`

**Integration tests:**
- Full search → agent queues selected results → pending queue populated → approve → embedded in `knowledge_library` collection
- Previous Topics load: session selected → auto-save runs (if ≥3 turns) → context loaded → transcript cleared
- `.env.example` contains all three new keys

**Structural tests:**
- `literature_client.py` defines `LiteratureSearchClient` with `search(query)` method
- Sidebar module contains Previous Topics section and Connections section
- Suggestions tab contains both section headers

**Existing tests:** All 255 tests must continue to pass.

---

## 9. Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-05 | `LiteratureSearchClient` wraps both APIs behind one interface | Swapping in additional sources (bioRxiv, OpenAlex) requires no agent or tool changes |
| 2026-05-05 | Agent filters `search_literature` results autonomously | Reasonable at current scale; `literature_searches` log provides future auditing capability |
| 2026-05-05 | `NEURODB_DEDUP_THRESHOLD` as env var, not config file | Zero new infrastructure; fits existing `.env` pattern; config file architecture deferred to LT-3 |
| 2026-05-05 | Previous Topics auto-load most recent session at startup | More predictable than semantic search on first message; user sees exactly what context is loaded |
| 2026-05-05 | Connector request visibility only (CF-1 deferred) | Connector framework architecture is a separate sprint; existing `source_suggestions` data is sufficient for visibility |

---

## 10. Out of Scope for LT-2

- Config file architecture and UI for persistent settings (LT-3)
- `literature_searches` monitoring UI (LT-3)
- CF-1 connector framework architecture (post-LT-2 sprint)
- Model/agent identity display and model selection (post-LT-2)
- bioRxiv, OpenAlex, or other literature sources beyond PubMed and Semantic Scholar
- Full-text PDF indexing
- User-defined search filters (MeSH terms, date ranges, citation thresholds)
