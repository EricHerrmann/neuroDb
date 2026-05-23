import { useEffect, useRef, useState } from 'react'

import Tooltip from './Tooltip'

interface Transition {
  label: string
  onSelect: () => void
  description?: string
}

interface StatusChipProps {
  status: string
  transitions: Transition[]
  isPending?: boolean
  statusDescription?: string
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

export default function StatusChip({ status, transitions, isPending, statusDescription }: StatusChipProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const { background, color, border } = chipColors(status)

  useEffect(() => {
    if (!open) return
    const handleMouseDown = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [open])

  if (transitions.length === 0) {
    const chip = (
      <span style={{
        background, color,
        border: `1px solid ${border}`,
        fontSize: 9, padding: '2px 7px', borderRadius: 10,
      }} tabIndex={0} aria-label={statusDescription ? `${status}: ${statusDescription}` : status}>
        {status}
      </span>
    )
    return statusDescription ? <Tooltip text={statusDescription} align="left">{chip}</Tooltip> : chip
  }

  const chipButton = (
    <button
      type="button"
      disabled={isPending}
      onClick={() => setOpen(v => !v)}
      aria-label={statusDescription ? `${status}: ${statusDescription}` : `${status} status actions`}
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
  )

  return (
    <div ref={containerRef} style={{ position: 'relative', display: 'inline-block' }}>
      {statusDescription ? <Tooltip text={statusDescription} align="left">{chipButton}</Tooltip> : chipButton}
      {open && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, zIndex: 10,
          background: '#0f172a', border: '1px solid #334155', borderRadius: 4,
          padding: 4, display: 'flex', flexDirection: 'column', gap: 2, minWidth: 190,
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
              <span style={{ display: 'block', fontWeight: 700, color: '#e2e8f0' }}>{t.label}</span>
              {t.description && (
                <span style={{ display: 'block', marginTop: 2, color: '#94a3b8', lineHeight: 1.25 }}>
                  {t.description}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
