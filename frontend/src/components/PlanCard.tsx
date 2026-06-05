import type { PlanSummary } from '../api/types'

const STATUS_COLORS: Record<string, string> = {
  proposed: '#b45309',
  active: '#0369a1',
  paused: '#6b7280',
  done: '#15803d',
}

interface PlanCardProps {
  plan: PlanSummary
  selected: boolean
  onSelect: () => void
  onConfirm: () => void
  onDismiss: () => void
}

export default function PlanCard({ plan, selected, onSelect, onConfirm, onDismiss }: PlanCardProps) {
  const color = STATUS_COLORS[plan.status] ?? '#6b7280'
  return (
    <div
      onClick={onSelect}
      style={{
        border: selected ? '1px solid #0369a1' : '1px solid #e2e8f0',
        borderRadius: 6,
        padding: 8,
        marginBottom: 6,
        cursor: 'pointer',
        background: selected ? '#f0f9ff' : '#fff',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#1e293b' }}>{plan.title}</span>
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            textTransform: 'uppercase',
            color,
            border: `1px solid ${color}`,
            borderRadius: 4,
            padding: '1px 5px',
          }}
        >
          {plan.status}
        </span>
      </div>

      {plan.status !== 'proposed' && (
        <div style={{ marginTop: 6 }}>
          <div style={{ height: 4, background: '#e2e8f0', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{ width: `${plan.percent_complete}%`, height: '100%', background: '#0369a1' }} />
          </div>
          <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>
            {plan.percent_complete}% · {plan.step_count} steps
          </div>
        </div>
      )}

      {plan.pending_change_count > 0 && (
        <div style={{ fontSize: 10, color: '#b45309', marginTop: 4 }}>
          {plan.pending_change_count} pending change{plan.pending_change_count === 1 ? '' : 's'}
        </div>
      )}

      {plan.status === 'proposed' && (
        <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
          <button
            onClick={e => {
              e.stopPropagation()
              onConfirm()
            }}
            style={{ fontSize: 11, padding: '2px 8px', cursor: 'pointer' }}
          >
            Confirm
          </button>
          <button
            onClick={e => {
              e.stopPropagation()
              onDismiss()
            }}
            style={{ fontSize: 11, padding: '2px 8px', cursor: 'pointer' }}
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  )
}
