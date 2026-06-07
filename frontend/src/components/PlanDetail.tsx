import type { PlanDetail as PlanDetailData, PlanStep } from '../api/types'

const PROGRESS_OPTIONS = ['todo', 'in_progress', 'done', 'skipped']

interface PlanDetailProps {
  plan: PlanDetailData
  onStepProgress: (stepId: number, progress: string) => void
  onStepLifecycle: (stepId: number, action: 'confirm' | 'dismiss') => void
  onConfirmChanges: () => void
  onDismissChanges: () => void
}

function StepRow({
  step,
  onStepProgress,
  onStepLifecycle,
}: {
  step: PlanStep
  onStepProgress: (stepId: number, progress: string) => void
  onStepLifecycle: (stepId: number, action: 'confirm' | 'dismiss') => void
}) {
  const sourceLabel = step.source_title ?? (
    step.paper_id != null ? `source #${step.paper_id}` : 'pending source'
  )
  const label =
    step.step_type === 'read'
      ? `Read: ${sourceLabel}`
      : step.action_text ?? '(action)'

  const removal = step.lifecycle === 'proposed_removal'
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 8,
        padding: '4px 0',
        borderBottom: '1px solid #f1f5f9',
      }}
    >
      <span
        style={{
          fontSize: 12,
          color: removal ? '#94a3b8' : '#1e293b',
          textDecoration: removal ? 'line-through' : 'none',
        }}
      >
        {label}
      </span>

      {step.lifecycle === 'confirmed' && (
        <select
          value={step.progress}
          onChange={e => onStepProgress(step.id, e.target.value)}
          style={{ fontSize: 11, padding: '1px 4px' }}
        >
          {PROGRESS_OPTIONS.map(p => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      )}

      {step.lifecycle === 'proposed' && (
        <span style={{ display: 'flex', gap: 4 }}>
          <button style={{ fontSize: 10 }} onClick={() => onStepLifecycle(step.id, 'confirm')}>
            Confirm
          </button>
          <button style={{ fontSize: 10 }} onClick={() => onStepLifecycle(step.id, 'dismiss')}>
            Dismiss
          </button>
        </span>
      )}

      {removal && (
        <span style={{ display: 'flex', gap: 4 }}>
          <button style={{ fontSize: 10 }} onClick={() => onStepLifecycle(step.id, 'dismiss')}>
            Keep
          </button>
          <button style={{ fontSize: 10 }} onClick={() => onStepLifecycle(step.id, 'confirm')}>
            Remove
          </button>
        </span>
      )}
    </div>
  )
}

export default function PlanDetail({
  plan,
  onStepProgress,
  onStepLifecycle,
  onConfirmChanges,
  onDismissChanges,
}: PlanDetailProps) {
  return (
    <div style={{ marginTop: 8, padding: 8, border: '1px solid #e2e8f0', borderRadius: 6 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: '#1e293b', marginBottom: 2 }}>{plan.title}</div>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6 }}>{plan.origin_prompt}</div>

      {plan.groupings.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
          {plan.groupings.map(g => (
            <span
              key={`${g.type}-${g.id}`}
              style={{
                fontSize: 10,
                background: '#f1f5f9',
                borderRadius: 10,
                padding: '1px 6px',
                color: '#475569',
              }}
            >
              {g.name}
            </span>
          ))}
        </div>
      )}

      {plan.steps.map(step => (
        <StepRow
          key={step.id}
          step={step}
          onStepProgress={onStepProgress}
          onStepLifecycle={onStepLifecycle}
        />
      ))}

      {plan.pending_change_count > 0 && (
        <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
          <button style={{ fontSize: 11 }} onClick={onConfirmChanges}>
            Confirm changes
          </button>
          <button style={{ fontSize: 11 }} onClick={onDismissChanges}>
            Dismiss changes
          </button>
        </div>
      )}
    </div>
  )
}
