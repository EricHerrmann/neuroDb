import type { ModelInfo } from '../api/types'

export default function ProviderChip({ modelInfo }: { modelInfo?: ModelInfo }) {
  const route = modelInfo?.tiers?.mid
  if (!route?.provider || !route?.model) return null

  return (
    <span
      aria-label="Active provider"
      title={`${route.tier}: ${route.provider} / ${route.model}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        maxWidth: 220,
        minHeight: 22,
        padding: '2px 7px',
        border: '1px solid #cbd5e1',
        borderRadius: 4,
        background: '#f8fafc',
        color: '#334155',
        fontSize: 11,
        fontWeight: 600,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}
    >
      {route.provider} · {route.model}
    </span>
  )
}
