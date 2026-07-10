# Clickable Knowledge Library Citations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the agent's Knowledge Library citations clickable so a click opens the Knowledge Library panel and scrolls to / highlights the referenced paper.

**Architecture:** The agent emits a library citation as an internal Markdown deep link carrying the paper's ID (`/knowledge-library?focus=<id>`). The chat renderer (`MessageBubble`) recognizes internal library links and renders them as in-app react-router navigation instead of new-tab anchors, with a narrowly scoped allow-list. `KnowledgeLibraryPanel` reads the `focus` query param, shows a visible per-card ID, scrolls to and briefly highlights the focused card, and resets the status filter to `all` if the focused paper is hidden.

**Tech Stack:** Python (agent prompt constant), React + TypeScript, react-router-dom v6 (`Link`, `useSearchParams`), Vitest + @testing-library/react, pytest.

## Global Constraints

- No backend, API, or database changes. Frontend + one Python prompt constant only.
- Internal-link allow-list is exact: only paths matching `^/knowledge-library(\?focus=\d+)?$` navigate in-app; everything else keeps existing behavior (external `http(s):`/`mailto:` open in a new tab; all else → `#`). No new URL schemes.
- The paper ID used in the deep link is the `source_id` already returned by `search_knowledge_library` / `search_full_text` results and present on context papers — never invent one.
- Follow the repo's existing hand-rolled Markdown renderer in `MessageBubble.tsx`; do not add a Markdown library.
- Frontend tests that render a component using `Link`/`useSearchParams` must provide a router context (`MemoryRouter`).

---

### Task 1: Manual test plan (phase-gate artifact)

Per CLAUDE.md, the manual test plan is created before implementation and registered in `docs/projectStatus.md` in the same step.

**Files:**
- Create: `docs/testsPlans/manualTestPlan_clickable_kl_citations.md`
- Modify: `docs/projectStatus.md` (Active Plans / Specs reference table)

- [x] **Step 1: Write the manual test plan**

Create `docs/testsPlans/manualTestPlan_clickable_kl_citations.md` with:

```markdown
# Manual Test Plan — Clickable Knowledge Library Citations

## Prerequisites
1. Run `uv run pytest tests/ -q`. Pass criteria: no new failures beyond those already tracked in `docs/testLog.md`.
2. Build/serve the frontend against the local API with an approved Knowledge Library paper that has an ID visible in the panel.

## Cases
- **CK1 — Clickable citation navigates + focuses.** In Tutor chat, ask a question that cites a Knowledge Library paper. Expected: the citation renders as a link; clicking it switches to the Knowledge Library panel, scrolls the referenced card into view, and briefly highlights it. No full-page reload.
- **CK2 — Visible ID.** Each Knowledge Library card shows its numeric ID (matching the ID the agent cites).
- **CK3 — Hidden-by-filter recovery.** Set the status filter to a value that hides the target paper, then click a citation for that paper. Expected: filter resets to All and the card is shown + highlighted.
- **CK4 — Link safety.** Confirm non-library links in chat still open in a new tab, and no citation link points outside `/knowledge-library`.
```

- [x] **Step 2: Register the plan in projectStatus**

Add this row under `**Active Plans / Specs**` in `docs/projectStatus.md`:

```markdown
| `docs/testsPlans/manualTestPlan_clickable_kl_citations.md` | Clickable Knowledge Library citations manual gate — CK1 clickable citation navigates + scrolls/highlights, CK2 visible per-card ID, CK3 hidden-by-filter recovery, CK4 link safety; pending verification |
```

- [ ] **Step 3: Commit**

```bash
git add docs/testsPlans/manualTestPlan_clickable_kl_citations.md docs/projectStatus.md
git commit -m "docs: manual test plan for clickable Knowledge Library citations"
```

---

### Task 2: Agent emits library citations as internal deep links

**Files:**
- Modify: `src/neurodb/agents/behavior_instructions.py:6-26` (`CITATION_PROVENANCE_RULE`)
- Test: `tests/unit/test_behavior_instructions.py:21-25`

**Interfaces:**
- Produces: updated `CITATION_PROVENANCE_RULE` string instructing the agent to render a Knowledge Library citation as `[<Title> (Knowledge Library · <level>)](/knowledge-library?focus=<id>)` using the result's `source_id`. Consumed by `frontend/src/components/MessageBubble.tsx` (Task 3), which parses that link shape.

- [x] **Step 1: Update the failing test**

Replace the body of `test_citation_rule_mentions_key_elements` in `tests/unit/test_behavior_instructions.py`:

```python
def test_citation_rule_mentions_key_elements():
    text = CITATION_PROVENANCE_RULE
    assert "Knowledge Library" in text
    assert "full text" in text
    assert "URL" in text or "url" in text
    # Knowledge Library citations must be clickable internal deep links carrying the paper id.
    assert "/knowledge-library?focus=" in text
    assert "source_id" in text
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_behavior_instructions.py::test_citation_rule_mentions_key_elements -v`
Expected: FAIL — assertion error on `"/knowledge-library?focus="` not in text.

- [x] **Step 3: Update the rule to emit the deep link**

In `src/neurodb/agents/behavior_instructions.py`, change the Knowledge Library branch of `CITATION_PROVENANCE_RULE` so the whole constant reads:

```python
CITATION_PROVENANCE_RULE = (
    "When you cite a specific paper, mark its source provenance inline, right "
    "after the paper. If the paper came from a Knowledge Library result (a "
    "search_knowledge_library result, or a paper in the provided local/topic "
    "context), render the citation as a clickable Markdown link to that paper "
    "in the Knowledge Library panel, using the result's source_id: "
    "'[<Title> (Knowledge Library · <level>)](/knowledge-library?focus=<source_id>)', "
    "where <level> is that result's data_tier rendered as 'metadata', 'abstract', "
    "or 'full text' and <source_id> is the integer id from the tool result or "
    "provided local context. If the paper is not in the Knowledge Library (for "
    "example a search_literature result), instead link it with its URL using "
    "Markdown, e.g. [Title](https://example.org). If a cited paper is neither in "
    "the Knowledge Library nor has a URL, write '(not in Knowledge Library)' and "
    "apply the usual model-knowledge / needs-verification labeling. Never state a "
    "Knowledge Library status or level, or a source_id, that did not come from a "
    "tool result or the provided local context."
)
```

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_behavior_instructions.py -v`
Expected: PASS (all tests in file).

- [x] **Step 5: Commit**

```bash
git add src/neurodb/agents/behavior_instructions.py tests/unit/test_behavior_instructions.py
git commit -m "feat(agent): emit Knowledge Library citations as internal deep links"
```

---

### Task 3: MessageBubble renders internal library links as in-app navigation

**Files:**
- Modify: `frontend/src/components/MessageBubble.tsx:1-25` (imports, `internalHref`, `renderInline` link branch)
- Test: `frontend/src/components/MessageBubble.test.tsx`

**Interfaces:**
- Consumes: the link shape `[label](/knowledge-library?focus=<id>)` produced by Task 2.
- Produces: internal library links rendered as react-router `<Link to={path}>` (renders an `<a href={path}>` without `target="_blank"`); all other links unchanged.

- [x] **Step 1: Write the failing tests**

Add to `frontend/src/components/MessageBubble.test.tsx` (add `import { MemoryRouter } from 'react-router-dom'` at the top):

```tsx
it('renders internal library citations as same-page navigation links', () => {
  render(
    <MemoryRouter>
      <MessageBubble
        message={{
          role: 'assistant',
          content: '[Hopfield (Knowledge Library · full text)](/knowledge-library?focus=9)',
        }}
      />
    </MemoryRouter>,
  )

  const link = screen.getByRole('link', { name: /Hopfield/ })
  expect(link).toHaveAttribute('href', '/knowledge-library?focus=9')
  expect(link).not.toHaveAttribute('target', '_blank')
})

it('does not treat non-library internal-looking paths as navigation', () => {
  render(
    <MemoryRouter>
      <MessageBubble
        message={{ role: 'assistant', content: '[Nope](/other-route?focus=9)' }}
      />
    </MemoryRouter>,
  )

  expect(screen.getByRole('link', { name: 'Nope' })).toHaveAttribute('href', '#')
})
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/MessageBubble.test.tsx`
Expected: FAIL — internal link renders with `href="#"` and/or `target="_blank"`.

- [x] **Step 3: Implement internal-link detection + Link rendering**

In `frontend/src/components/MessageBubble.tsx`, add one new import at the top of the file (the existing `import type { Message } from '../hooks/useChat'` line stays):

```tsx
import { Link } from 'react-router-dom'
```

Add the allow-list helper next to the existing `safeHref` function (leave `safeHref` unchanged — do not re-declare it):

```tsx
const INTERNAL_LIBRARY_PATH = /^\/knowledge-library(\?focus=\d+)?$/

function internalHref(href: string): string | null {
  const trimmed = href.trim()
  return INTERNAL_LIBRARY_PATH.test(trimmed) ? trimmed : null
}
```

Then in `renderInline`, replace the existing link branch (the `if (link) { ... }` block) with:

```tsx
    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
    if (link) {
      const internal = internalHref(link[2])
      if (internal) {
        return <Link key={index} to={internal}>{link[1]}</Link>
      }
      return <a key={index} href={safeHref(link[2])} target="_blank" rel="noreferrer">{link[1]}</a>
    }
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/MessageBubble.test.tsx`
Expected: PASS (new tests plus the existing MessageBubble/EvidenceLens tests, which render no internal links and need no router).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/MessageBubble.tsx frontend/src/components/MessageBubble.test.tsx
git commit -m "feat(chat): navigate in-app for internal Knowledge Library citation links"
```

---

### Task 4: KnowledgeLibraryPanel focus param — visible ID, scroll, highlight, filter recovery

**Files:**
- Modify: `frontend/src/pages/KnowledgeLibraryPanel.tsx:1` (imports), `:465-489` (component state + focus effect), `:624-636` (card anchor id, visible ID, highlight style)
- Test: `frontend/src/pages/KnowledgeLibraryPanel.test.tsx:1-16` (wrapper) plus new cases

**Interfaces:**
- Consumes: `focus` query param set by the Task 3 `<Link to="/knowledge-library?focus=<id>">` navigation.
- Produces: focused card scrolled into view + highlighted; each card shows `#<id>`.

- [x] **Step 1: Write the failing tests**

In `frontend/src/pages/KnowledgeLibraryPanel.test.tsx`, add `import { MemoryRouter } from 'react-router-dom'` and update `makeWrapper` to nest a router, then add two cases. Replace `makeWrapper` with:

```tsx
function makeWrapper(data: unknown, libraryFiles: unknown = [], initialEntry = '/knowledge-library') {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  qc.setQueryData(['knowledge-library', 'all'], data)
  qc.setQueryData(['library-files'], libraryFiles)
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(
      MemoryRouter,
      { initialEntries: [initialEntry] },
      React.createElement(QueryClientProvider, { client: qc }, children),
    )
}
```

Add these cases (a paper fixture with `id: 2` shaped like the others already used in the file):

```tsx
it('shows the numeric id on each card', () => {
  const paper = { id: 2, title: 'Neuroplasticity', source_type: 'paper', topic_context: 't', status: 'approved', data_tier: 'full_text', full_text_status: 'verified', year: 2020, doi: null, url: null, summary: null, reference_counts: {} }
  render(<KnowledgeLibraryPanel />, { wrapper: makeWrapper([paper]) })
  expect(screen.getByText('#2')).toBeTruthy()
})

it('scrolls to and highlights the focused paper', () => {
  const scrollSpy = vi.fn()
  Element.prototype.scrollIntoView = scrollSpy
  const paper = { id: 2, title: 'Neuroplasticity', source_type: 'paper', topic_context: 't', status: 'approved', data_tier: 'full_text', full_text_status: 'verified', year: 2020, doi: null, url: null, summary: null, reference_counts: {} }
  render(<KnowledgeLibraryPanel />, { wrapper: makeWrapper([paper], [], '/knowledge-library?focus=2') })
  expect(scrollSpy).toHaveBeenCalled()
  expect(screen.getByTestId('kl-card-2').getAttribute('data-focused')).toBe('true')
})
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/pages/KnowledgeLibraryPanel.test.tsx`
Expected: FAIL — no `#2` text; no `kl-card-2` test id / `data-focused`.

- [x] **Step 3: Add focus state, effect, and card rendering**

In `frontend/src/pages/KnowledgeLibraryPanel.tsx`:

Update the import line 1 and add the router import:

```tsx
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
```

Inside `KnowledgeLibraryPanel`, after the `statusFilter` state, add:

```tsx
  const [searchParams] = useSearchParams()
  const focusId = Number(searchParams.get('focus')) || null
  const [highlightedId, setHighlightedId] = useState<number | null>(null)
```

After the existing `useEffect` that tracks pending (around line 486-489), add the focus effect:

```tsx
  useEffect(() => {
    if (focusId === null) return
    const present = data.some(item => item.id === focusId)
    if (!present) {
      if (statusFilter !== 'all') setStatusFilter('all')
      return
    }
    const el = document.getElementById(`kl-paper-${focusId}`)
    if (!el) return
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setHighlightedId(focusId)
    const timer = setTimeout(() => setHighlightedId(null), 2500)
    return () => clearTimeout(timer)
  }, [focusId, data, statusFilter])
```

Update the card container (the `data.map(item => (` block, around line 624-628) to add the anchor id, test id, visible ID, and highlight:

```tsx
      ) : data.map(item => (
        <div
          key={item.id}
          id={`kl-paper-${item.id}`}
          data-testid={`kl-card-${item.id}`}
          data-focused={highlightedId === item.id ? 'true' : 'false'}
          style={{
            border: highlightedId === item.id ? '2px solid #f59e0b' : '1px solid #e2e8f0',
            borderRadius: 8,
            padding: 12,
            marginBottom: 8,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, color: '#94a3b8' }}>#{item.id}</span>
            <span style={{ fontWeight: 600, fontSize: 13 }}>{item.title}</span>
            <TierBadge tier={item.data_tier} />
            {item.full_text_status === 'verified' && <FullTextStatusBadge />}
          </div>
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/KnowledgeLibraryPanel.test.tsx`
Expected: PASS (new cases plus existing ones, now wrapped in `MemoryRouter`).

- [x] **Step 5: Run the full frontend suite and typecheck**

Run: `cd frontend && npx vitest run && npx tsc --noEmit`
Expected: PASS, no type errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/KnowledgeLibraryPanel.tsx frontend/src/pages/KnowledgeLibraryPanel.test.tsx
git commit -m "feat(library): focus, scroll-to, highlight, and show id for cited papers"
```

---

### Task 5: Full verification

- [x] **Step 1: Backend tests**

Run: `uv run pytest tests/ -q`
Expected: no new failures beyond those tracked in `docs/testLog.md`.

- [x] **Step 2: Frontend tests + typecheck**

Run: `cd frontend && npx vitest run && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 3: Manual gate**

Execute `docs/testsPlans/manualTestPlan_clickable_kl_citations.md` (CK1–CK4). When it passes, move it to `docs/testsPlans/completedAndPassedTestPlans/` and update the `docs/projectStatus.md` reference row to signed-off, in the same commit.

## Notes for the implementer

- `PaperItem` fixtures in the KL test file already exist for other cases — reuse an existing fixture's shape rather than the minimal inline one if the type requires more fields; the two fields this feature adds usage of are `id` and existing display fields.
- `react-router-dom` is already a dependency (`main.tsx`/`App.tsx` use it); no install needed.
- Do not broaden `internalHref`. If future routes need deep links, extend the allow-list deliberately in a separate change.
