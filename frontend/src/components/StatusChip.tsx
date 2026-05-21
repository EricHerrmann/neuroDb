import { useState } from 'react'

interface Transition {
  label: string
  onSelect: () => void
}

interface StatusChipProps {
  status: string
  transitions: Transition[]
  isPending?: boolean
}

function chipColors(status: string): { background: string; color: string; border: string } {
  if (status === 'approved' || status === 'resolved' || status === 'active') {
    return { background: '#14532d', color: '#86efac', border: '#166534' }
  }
  if (status === 'rejected' || status === 'retracted' || status === 'archived') {
    return { background: '#7f1d1d', color: '#fca5a5', border: '#991b1b' }
  }
  return { background: '#1e293b', color: '#94a3b8', border: '#334155' }
}

export default function StatusChip({ status, transitions, isPending }: StatusChipProps) {
  const [open, setOpen] = useState(false)
  const { background, color, border } = chipColors(status)

  if (transitions.length === 0) {
    return (
      <span style={{
        background, color,
        border: `1px solid ${border}`,
        fontSize: 9, padding: '2px 7px', borderRadius: 10,
      }}>
        {status}
      </span>
    )
  }

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        disabled={isPending}
        onClick={() => setOpen(v => !v)}
        style={{
          background, color,
          border: `1px solid ${border}`,
          fontSize: 9, padding: '2px 7px', borderRadius: 10,
          cursor: isPending ? 'not-allowed' : 'pointer',
          opacity: isPending ? 0.6 : 1,
        }}
      >
        {status} ▾
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: '100%', right: 0, zIndex: 10,
          background: '#0f172a', border: '1px solid #334155', borderRadius: 4,
          padding: 4, display: 'flex', flexDirection: 'column', gap: 2, minWidth: 80,
        }}>
          {transitions.map(t => (
            <button
              key={t.label}
              type="button"
              onClick={() => { t.onSelect(); setOpen(false) }}
              style={{
                background: 'none', border: 'none', textAlign: 'left',
                padding: '3px 8px', fontSize: 10, color: '#94a3b8', cursor: 'pointer',
                borderRadius: 3,
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
