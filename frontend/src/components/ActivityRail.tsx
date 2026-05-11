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
    <nav
      aria-label="Panel navigation"
      style={{
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
          <Icon size={14} aria-hidden={true} />
        </NavLink>
      ))}
    </nav>
  )
}
