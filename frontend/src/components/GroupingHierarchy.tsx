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
  const [collapsedParentIds, setCollapsedParentIds] = useState<Set<number>>(() => new Set())

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

  const toggleParent = (id: number) => {
    setCollapsedParentIds(current => {
      const next = new Set(current)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

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
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            {childrenOf(parent.id).length > 0 ? (
              <button
                type="button"
                aria-label={`${collapsedParentIds.has(parent.id) ? 'Expand' : 'Collapse'} ${parent.name}`}
                aria-expanded={!collapsedParentIds.has(parent.id)}
                onClick={() => toggleParent(parent.id)}
                style={{
                  width: 16,
                  height: 16,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: 0,
                  border: '1px solid #cbd5e1',
                  borderRadius: 4,
                  background: '#fff',
                  color: '#475569',
                  cursor: 'pointer',
                  fontSize: 10,
                  lineHeight: 1,
                }}
              >
                {collapsedParentIds.has(parent.id) ? '▸' : '▾'}
              </button>
            ) : (
              <span aria-hidden="true" style={{ width: 16 }} />
            )}
            <GroupingRow
              g={parent}
              parents={eligibleParents(parent)}
              onReparent={(pid) => reparent.mutate({ id: parent.id, parentId: pid })}
            />
          </div>
          {!collapsedParentIds.has(parent.id) && (
            <div style={{ marginLeft: 30 }}>
              {childrenOf(parent.id).map(child => (
                <GroupingRow
                  key={child.id}
                  g={child}
                  parents={eligibleParents(child)}
                  onReparent={(pid) => reparent.mutate({ id: child.id, parentId: pid })}
                />
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
