import { NavLink } from 'react-router-dom'

const PANELS = [
  { path: '/suggestions', label: 'Suggestions' },
  { path: '/study-log', label: 'Study Log' },
  { path: '/datasets', label: 'Datasets' },
  { path: '/registry', label: 'Registry' },
  { path: '/knowledge-library', label: 'Knowledge Library' },
  { path: '/research', label: 'Research' },
  { path: '/sql', label: 'SQL' },
]

export default function PanelNav() {
  return (
    <nav style={{
      display: 'flex',
      borderBottom: '1px solid #e2e8f0',
      overflowX: 'auto',
      flexShrink: 0,
      background: '#f8fafc',
    }}>
      {PANELS.map(panel => (
        <NavLink
          key={panel.path}
          to={panel.path}
          style={({ isActive }) => ({
            padding: '8px 12px',
            textDecoration: 'none',
            fontSize: 12,
            fontWeight: isActive ? 700 : 400,
            color: isActive ? '#1e3a8a' : '#475569',
            borderBottom: isActive ? '2px solid #1e3a8a' : '2px solid transparent',
            whiteSpace: 'nowrap',
            flexShrink: 0,
          })}
        >
          {panel.label}
        </NavLink>
      ))}
    </nav>
  )
}
