import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import TaskStatus from '../components/TaskStatus'
import { useTask } from '../hooks/useTask'
import type { DuplicateCandidate } from '../api/types'

function doiHref(doi: string): string | null {
  if (doi.startsWith('10.')) return `https://doi.org/${doi}`
  if (doi.startsWith('http://') || doi.startsWith('https://')) return doi
  return null
}

function DoiValue({ doi }: { doi: string }) {
  const href = doiHref(doi)
  if (!href) return <span>{doi}</span>
  return (
    <a href={href} target="_blank" rel="noreferrer" style={{ color: '#1d4ed8' }}>
      {doi}
    </a>
  )
}

export default function KnowledgeLibraryPanel() {
  const [statusFilter, setStatusFilter] = useState('all')
  const [approveWarnings, setApproveWarnings] = useState<Record<number, string>>({})
  const [duplicateWarnings, setDuplicateWarnings] = useState<Record<number, DuplicateCandidate[]>>({})
  const [taskId, setTaskId] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data = [], isLoading, isError, error } = useQuery({
    queryKey: ['knowledge-library', statusFilter],
    queryFn: () => api.getKnowledgeLibrary(statusFilter),
  })

  const taskState = useTask(taskId, 180000, () => {
    queryClient.invalidateQueries({ queryKey: ['knowledge-library'] })
  })

  const approveWithSummary = useMutation({
    mutationFn: (id: number) => api.approveSourceWithSummary(id),
    onSuccess: data => {
      setTaskId(data.task_id)
    },
  })
  const duplicateCheck = useMutation({
    mutationFn: (id: number) => api.getKnowledgeDuplicates(id),
    onSuccess: (data, id) => {
      if (data.candidates.length > 0) {
        setDuplicateWarnings(prev => ({ ...prev, [id]: data.candidates }))
        return
      }
      approveWithSummary.mutate(id)
    },
    onError: (_error, id) => {
      setApproveWarnings(prev => ({ ...prev, [id]: 'Duplicate check failed; approval was not started.' }))
    },
  })
  const reject = useMutation({
    mutationFn: (id: number) => api.rejectSource(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['knowledge-library'] }),
  })

  if (isLoading) return <div style={{ padding: 12 }}>Loading...</div>
  if (isError) {
    return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>
  }

  return (
    <div style={{ padding: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <h4>Knowledge Library</h4>
        <select
          value={statusFilter}
          onChange={event => setStatusFilter(event.target.value)}
          style={{ fontSize: 12, padding: '3px 6px', border: '1px solid #cbd5e1', borderRadius: 4 }}
        >
          <option value="all">All</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>
      <TaskStatus status={taskState.status} error={taskState.error} successMessage="Summary generated" />
      {data.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 13 }}>No sources matching filter.</p>
      ) : data.map(item => (
        <div
          key={item.id}
          style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, marginBottom: 8 }}
        >
          <div style={{ fontWeight: 600, fontSize: 13 }}>{item.title}</div>
          <div style={{ fontSize: 11, color: '#64748b', margin: '2px 0' }}>
            {item.source_type} · {item.topic_context.slice(0, 80)}
          </div>
          {item.doi && <div style={{ fontSize: 11 }}>DOI: <DoiValue doi={item.doi} /></div>}
          {item.summary && (
            <details style={{ fontSize: 12, marginTop: 4 }}>
              <summary style={{ cursor: 'pointer', color: '#475569' }}>Summary</summary>
              <p style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>{item.summary}</p>
            </details>
          )}
          {item.status === 'pending' ? (
            <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
              <button
                onClick={() => duplicateCheck.mutate(item.id)}
                disabled={duplicateCheck.isPending || approveWithSummary.isPending}
                style={{
                  fontSize: 12, padding: '3px 10px', cursor: 'pointer',
                  background: '#1e3a8a', color: '#fff', border: 'none', borderRadius: 4,
                }}
              >
                Approve
              </button>
              <button
                onClick={() => reject.mutate(item.id)}
                disabled={reject.isPending}
                style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
              >
                Reject
              </button>
            </div>
          ) : (
            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
              {item.status} · {item.reviewed_at?.slice(0, 10) ?? ''}
            </div>
          )}
          {duplicateWarnings[item.id]?.length > 0 && (
            <div style={{ color: '#92400e', background: '#fef3c7', padding: '6px 8px', borderRadius: 4, fontSize: 11, marginTop: 6 }}>
              <div style={{ fontWeight: 700 }}>Similar approved sources found</div>
              {duplicateWarnings[item.id].map(candidate => (
                <div key={candidate.id}>{candidate.title} {candidate.distance !== null ? `(${candidate.distance.toFixed(3)})` : ''}</div>
              ))}
              <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                <button
                  onClick={() => setDuplicateWarnings(prev => {
                    const next = { ...prev }
                    delete next[item.id]
                    return next
                  })}
                  style={{ fontSize: 11, padding: '2px 8px', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    setDuplicateWarnings(prev => {
                      const next = { ...prev }
                      delete next[item.id]
                      return next
                    })
                    approveWithSummary.mutate(item.id)
                  }}
                  style={{ fontSize: 11, padding: '2px 8px', cursor: 'pointer' }}
                >
                  Approve Anyway
                </button>
              </div>
            </div>
          )}
          {approveWarnings[item.id] && (
            <div style={{
              color: '#92400e', background: '#fef3c7',
              padding: '4px 8px', borderRadius: 4, fontSize: 11, marginTop: 4,
            }}>
              {approveWarnings[item.id]}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
