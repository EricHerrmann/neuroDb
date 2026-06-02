# Groupings Phase 3b — UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the Phase 3a backend in the Research UI — repoint the topic filter to the new `/api/research/groupings` endpoint, mark proposed ("new") suggestions on the pending chips, and add a small topic-hierarchy curation view for re-parenting — all additive, with no change to existing confirmed/pending chip behavior.

**Architecture:** All three changes are additive and API-mediated; no backend work. The filter query swaps a raw `executeSQL("SELECT … FROM topics")` for the typed `api.listGroupings(...)` client call. The pending chips read the additive `proposed` field already returned by 3a and render a "new" badge; confirm/dismiss reuse the existing mutations (the backend already activates/cleans up proposed groupings). The hierarchy view is a new focused component, `GroupingHierarchy`, rendered inside `ResearchPanel`.

**Tech Stack:** React 18 + TypeScript, `@tanstack/react-query` v5, Vite, Vitest + `@testing-library/react`.

**Spec:** `docs/superpowers/specs/2026-06-01-groupings-phase3-question-cutover-design.md` (Phase 3b section).

**Prerequisites:** Phase 3a is implemented and merged — the API returns `topics[].proposed` / `concepts[].proposed`, and `GET/POST/PATCH /api/research/groupings` exist.

**Conventions discovered in this codebase (follow exactly):**
- API client lives in `frontend/src/api/client.ts` as the `api` object; helpers `get`/`post`/`patch`/`del<T>` already exist. Types live in `frontend/src/api/types.ts`.
- Components are function components using `useQuery`/`useMutation` from `@tanstack/react-query`; mutations call `queryClient.invalidateQueries({ queryKey: [...] })` or a local `invalidate()` in `onSuccess`.
- Tests are colocated `*.test.tsx`, run with `npm test` (Vitest). The pattern (see `frontend/src/pages/ResearchPanel.test.tsx`): build a `QueryClient` with `retry: false, staleTime: Infinity`, seed caches with `qc.setQueryData(queryKey, data)`, wrap with `QueryClientProvider`, render, assert with `screen`. For mutations, `vi.spyOn(api, 'fnName').mockResolvedValue(...)` / `.mockRejectedValue(new Error(...))`.
- Typecheck + build: `npm run build` (`tsc -b && vite build`). Run from `frontend/`.
- The current filter query is `useQuery({ queryKey: ['topics-for-filter'], queryFn: () => api.executeSQL("SELECT id, name FROM topics WHERE status = 'active' ORDER BY name") })` at `ResearchPanel.tsx:658`, with `topicOptions` derived from `topicSqlResult.rows`.
- The pending chips render at `ResearchPanel.tsx:292-312`; confirmed chips at `277-290`; mutations `confirmTopic`/`dismissTopic`/`confirmConcept`/`dismissConcept` at `229-244`.

All commands below run from the `frontend/` directory unless noted.

---

### Task 1: API client + types for groupings

**Files:**
- Modify: `frontend/src/api/types.ts` (add `GroupingItem`; add `proposed` to the two link interfaces)
- Modify: `frontend/src/api/client.ts` (add `listGroupings`, `createGrouping`, `patchGrouping`)
- Test: `frontend/src/api/client.groupings.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/api/client.groupings.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './client'

describe('groupings API client', () => {
  afterEach(() => vi.restoreAllMocks())

  it('listGroupings builds a type+status query', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    await api.listGroupings({ type: 'topic', status: 'active' })
    const url = String(fetchSpy.mock.calls[0][0])
    expect(url).toContain('/api/research/groupings?')
    expect(url).toContain('type=topic')
    expect(url).toContain('status=active')
  })

  it('patchGrouping issues PATCH with parent_id', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: 2, type: 'topic', name: 'np', parent_id: 1, status: 'active', description: null }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    const out = await api.patchGrouping(2, { parent_id: 1 })
    const [, init] = fetchSpy.mock.calls[0]
    expect((init as RequestInit).method).toBe('PATCH')
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ parent_id: 1 })
    expect(out.parent_id).toBe(1)
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- src/api/client.groupings.test.ts`
Expected: FAIL — `api.listGroupings is not a function`.

- [ ] **Step 3: Add the `GroupingItem` type and `proposed` fields**

In `frontend/src/api/types.ts`, replace the two link interfaces and add `GroupingItem`:

```ts
export interface QuestionTopicLink {
  topic_id: number
  topic_name: string
  status: string  // 'pending' | 'confirmed'
  proposed?: boolean
}

export interface QuestionConceptLink {
  concept_id: number
  concept_name: string
  status: string
  proposed?: boolean
}

export interface GroupingItem {
  id: number
  type: string
  name: string
  parent_id: number | null
  status: string
  description: string | null
}
```

- [ ] **Step 4: Add the client functions**

In `frontend/src/api/client.ts`, first add `GroupingItem` to the type import from `./types` (the file imports its response types at the top — add `GroupingItem` to that import list). Then add these three entries to the `api` object (next to the other `/research` calls, e.g. after `removeQuestionConcept`):

```ts
  listGroupings: (params: { type?: string; status?: string } = {}) => {
    const q = new URLSearchParams()
    if (params.type) q.set('type', params.type)
    if (params.status) q.set('status', params.status)
    const query = q.toString()
    return get<GroupingItem[]>(query ? `/api/research/groupings?${query}` : '/api/research/groupings')
  },
  createGrouping: (body: { type: string; name: string; parent_id?: number | null; description?: string | null }) =>
    post<GroupingItem>('/api/research/groupings', body),
  patchGrouping: (id: number, body: { parent_id?: number | null; status?: string }) =>
    patch<GroupingItem>(`/api/research/groupings/${id}`, body),
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `npm test -- src/api/client.groupings.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/api/client.groupings.test.ts
git commit -m "feat(ui/groupings): add GroupingItem type + listGroupings/createGrouping/patchGrouping client"
```

---

### Task 2: Repoint the topic filter to `GET /api/research/groupings`

**Files:**
- Modify: `frontend/src/pages/ResearchPanel.tsx` (the `topics-for-filter` query + `topicOptions`)
- Test: `frontend/src/pages/ResearchPanel.test.tsx` (add a case)

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/pages/ResearchPanel.test.tsx` (inside the existing `describe('ResearchPanel', …)` block). It seeds the new query key and asserts the filter button renders from grouping data:

```ts
  it('renders topic filter buttons from the groupings endpoint', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
    qc.setQueryData(['research-hypotheses'], [])
    qc.setQueryData(['research-metrics'], {
      approved_sources_count: 0, chat_sessions_count: 0,
      literature_searches_count: 0, research_hypotheses_count: 0, caveats: [],
    })
    qc.setQueryData(['research-questions-detail', undefined, []], [])
    qc.setQueryData(['research-claims'], [])
    qc.setQueryData(['research-gaps'], [])
    qc.setQueryData(['groupings-for-filter', 'topic'], [
      { id: 7, type: 'topic', name: 'plasticity', parent_id: null, status: 'active', description: null },
    ])
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: qc }, children)
    render(<ResearchPanel />, { wrapper })
    expect(screen.getByRole('button', { name: 'plasticity' })).toBeTruthy()
  })
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- src/pages/ResearchPanel.test.tsx`
Expected: FAIL — the panel still reads `['topics-for-filter']` via `executeSQL`, so the seeded `['groupings-for-filter','topic']` data is ignored and the `plasticity` button is absent.

- [ ] **Step 3: Repoint the query**

In `frontend/src/pages/ResearchPanel.tsx`, replace the topic-filter query block:

```tsx
  const { data: topicSqlResult } = useQuery({
    queryKey: ['topics-for-filter'],
    queryFn: () => api.executeSQL("SELECT id, name FROM topics WHERE status = 'active' ORDER BY name"),
  })
  const topicOptions: Array<{ id: number; name: string }> =
    topicSqlResult?.rows?.map((r: unknown[]) => ({ id: r[0] as number, name: r[1] as string })) ?? []
```

with:

```tsx
  const { data: topicGroupings = [] } = useQuery({
    queryKey: ['groupings-for-filter', 'topic'],
    queryFn: () => api.listGroupings({ type: 'topic', status: 'active' }),
  })
  const topicOptions: Array<{ id: number; name: string }> =
    topicGroupings.map(g => ({ id: g.id, name: g.name }))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test -- src/pages/ResearchPanel.test.tsx`
Expected: PASS (all prior cases + the new one).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ResearchPanel.tsx frontend/src/pages/ResearchPanel.test.tsx
git commit -m "feat(ui/groupings): repoint topic filter to /api/research/groupings"
```

---

### Task 3: "new" badge on proposed pending chips

**Files:**
- Modify: `frontend/src/pages/ResearchPanel.tsx` (pending-chip renderer, ~lines 296-309)
- Test: `frontend/src/pages/ResearchPanel.test.tsx` (add a case)

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/pages/ResearchPanel.test.tsx`:

```ts
  it('marks a proposed pending topic with a "new" badge', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
    qc.setQueryData(['research-hypotheses'], [])
    qc.setQueryData(['research-metrics'], {
      approved_sources_count: 0, chat_sessions_count: 0,
      literature_searches_count: 0, research_hypotheses_count: 0, caveats: [],
    })
    qc.setQueryData(['research-claims'], [])
    qc.setQueryData(['research-gaps'], [])
    qc.setQueryData(['groupings-for-filter', 'topic'], [])
    qc.setQueryData(['research-questions-detail', undefined, []], [
      {
        id: 1, question: 'Q?', status: 'open', topic_context: '', origin_session_id: null,
        created_at: '2026-06-01',
        topics: [{ topic_id: 9, topic_name: 'plasticity', status: 'pending', proposed: true }],
        concepts: [],
      },
    ])
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: qc }, children)
    render(<ResearchPanel />, { wrapper })
    expect(screen.getByText('plasticity')).toBeTruthy()
    expect(screen.getByText('new')).toBeTruthy()
  })
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- src/pages/ResearchPanel.test.tsx`
Expected: FAIL — no `new` badge is rendered.

- [ ] **Step 3: Render the badge**

In `frontend/src/pages/ResearchPanel.tsx`, in the pending-topic chip (the `{pendingTopics.map(t => ( … ))}` block), add the badge right after `{t.topic_name}`:

```tsx
            {pendingTopics.map(t => (
              <span key={t.topic_id} style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, padding: '1px 4px', border: '1px dashed #93c5fd', borderRadius: 10, color: '#1e40af' }}>
                {t.topic_name}
                {t.proposed && (
                  <span style={{ fontSize: 8, padding: '0 3px', background: '#fde68a', color: '#92400e', borderRadius: 6 }}>new</span>
                )}
                <button type="button" onClick={() => confirmTopic.mutate(t.topic_id)} style={{ fontSize: 9, border: 'none', background: 'transparent', cursor: 'pointer', color: '#16a34a', padding: 0 }}>✓</button>
                <button type="button" onClick={() => dismissTopic.mutate(t.topic_id)} style={{ fontSize: 9, border: 'none', background: 'transparent', cursor: 'pointer', color: '#dc2626', padding: 0 }}>✕</button>
              </span>
            ))}
```

And the same for the pending-concept chip (`{pendingConcepts.map(c => ( … ))}`), after `{c.concept_name}`:

```tsx
                {c.proposed && (
                  <span style={{ fontSize: 8, padding: '0 3px', background: '#fde68a', color: '#92400e', borderRadius: 6 }}>new</span>
                )}
```

(Confirm/dismiss buttons are unchanged — the 3a backend activates a proposed grouping on confirm and removes an orphan proposal on dismiss.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test -- src/pages/ResearchPanel.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ResearchPanel.tsx frontend/src/pages/ResearchPanel.test.tsx
git commit -m "feat(ui/groupings): mark proposed suggestions with a 'new' badge"
```

---

### Task 4: Topic hierarchy / curation view

A focused component that lists topic groupings nested by parent and lets the user set/clear a grouping's parent via `PATCH /api/research/groupings/{id}`, surfacing the 422 invariant error inline.

**Files:**
- Create: `frontend/src/components/GroupingHierarchy.tsx`
- Test: `frontend/src/components/GroupingHierarchy.test.tsx`
- Modify: `frontend/src/pages/ResearchPanel.tsx` (render the component)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/GroupingHierarchy.test.tsx`:

```tsx
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import GroupingHierarchy from './GroupingHierarchy'
import { api } from '../api/client'

function wrapperWith(groupings: unknown[]) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  qc.setQueryData(['groupings-all', 'topic'], groupings)
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

const PARENT = { id: 1, type: 'topic', name: 'plasticity', parent_id: null, status: 'active', description: null }
const CHILD = { id: 2, type: 'topic', name: 'neuroplasticity', parent_id: 1, status: 'active', description: null }
const LOOSE = { id: 3, type: 'topic', name: 'stroke', parent_id: null, status: 'active', description: null }

describe('GroupingHierarchy', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renders top-level groupings with nested children', () => {
    render(<GroupingHierarchy type="topic" />, { wrapper: wrapperWith([PARENT, CHILD, LOOSE]) })
    expect(screen.getByText('plasticity')).toBeTruthy()
    expect(screen.getByText('neuroplasticity')).toBeTruthy()
    expect(screen.getByText('stroke')).toBeTruthy()
  })

  it('re-parents a grouping via patchGrouping', async () => {
    const spy = vi.spyOn(api, 'patchGrouping').mockResolvedValue(
      { ...CHILD, parent_id: 3 } as never,
    )
    render(<GroupingHierarchy type="topic" />, { wrapper: wrapperWith([PARENT, LOOSE,
      { ...CHILD, parent_id: null }]) })
    // the select for the (currently top-level) 'neuroplasticity'
    const select = screen.getByLabelText('parent of neuroplasticity')
    fireEvent.change(select, { target: { value: '3' } })
    await waitFor(() => expect(spy).toHaveBeenCalledWith(2, { parent_id: 3 }))
  })

  it('shows an inline error when re-parent is rejected (422)', async () => {
    vi.spyOn(api, 'patchGrouping').mockRejectedValue(new Error('Parent must be top-level'))
    render(<GroupingHierarchy type="topic" />, { wrapper: wrapperWith([PARENT, LOOSE,
      { ...CHILD, parent_id: null }]) })
    const select = screen.getByLabelText('parent of neuroplasticity')
    fireEvent.change(select, { target: { value: '3' } })
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Parent must be top-level'))
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- src/components/GroupingHierarchy.test.tsx`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Create the component**

Create `frontend/src/components/GroupingHierarchy.tsx`:

```tsx
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import type { GroupingItem } from '../api/types'

interface RowProps {
  g: GroupingItem
  parents: GroupingItem[]
  onReparent: (parentId: number | null) => void
}

function GroupingRow({ g, parents, onReparent }: RowProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
      <span style={{ fontSize: 11, color: '#1e293b' }}>{g.name}</span>
      <select
        aria-label={`parent of ${g.name}`}
        value={g.parent_id ?? ''}
        onChange={(e) => onReparent(e.target.value === '' ? null : Number(e.target.value))}
        style={{ fontSize: 10 }}
      >
        <option value="">No parent</option>
        {parents.map(p => (
          <option key={p.id} value={p.id}>{p.name}</option>
        ))}
      </select>
    </div>
  )
}

export default function GroupingHierarchy({ type = 'topic' }: { type?: string }) {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)

  const { data: groupings = [] } = useQuery({
    queryKey: ['groupings-all', type],
    queryFn: () => api.listGroupings({ type }),
  })

  const reparent = useMutation({
    mutationFn: ({ id, parentId }: { id: number; parentId: number | null }) =>
      api.patchGrouping(id, { parent_id: parentId }),
    onSuccess: () => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['groupings-all', type] })
      queryClient.invalidateQueries({ queryKey: ['groupings-for-filter', type] })
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : 'Re-parent failed'),
  })

  const childrenOf = (id: number) => groupings.filter(g => g.parent_id === id)
  const topLevel = groupings.filter(g => g.parent_id === null)

  // A grouping may be parented only under a top-level grouping that is not itself,
  // and only when it has no children of its own (single-level invariant).
  const eligibleParents = (g: GroupingItem) =>
    childrenOf(g.id).length > 0 ? [] : topLevel.filter(p => p.id !== g.id)

  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#475569', marginBottom: 4 }}>
        Topic hierarchy
      </div>
      {error && (
        <div role="alert" style={{ fontSize: 10, color: '#dc2626', marginBottom: 4 }}>{error}</div>
      )}
      {topLevel.map(parent => (
        <div key={parent.id} style={{ marginBottom: 4 }}>
          <GroupingRow
            g={parent}
            parents={eligibleParents(parent)}
            onReparent={(pid) => reparent.mutate({ id: parent.id, parentId: pid })}
          />
          <div style={{ marginLeft: 14 }}>
            {childrenOf(parent.id).map(child => (
              <GroupingRow
                key={child.id}
                g={child}
                parents={eligibleParents(child)}
                onReparent={(pid) => reparent.mutate({ id: child.id, parentId: pid })}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test -- src/components/GroupingHierarchy.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Render it inside `ResearchPanel`**

In `frontend/src/pages/ResearchPanel.tsx`, add the import near the other imports:

```tsx
import GroupingHierarchy from '../components/GroupingHierarchy'
```

Then render it just below the topic filter buttons block (after the `</div>` that closes the `display: 'flex'` filter-bar div containing the "All topics" + `topicOptions` buttons):

```tsx
        <GroupingHierarchy type="topic" />
```

- [ ] **Step 6: Run the panel tests to verify nothing broke**

Run: `npm test -- src/pages/ResearchPanel.test.tsx`
Expected: PASS. (The component issues a `['groupings-all','topic']` query; unseeded in the existing cases it returns nothing and renders only the "Topic hierarchy" heading — harmless.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/GroupingHierarchy.tsx frontend/src/components/GroupingHierarchy.test.tsx frontend/src/pages/ResearchPanel.tsx
git commit -m "feat(ui/groupings): topic hierarchy curation view with re-parent + 422 surfacing"
```

---

### Task 5: Build/typecheck, manual test plan, status sync

**Files:**
- Create: `docs/testsPlans/manualTestPlan_groupings_phase3b.md`
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Full frontend test + typecheck/build**

Run (from `frontend/`):
```bash
npm test
npm run build
```
Expected: all Vitest suites pass; `tsc -b && vite build` completes with no type errors. If `tsc` flags an unused import (e.g. `SqlResult` if the filter repoint left it dangling), remove it.

- [ ] **Step 2: Write the manual test plan**

Create `docs/testsPlans/manualTestPlan_groupings_phase3b.md`:

```markdown
# Manual Test Plan — Groupings Phase 3b (UI)

## Prerequisites
- [ ] Run the automated suites:
  - Backend: `uv run pytest tests/ -q` — pass criterion: no new failures beyond `docs/testLog.md`.
  - Frontend: `cd frontend && npm test` — all suites pass.
- [ ] Start the backend: `uv run uvicorn neurodb.api.app:app_factory --factory --port 8001`.
- [ ] Start the frontend: `cd frontend && npm run dev` (Vite proxies `/api` to port 8001).

## T1 — Topic filter is populated from the groupings endpoint
- [ ] Open the Research panel.
- [ ] Expected: the topic filter bar shows active topic groupings (network tab shows `GET /api/research/groupings?type=topic&status=active`, not a `/api/sql/execute` call).
- [ ] Click a topic → the question list filters; clicking a parent topic also returns child-tagged questions (rollup).

## T2 — Proposed ("new") suggestion chips
- [ ] Create a question that yields a proposed grouping (a general term not yet in the taxonomy).
- [ ] Expected: a pending chip shows a small "new" badge.
- [ ] Click ✓ → the chip becomes a confirmed badge; the grouping now appears in the topic filter (it was activated).
- [ ] Create another proposed suggestion and click ✕ → the chip disappears and the proposed grouping is not added to the filter.

## T3 — Hierarchy curation
- [ ] In the Topic hierarchy view, confirm seeded parents (e.g. `plasticity`) show their children nested.
- [ ] Use a grouping's parent dropdown to set its parent → the view re-nests after the change.
- [ ] Attempt an invalid re-parent (e.g. assign a parent that already has a parent, or a grouping that has children) → an inline error message appears and the hierarchy is unchanged.
```

- [ ] **Step 3: Update project status**

In `docs/projectStatus.md`:
- Update **Active focus** to: Unified Groupings Phase 3 complete (3a backend + 3b UI) — semantic/proposal matcher, `/groupings` routes, proposal chips, hierarchy curation; LOG-062 closed.
- Update **Next** to: Unified Groupings Phase 4 (migrate papers/datasets/notes/bundles consumers off legacy tables).
- Update the Research and UI epoch rows' "Next" cells accordingly.
- Mark the 3b plan implemented and add the manual test plan to the reference table:
  - `| `docs/superpowers/plans/2026-06-01-groupings-phase3b-ui.md` | Groupings Phase 3b UI plan — filter repoint, proposal "new" chips, hierarchy curation view; implemented <date> |`
  - `| `docs/testsPlans/manualTestPlan_groupings_phase3b.md` | Groupings Phase 3b manual test plan — filter source, proposal chips, hierarchy curation |`

- [ ] **Step 4: Commit**

```bash
git add docs/testsPlans/manualTestPlan_groupings_phase3b.md docs/projectStatus.md
git commit -m "docs: Groupings Phase 3b manual test plan; status sync"
```

---

## Phase 3b Done When

- The Research topic filter reads from `GET /api/research/groupings?type=topic&status=active` (no raw `executeSQL` for topics remains).
- Proposed suggestions are visibly marked "new"; confirming activates the grouping (reusing existing mutations), dismissing removes the orphan.
- The topic hierarchy view lists groupings nested by parent and supports re-parenting, surfacing the 422 invariant error inline.
- `npm test` and `npm run build` are green from `frontend/`.

## Out of Scope for 3b (later phases)

- Migrating papers/datasets/notes/bundles consumers off legacy tables → **Phase 4**.
- Dropping legacy `topics`/`concepts`/join tables → **Phase 5**.
- A create-grouping form in the UI (the `createGrouping` client exists for future use; no UI form is required by this phase).
