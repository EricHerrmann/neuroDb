# UI-2B Layout Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `Sidebar` + `PanelNav` with a vertical `ActivityRail`, make the chat/panel split resizable and collapsible, and move agent mode selection into the `ChatPanel` header.

**Architecture:** `ActivityRail` (40px fixed column) uses React Router `NavLink` with Lucide icons and an imperative panel ref to expand the right panel on click. `react-resizable-panels` (`Group`/`Panel`/`Separator`) handles the drag-resize between chat and right panel. `ChatPanel` gains an agent-mode `<select>` header and owns the `setAgentMode` mutation (moved from deleted `Sidebar`). `Sidebar` and `PanelNav` are deleted.

**Tech Stack:** `react-resizable-panels` (Group, Panel, Separator, usePanelRef), `lucide-react` (tree-shakeable SVG icons), React Router v7 NavLink, TanStack Query v5 useMutation, Vitest + React Testing Library.

---

## File Map

| Change | File | Responsibility |
|--------|------|---------------|
| New | `frontend/src/components/ActivityRail.tsx` | 40px icon rail, 7 NavLink items, expand panel on click |
| New test | `frontend/src/components/ActivityRail.test.tsx` | 3 tests: link count, active state, expand-on-click |
| Modify | `frontend/src/components/ChatPanel.tsx` | Add agent mode header + setMode mutation |
| New test | `frontend/src/components/ChatPanel.test.tsx` | 2 tests: select renders, mutation fires |
| Modify | `frontend/src/App.tsx` | Wire ActivityRail + Group/Panel/Separator, remove Sidebar/PanelNav |
| Delete | `frontend/src/components/Sidebar.tsx` | Replaced by ActivityRail + ChatPanel header |
| Delete | `frontend/src/components/PanelNav.tsx` | Replaced by ActivityRail |
| Modify | `frontend/package.json` | Add react-resizable-panels, lucide-react |

---

## Task 1: Install dependencies

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install packages**

```bash
cd frontend && npm install react-resizable-panels lucide-react
```

Expected: packages added to `node_modules/`, `package.json` dependencies updated, no errors.

- [ ] **Step 2: Verify imports resolve**

```bash
cd frontend && node -e "
import('react-resizable-panels').then(m => {
  const keys = Object.keys(m)
  if (!keys.includes('Group')) throw new Error('Group missing: ' + keys)
  if (!keys.includes('Panel')) throw new Error('Panel missing')
  if (!keys.includes('Separator')) throw new Error('Separator missing')
  if (!keys.includes('usePanelRef')) throw new Error('usePanelRef missing')
  console.log('react-resizable-panels ok:', keys.filter(k => ['Group','Panel','Separator','usePanelRef'].includes(k)))
})
import('lucide-react').then(m => {
  if (!m.Lightbulb) throw new Error('Lightbulb missing')
  console.log('lucide-react ok')
})
"
```

Expected output contains `react-resizable-panels ok:` and `lucide-react ok`.

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add react-resizable-panels and lucide-react"
```

---

## Task 2: ActivityRail component

**Files:**
- Create: `frontend/src/components/ActivityRail.tsx`
- Create: `frontend/src/components/ActivityRail.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/ActivityRail.test.tsx`:

```tsx
import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'

import ActivityRail from './ActivityRail'

function makePanelRef(collapsed: boolean) {
  return {
    current: {
      isCollapsed: () => collapsed,
      expand: vi.fn(),
    },
  }
}

describe('ActivityRail', () => {
  it('renders 7 navigation links', () => {
    render(
      <MemoryRouter>
        <ActivityRail panelRef={makePanelRef(false)} />
      </MemoryRouter>,
    )
    expect(screen.getAllByRole('link')).toHaveLength(7)
  })

  it('suggestions link has aria-current=page at /suggestions route', () => {
    render(
      <MemoryRouter initialEntries={['/suggestions']}>
        <ActivityRail panelRef={makePanelRef(false)} />
      </MemoryRouter>,
    )
    expect(screen.getByTitle('Suggestions')).toHaveAttribute('aria-current', 'page')
  })

  it('clicking an icon while panel is collapsed calls expand', () => {
    const ref = makePanelRef(true)
    render(
      <MemoryRouter>
        <ActivityRail panelRef={ref} />
      </MemoryRouter>,
    )
    fireEvent.click(screen.getByTitle('Suggestions'))
    expect(ref.current.expand).toHaveBeenCalledOnce()
  })
})
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd frontend && npm run test -- --reporter=verbose ActivityRail
```

Expected: 3 failures — `ActivityRail` module not found.

- [ ] **Step 3: Implement ActivityRail**

Create `frontend/src/components/ActivityRail.tsx`:

```tsx
import {
  BookOpen,
  ClipboardList,
  Database,
  FlaskConical,
  Lightbulb,
  Package,
  Zap,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'

interface PanelHandle {
  isCollapsed: () => boolean
  expand: () => void
}

interface ActivityRailProps {
  panelRef: { current: PanelHandle | null }
}

const PANELS = [
  { path: '/suggestions', label: 'Suggestions', Icon: Lightbulb },
  { path: '/study-log', label: 'Study Log', Icon: ClipboardList },
  { path: '/datasets', label: 'Datasets', Icon: Database },
  { path: '/registry', label: 'Registry', Icon: Package },
  { path: '/knowledge-library', label: 'Knowledge Library', Icon: BookOpen },
  { path: '/research', label: 'Research', Icon: FlaskConical },
  { path: '/sql', label: 'SQL', Icon: Zap },
]

export default function ActivityRail({ panelRef }: ActivityRailProps) {
  return (
    <div style={{
      width: 40,
      flexShrink: 0,
      background: '#1e293b',
      borderRight: '1px solid #334155',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      paddingTop: 10,
      gap: 6,
    }}>
      {PANELS.map(({ path, label, Icon }) => (
        <NavLink
          key={path}
          to={path}
          title={label}
          onClick={() => {
            if (panelRef.current?.isCollapsed()) {
              panelRef.current.expand()
            }
          }}
          style={({ isActive }) => ({
            width: 26,
            height: 26,
            borderRadius: 5,
            background: isActive ? '#3b82f6' : '#334155',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: isActive ? 'white' : '#64748b',
            textDecoration: 'none',
          })}
        >
          <Icon size={14} />
        </NavLink>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd frontend && npm run test -- --reporter=verbose ActivityRail
```

Expected: 3 passing.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ActivityRail.tsx frontend/src/components/ActivityRail.test.tsx
git commit -m "feat: add ActivityRail component with icon nav and expand-on-click"
```

---

## Task 3: Update ChatPanel — agent mode header

**Files:**
- Modify: `frontend/src/components/ChatPanel.tsx`
- Create: `frontend/src/components/ChatPanel.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/ChatPanel.test.tsx`:

```tsx
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import ChatPanel from './ChatPanel'

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('ChatPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response('{}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
  })

  it('renders agent mode select with current mode selected', () => {
    render(<ChatPanel agentMode="neuro_tutor" />, { wrapper: makeWrapper() })
    const select = screen.getByRole('combobox')
    expect((select as HTMLSelectElement).value).toBe('neuro_tutor')
  })

  it('changing agent mode fires PUT /api/preferences/agent-mode', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ agent_mode: 'local_db' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<ChatPanel agentMode="neuro_tutor" />, { wrapper: makeWrapper() })
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'local_db' } })

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/preferences/agent-mode',
        expect.objectContaining({ method: 'PUT' }),
      )
    })
  })
})
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd frontend && npm run test -- --reporter=verbose ChatPanel
```

Expected: 2 failures — `select` element not found (no `<select>` in current ChatPanel).

- [ ] **Step 3: Update ChatPanel**

Replace `frontend/src/components/ChatPanel.tsx` entirely:

```tsx
import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import { useChat } from '../hooks/useChat'
import MessageBubble from './MessageBubble'

const MODES = [
  { value: 'local_db', label: 'Local DB' },
  { value: 'external_db', label: 'External DB' },
  { value: 'neuro_tutor', label: 'Neuro Tutor' },
  { value: 'neuro_research', label: 'Neuro Research' },
]

export default function ChatPanel({ agentMode }: { agentMode: string }) {
  const queryClient = useQueryClient()
  const { messages, isStreaming, sendMessage } = useChat(agentMode)
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const setMode = useMutation({
    mutationFn: (mode: string) => api.setAgentMode(mode),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['preferences'] }),
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!input.trim()) return
    sendMessage(input)
    setInput('')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{
        padding: '8px 12px',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
      }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: '#475569', letterSpacing: '0.05em' }}>
          CHAT
        </span>
        <select
          value={agentMode}
          onChange={event => setMode.mutate(event.target.value)}
          style={{
            padding: '3px 6px',
            fontSize: 11,
            border: '1px solid #cbd5e1',
            borderRadius: 4,
          }}
        >
          {MODES.map(mode => (
            <option key={mode.value} value={mode.value}>{mode.label}</option>
          ))}
        </select>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
        {messages.length === 0 && (
          <p style={{ color: '#94a3b8', fontSize: 13, textAlign: 'center', marginTop: 32 }}>
            Start a conversation...
          </p>
        )}
        {messages.map((message, index) => <MessageBubble key={index} message={message} />)}
        <div ref={bottomRef} />
      </div>
      <form
        onSubmit={handleSubmit}
        style={{
          display: 'flex',
          gap: 8,
          padding: 12,
          borderTop: '1px solid #e2e8f0',
          flexShrink: 0,
        }}
      >
        <input
          value={input}
          onChange={event => setInput(event.target.value)}
          placeholder="Type a message..."
          disabled={isStreaming}
          style={{
            flex: 1,
            padding: '8px 10px',
            border: '1px solid #cbd5e1',
            borderRadius: 6,
            fontSize: 13,
          }}
        />
        <button
          type="submit"
          disabled={isStreaming || !input.trim()}
          style={{
            padding: '8px 14px',
            background: '#1e3a8a',
            color: '#fff',
            border: 'none',
            borderRadius: 6,
            cursor: 'pointer',
            fontSize: 13,
          }}
        >
          Send
        </button>
      </form>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd frontend && npm run test -- --reporter=verbose ChatPanel
```

Expected: 2 passing.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChatPanel.tsx frontend/src/components/ChatPanel.test.tsx
git commit -m "feat: add agent mode header to ChatPanel, move setMode mutation from Sidebar"
```

---

## Task 4: Update App.tsx — wire ActivityRail and resizable panels

**Files:**
- Modify: `frontend/src/App.tsx`

No new test file for this task — the existing `SuggestionsPanel`, `KnowledgeLibraryPanel`, `useChat`, `ActivityRail`, and `ChatPanel` tests cover the pieces. Run the full suite after to catch regressions.

- [ ] **Step 1: Replace App.tsx**

Replace `frontend/src/App.tsx` entirely:

```tsx
import { useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Group, Panel, Separator, usePanelRef } from 'react-resizable-panels'

import { api } from './api/client'
import ActivityRail from './components/ActivityRail'
import ChatPanel from './components/ChatPanel'
import DatasetsPanel from './pages/DatasetsPanel'
import KnowledgeLibraryPanel from './pages/KnowledgeLibraryPanel'
import RegistryPanel from './pages/RegistryPanel'
import ResearchPanel from './pages/ResearchPanel'
import SqlPanel from './pages/SqlPanel'
import StudyLogPanel from './pages/StudyLogPanel'
import SuggestionsPanel from './pages/SuggestionsPanel'

export default function App() {
  const { data: prefs } = useQuery({
    queryKey: ['preferences'],
    queryFn: api.getPreferences,
  })
  const agentMode = prefs?.agent_mode ?? 'local_db'
  const rightPanelRef = usePanelRef()
  const [isRightCollapsed, setIsRightCollapsed] = useState(false)

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <ActivityRail panelRef={rightPanelRef} />
      <Group orientation="horizontal" style={{ flex: 1, overflow: 'hidden' }}>
        <Panel defaultSize={55} minSize={30}>
          <ChatPanel agentMode={agentMode} />
        </Panel>
        <Separator
          style={{
            width: 5,
            cursor: 'col-resize',
            background: isRightCollapsed ? '#3b82f6' : '#334155',
            flexShrink: 0,
          }}
        />
        <Panel
          panelRef={rightPanelRef}
          defaultSize={45}
          minSize={0}
          collapsible
          onResize={(size) => {
            setIsRightCollapsed(size.asPercentage === 0)
          }}
        >
          <div style={{ height: '100%', overflowY: 'auto' }}>
            <Routes>
              <Route path="/suggestions" element={<SuggestionsPanel />} />
              <Route path="/study-log" element={<StudyLogPanel />} />
              <Route path="/datasets" element={<DatasetsPanel />} />
              <Route path="/registry" element={<RegistryPanel />} />
              <Route path="/knowledge-library" element={<KnowledgeLibraryPanel />} />
              <Route path="/research" element={<ResearchPanel />} />
              <Route path="/sql" element={<SqlPanel />} />
              <Route path="*" element={<Navigate to="/suggestions" replace />} />
            </Routes>
          </div>
        </Panel>
      </Group>
    </div>
  )
}
```

- [ ] **Step 2: Run the full frontend test suite**

```bash
cd frontend && npm run test
```

Expected: all tests pass (7 existing + 5 new = 12 total). No TypeScript errors.

If TypeScript errors on `size.asPercentage`, check the `onResize` callback signature from the package. Alternative using `inPixels`:

```tsx
onResize={(size) => {
  setIsRightCollapsed(size.inPixels === 0)
}}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: wire ActivityRail and react-resizable-panels in App, remove Sidebar/PanelNav usage"
```

---

## Task 5: Delete Sidebar and PanelNav, final suite check

**Files:**
- Delete: `frontend/src/components/Sidebar.tsx`
- Delete: `frontend/src/components/PanelNav.tsx`

- [ ] **Step 1: Delete the files**

```bash
rm frontend/src/components/Sidebar.tsx frontend/src/components/PanelNav.tsx
```

- [ ] **Step 2: Confirm no remaining imports**

```bash
grep -r "Sidebar\|PanelNav" frontend/src --include="*.tsx" --include="*.ts"
```

Expected: no output (zero references remaining).

- [ ] **Step 3: Run full frontend test suite**

```bash
cd frontend && npm run test
```

Expected: all 12 tests pass, no TypeScript errors.

- [ ] **Step 4: Run Python test suite to confirm no regressions**

```bash
uv run pytest tests/ -q
```

Expected: same count as before this phase (currently 398+), no new failures.

- [ ] **Step 5: Commit**

```bash
git add -A frontend/src/components/Sidebar.tsx frontend/src/components/PanelNav.tsx
git commit -m "chore: delete Sidebar and PanelNav — replaced by ActivityRail and ChatPanel header"
```

---

## Task 6: Manual verification and docs update

**Files:**
- Modify: `docs/projectStatus.md`
- Modify: `docs/UI_EpochPlan.md`

- [ ] **Step 1: Start both servers**

Terminal 1:
```bash
uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
```

Terminal 2:
```bash
cd frontend && npm run dev
```

Open http://localhost:5173 in a browser.

- [ ] **Step 2: Verify the layout**

Check each item manually:

1. The left sidebar is gone — replaced by a 40px icon rail
2. Clicking each rail icon switches the right panel
3. The active icon is highlighted blue
4. The agent mode `<select>` appears in the chat panel header
5. Dragging the separator resizes chat vs right panel
6. Dragging the separator fully right collapses the right panel; separator turns blue
7. Clicking any rail icon while right panel is collapsed re-expands it
8. Chat streaming still works (send a message)

- [ ] **Step 3: Update docs**

In `docs/UI_EpochPlan.md`, update the UI-2B phase row status to `Complete` and add test count and sign-off date.

In `docs/projectStatus.md`, update:
- UI epoch row: mark UI-2B complete
- Active focus: next task

- [ ] **Step 4: Commit docs**

```bash
git add docs/projectStatus.md docs/UI_EpochPlan.md
git commit -m "docs: mark UI-2B complete"
```
