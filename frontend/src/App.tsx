import { useQuery } from '@tanstack/react-query'
import { Navigate, Route, Routes } from 'react-router-dom'

import { api } from './api/client'
import ChatPanel from './components/ChatPanel'
import PanelNav from './components/PanelNav'
import Sidebar from './components/Sidebar'
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

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar agentMode={agentMode} />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div style={{
          flex: '0 0 55%',
          overflow: 'hidden',
          borderRight: '1px solid #e2e8f0',
        }}>
          <ChatPanel agentMode={agentMode} />
        </div>
        <div style={{
          flex: '0 0 45%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}>
          <PanelNav />
          <div style={{ flex: 1, overflowY: 'auto' }}>
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
        </div>
      </div>
    </div>
  )
}
