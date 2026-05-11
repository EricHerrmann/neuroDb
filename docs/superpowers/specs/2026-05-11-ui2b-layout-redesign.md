# UI-2B Layout Redesign Design

**Date:** 2026-05-11
**Status:** Approved
**Author:** Eric Herrmann

---

## Goal

Replace the horizontal `PanelNav` tab bar and the `Sidebar` with a vertical `ActivityRail`, add a drag-resizable split between the chat and right panel (collapsible to zero for full-width chat), and move agent mode selection into the chat panel header. No new API routes — this is a pure layout change on top of the UI-2 React workbench.

---

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Resizable panels | `react-resizable-panels` | `Group`/`Panel`/`Separator` API with built-in `collapsible`, `minSize`, `maxSize`, and imperative ref (`expand`, `collapse`, `isCollapsed`) |
| Icons | `lucide-react` | Tree-shakeable SVG icons, one import per icon, zero runtime overhead for unused icons |
| Routing | React Router v7 `NavLink` (existing) | `className` callback with `isActive` — same pattern as UI-2 `PanelNav`, now in rail |

---

## Architecture

### Layout Structure

```
App
├── ActivityRail (40px fixed, left edge)
│   └── 7 × NavLink icon buttons (one per panel route)
└── Group orientation="horizontal"          ← react-resizable-panels
    ├── Panel (chat, default 55%, min 30%)
    │   └── ChatPanel
    │       ├── Header (agent mode <select>)
    │       ├── MessageList
    │       └── ChatInput
    ├── Separator (drag handle)
    └── Panel (right, default 45%, min 0%, collapsible)
        └── <Outlet /> (React Router — active panel page)
```

### File Changes

| Change | File |
|--------|------|
| **New** | `frontend/src/components/ActivityRail.tsx` |
| **Modify** | `frontend/src/App.tsx` |
| **Modify** | `frontend/src/components/ChatPanel.tsx` |
| **Delete** | `frontend/src/components/Sidebar.tsx` |
| **Delete** | `frontend/src/components/PanelNav.tsx` |
| **New test** | `frontend/src/components/ActivityRail.test.tsx` |
| **New test** | `frontend/src/components/ChatPanel.test.tsx` (component exists; test file is new) |

---

## Components

### `ActivityRail`

Props:
```ts
interface ActivityRailProps {
  panelRef: React.RefObject<PanelImperativeApi>
}
```

- Fixed 40px wide column on the left edge, full viewport height
- 7 `NavLink` items, one per panel route, each with a Lucide icon and HTML `title` attribute for tooltip
- `NavLink` `className` callback: active route gets blue background (`#3b82f6`), inactive gets muted (`#334155`)
- Each `NavLink` `onClick`: if `panelRef.current?.isCollapsed()`, call `panelRef.current.expand()` before navigation
- No external tooltip library — HTML `title` is sufficient

Panel routes and icons:

| Route | Label | Icon (`lucide-react`) |
|-------|-------|-----------------------|
| `/suggestions` | Suggestions | `Lightbulb` |
| `/study-log` | Study Log | `ClipboardList` |
| `/datasets` | Datasets | `Database` |
| `/registry` | Registry | `Package` |
| `/knowledge-library` | Knowledge Library | `BookOpen` |
| `/research` | Research | `FlaskConical` |
| `/sql` | SQL | `Zap` |

### `App.tsx`

- Remove `<Sidebar>` and `<PanelNav>`
- Add `<ActivityRail panelRef={rightPanelRef} />`
- Create `rightPanelRef = useRef<PanelImperativeApi>(null)`
- Wrap chat + right panel in `<Group orientation="horizontal">` with `<Separator>` between
- Chat `<Panel>`: `defaultSize={55}` `minSize={30}`
- Right `<Panel>`: `ref={rightPanelRef}` `defaultSize={45}` `minSize={0}` `collapsible`
- `<Separator>` styled: `width: 5px`, `cursor: col-resize`, turns `#3b82f6` when panel is collapsed (via `onCollapse`/`onExpand` callbacks updating local state)

### `ChatPanel.tsx`

- Add header bar above the message list:
  - Left: `CHAT` label
  - Right: agent mode `<select>` with the four modes
- Move `setMode` mutation here from `Sidebar` (was: `useMutation` calling `api.setAgentMode`)
- `agentMode` prop remains — passed from `App` via `useQuery(['preferences'])`

### `Sidebar.tsx` — deleted

All functionality migrated: agent mode → `ChatPanel` header; session history → already covered by `StudyLogPanel`.

### `PanelNav.tsx` — deleted

Replaced by `ActivityRail`.

---

## Data Flow

### Panel collapse/expand

```
User drags Separator to right edge
  → Panel collapses (size → 0)
  → onCollapse callback fires → App sets isRightCollapsed=true
  → Separator style changes to blue

User clicks ActivityRail icon while isRightCollapsed=true
  → onClick: panelRef.current.expand()
  → NavLink navigation fires → route changes → panel shows new content
  → onExpand callback fires → App sets isRightCollapsed=false
  → Separator returns to default style
```

### Agent mode

`useQuery(['preferences'])` in `App` → `agentMode` prop → `ChatPanel` renders `<select>`.
`useMutation` in `ChatPanel` calls `api.setAgentMode(mode)` on `onChange`, invalidates `['preferences']`.

---

## Separator Styling

The `Separator` component needs visual feedback for the collapsed state. `App` tracks `isRightCollapsed: boolean` via `useState`, toggled by the Panel's `onCollapse` and `onExpand` callbacks. The `Separator` receives an `isCollapsed` prop and renders blue when true.

```tsx
// App.tsx excerpt
const [isRightCollapsed, setIsRightCollapsed] = useState(false)

<Separator style={{
  width: 5,
  cursor: 'col-resize',
  background: isRightCollapsed ? '#3b82f6' : '#334155',
}} />

<Panel
  ref={rightPanelRef}
  defaultSize={45}
  minSize={0}
  collapsible
  onCollapse={() => setIsRightCollapsed(true)}
  onExpand={() => setIsRightCollapsed(false)}
>
```

---

## Testing

### `ActivityRail.test.tsx` (3 tests)

```ts
// T1: renders all 7 nav items
render(<ActivityRail panelRef={mockRef} />)
expect(screen.getAllByRole('link')).toHaveLength(7)

// T2: active link gets blue background
// render with MemoryRouter at /suggestions
// assert the suggestions NavLink has active class/style

// T3: clicking icon while collapsed calls expand()
const mockPanel = { isCollapsed: () => true, expand: vi.fn() }
const ref = { current: mockPanel }
fireEvent.click(screen.getByTitle('Suggestions'))
expect(mockPanel.expand).toHaveBeenCalledOnce()
```

### `ChatPanel.test.tsx` (2 tests)

```ts
// T1: agent mode select renders with current mode
render(<ChatPanel agentMode="neuro_tutor" />)
expect(screen.getByRole('combobox')).toHaveValue('neuro_tutor')

// T2: changing select fires setAgentMode
fireEvent.change(screen.getByRole('combobox'), { target: { value: 'local_db' } })
// assert fetch called with POST /api/preferences { agent_mode: 'local_db' }
```

### Manual test prerequisites

`uv run pytest tests/ -q` — no new Python test failures (no backend changes).
`npm run test` in `frontend/` — all 7 existing + 5 new frontend tests pass.

---

## Error Handling

- If `panelRef.current` is null on icon click (panel not yet mounted), `expand()` is skipped — navigation still fires normally.
- Agent mode mutation failure: no special handling beyond what `useMutation` provides by default (error state available if needed in a later phase).

---

## Out of Scope (UI-2B)

- Monaco editor for SQL panel
- Tooltips beyond HTML `title`
- Streamlit retirement
- Any new API routes
- E2E / Cypress tests
- Provider selection UI
