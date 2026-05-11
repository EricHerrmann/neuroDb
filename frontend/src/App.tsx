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
