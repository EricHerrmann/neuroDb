import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import TaskStatus from '../components/TaskStatus'
import { useTask } from '../hooks/useTask'
import type { DuplicateCandidate, PaperItem } from '../api/types'

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

function externalHref(value: string): string | null {
  if (value.startsWith('http://') || value.startsWith('https://')) return value
  return null
}

function titleSearchHref(title: string): string {
  return `https://scholar.google.com/scholar?q=${encodeURIComponent(title)}`
}

function ExternalLink({ href, label }: { href: string; label: string }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" style={{ color: '#1d4ed8' }}>
      {label}
    </a>
  )
}

function GroupingLinks({ item }: { item: PaperItem }) {
  const links = item.grouping_links ?? []
  if (links.length === 0) return null

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
      {links.map(link => (
        <span
          key={`${link.grouping_type}-${link.grouping_id}`}
          title={`${link.grouping_type} grouping link: ${link.status}`}
          style={{
            fontSize: 10,
            lineHeight: '16px',
            padding: '1px 6px',
            border: '1px solid #bfdbfe',
            background: '#eff6ff',
            color: '#1e40af',
            borderRadius: 10,
          }}
        >
          {link.grouping_type}: {link.grouping_name}
          {link.status !== 'confirmed' ? ` (${link.status})` : ''}
        </span>
      ))}
    </div>
  )
}

function SourceReviewDetails({ item }: { item: PaperItem }) {
  const sourceHref = item.url ? externalHref(item.url) : null
  const hasRecordedReference = Boolean(item.doi || sourceHref)

  return (
    <details style={{ fontSize: 12, marginTop: 6 }}>
      <summary style={{ cursor: 'pointer', color: '#475569' }}>Review details</summary>
      <div style={{ marginTop: 6, display: 'grid', gap: 4 }}>
        <div><strong>Status:</strong> {item.status}</div>
        <div><strong>Queued:</strong> {item.queued_at?.slice(0, 10) ?? '-'}</div>
        {item.year !== null && item.year !== undefined && (
          <div><strong>Year:</strong> {item.year}</div>
        )}
        <div><strong>Type:</strong> {item.source_type}</div>
        <div><strong>Relevance:</strong> {item.topic_context || '-'}</div>
        {item.doi && (
          <div><strong>DOI:</strong> <DoiValue doi={item.doi} /></div>
        )}
        {item.url && (
          <div>
            <strong>URL:</strong>{' '}
            {sourceHref ? <ExternalLink href={sourceHref} label={item.url} /> : item.url}
          </div>
        )}
        {(item.grouping_links ?? []).length > 0 && (
          <div>
            <strong>Grouping links:</strong>{' '}
            {(item.grouping_links ?? [])
              .map(link => `${link.grouping_type}: ${link.grouping_name} (${link.status})`)
              .join(', ')}
          </div>
        )}
        {!hasRecordedReference && (
          <div style={{ color: '#92400e' }}>
            No DOI or URL is recorded yet.{' '}
            <ExternalLink href={titleSearchHref(item.title)} label="Verify by title" />
          </div>
        )}
        {item.abstract && (
          <div>
            <strong>Abstract:</strong>
            <p style={{ margin: '3px 0 0', whiteSpace: 'pre-wrap' }}>{item.abstract}</p>
          </div>
        )}
      </div>
    </details>
  )
}

const TIER_LABELS: Record<string, string> = {
  full_text: 'full text',
  abstract: 'abstract',
  metadata: 'metadata',
}

const TIER_COLORS: Record<string, { background: string; color: string; border: string }> = {
  full_text: { background: '#dcfce7', color: '#166534', border: '#bbf7d0' },
  abstract: { background: '#dbeafe', color: '#1e40af', border: '#bfdbfe' },
  metadata: { background: '#f1f5f9', color: '#475569', border: '#cbd5e1' },
}

function TierBadge({ tier }: { tier: string | undefined }) {
  const key = tier ?? 'metadata'
  const label = TIER_LABELS[key] ?? key
  const colors = TIER_COLORS[key] ?? TIER_COLORS.metadata
  return (
    <span
      title={`Data tier: ${key}`}
      style={{
        fontSize: 10,
        lineHeight: '16px',
        padding: '1px 6px',
        border: `1px solid ${colors.border}`,
        background: colors.background,
        color: colors.color,
        borderRadius: 10,
        fontWeight: 600,
      }}
    >
      {label}
    </span>
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
  const remove = useMutation({
    mutationFn: (id: number) => api.removeSource(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['knowledge-library'] }),
  })
  const acquireFullText = useMutation({
    mutationFn: (id: number) => api.acquireFullText(id),
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
          <option value="removed">Removed</option>
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 600, fontSize: 13 }}>{item.title}</span>
            <TierBadge tier={item.data_tier} />
          </div>
          <div style={{ fontSize: 11, color: '#64748b', margin: '2px 0' }}>
            {item.source_type} · {item.topic_context.slice(0, 80)}
          </div>
          {item.full_text_status && (
            <div style={{ fontSize: 11, color: item.full_text_status === 'verified' ? '#166534' : '#92400e', margin: '2px 0' }}>
              Full text: {item.full_text_status}
              {item.full_text_status === 'unavailable' && item.warnings?.[0] && (
                <span style={{ marginLeft: 4, color: '#92400e' }}>— {item.warnings[0]}</span>
              )}
            </div>
          )}
          <GroupingLinks item={item} />
          {item.doi && <div style={{ fontSize: 11 }}>DOI: <DoiValue doi={item.doi} /></div>}
          {item.url && (
            <div style={{ fontSize: 11 }}>
              URL:{' '}
              {externalHref(item.url)
                ? <ExternalLink href={item.url} label={item.url} />
                : item.url}
            </div>
          )}
          <SourceReviewDetails item={item} />
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
              <button
                onClick={() => remove.mutate(item.id)}
                disabled={remove.isPending}
                style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer', color: '#dc2626' }}
              >
                Remove
              </button>
            </div>
          ) : item.status !== 'removed' ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 11, color: '#94a3b8' }}>
                {item.status} · {item.reviewed_at?.slice(0, 10) ?? ''}
              </span>
              {item.status === 'approved' && (
                <button
                  onClick={() => acquireFullText.mutate(item.id)}
                  disabled={acquireFullText.isPending}
                  style={{
                    fontSize: 11, padding: '2px 8px', cursor: 'pointer',
                    background: '#0f172a', color: '#fff', border: 'none', borderRadius: 4,
                  }}
                >
                  {acquireFullText.isPending ? 'Acquiring…' : 'Acquire full text'}
                </button>
              )}
              <button
                onClick={() => remove.mutate(item.id)}
                disabled={remove.isPending}
                style={{ fontSize: 11, padding: '2px 6px', cursor: 'pointer', color: '#dc2626' }}
              >
                Remove
              </button>
            </div>
          ) : (
            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
              removed
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
