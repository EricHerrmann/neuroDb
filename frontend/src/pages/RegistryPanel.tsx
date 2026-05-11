import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'
import type { LearningSourceItem } from '../api/types'

function SourceGroup({ title, items }: { title: string; items: LearningSourceItem[] }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4 }}>
        {title} ({items.length})
      </div>
      {items.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 12 }}>None yet.</p>
      ) : items.map(item => (
        <div
          key={item.id}
          style={{ padding: '6px 8px', border: '1px solid #e2e8f0', borderRadius: 6, marginBottom: 4 }}
        >
          <div style={{ fontSize: 13 }}>{item.display_name}</div>
          <div style={{ fontSize: 11, color: '#64748b' }}>
            {item.source_key} · added by {item.added_by} on {item.added_at.slice(0, 10)}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function RegistryPanel() {
  const { data = [], isLoading, isError, error } = useQuery({
    queryKey: ['registry'],
    queryFn: api.getRegistry,
  })

  if (isLoading) return <div style={{ padding: 12 }}>Loading...</div>
  if (isError) {
    return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>
  }

  const books = data.filter(row => row.source_type === 'book')
  const papers = data.filter(row => row.source_type === 'paper')
  const datasets = data.filter(row => row.source_type === 'dataset')
  const other = data.filter(row => !['book', 'paper', 'dataset'].includes(row.source_type))

  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 12 }}>Learning Registry</h4>
      <SourceGroup title="Books" items={books} />
      <SourceGroup title="Papers & Studies" items={papers} />
      <SourceGroup title="Datasets" items={datasets} />
      {other.length > 0 && <SourceGroup title="Other" items={other} />}
    </div>
  )
}
