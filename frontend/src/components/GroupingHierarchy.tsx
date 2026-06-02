import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import type { GroupingItem } from '../api/types'

interface RowProps {
  g: GroupingItem
  parents: GroupingItem[]
  onReparent: (parentId: number | null) => void
}

function GroupingRow({ g, parents, onReparent }: RowProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
      <span style={{ fontSize: 11, color: '#1e293b' }}>{g.name}</span>
      <select
        aria-label={`parent of ${g.name}`}
        value={g.parent_id ?? ''}
        onChange={(e) => onReparent(e.target.value === '' ? null : Number(e.target.value))}
        style={{ fontSize: 10 }}
      >
        <option value="">No parent</option>
        {parents.map(p => (
          <option key={p.id} value={p.id}>{p.name}</option>
        ))}
      </select>
    </div>
  )
}

export default function GroupingHierarchy({ type = 'topic' }: { type?: string }) {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)

  const { data: groupings = [] } = useQuery({
    queryKey: ['groupings-all', type],
    queryFn: () => api.listGroupings({ type }),
  })

  const reparent = useMutation({
    mutationFn: ({ id, parentId }: { id: number; parentId: number | null }) =>
      api.patchGrouping(id, { parent_id: parentId }),
    onSuccess: () => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['groupings-all', type] })
      queryClient.invalidateQueries({ queryKey: ['groupings-for-filter', type] })
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : 'Re-parent failed'),
  })

  const childrenOf = (id: number) => groupings.filter(g => g.parent_id === id)
  const topLevel = groupings.filter(g => g.parent_id === null)

  // A grouping may be parented only under a top-level grouping that is not itself,
  // and only when it has no children of its own (single-level invariant).
  const eligibleParents = (g: GroupingItem) =>
    childrenOf(g.id).length > 0 ? [] : topLevel.filter(p => p.id !== g.id)

  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#475569', marginBottom: 4 }}>
        Topic hierarchy
      </div>
      {error && (
        <div role="alert" style={{ fontSize: 10, color: '#dc2626', marginBottom: 4 }}>{error}</div>
      )}
      {topLevel.map(parent => (
        <div key={parent.id} style={{ marginBottom: 4 }}>
          <GroupingRow
            g={parent}
            parents={eligibleParents(parent)}
            onReparent={(pid) => reparent.mutate({ id: parent.id, parentId: pid })}
          />
          <div style={{ marginLeft: 14 }}>
            {childrenOf(parent.id).map(child => (
              <GroupingRow
                key={child.id}
                g={child}
                parents={eligibleParents(child)}
                onReparent={(pid) => reparent.mutate({ id: child.id, parentId: pid })}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
