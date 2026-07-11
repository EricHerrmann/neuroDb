import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import { ApiError, api, isRemoveSourceBlockedDetail } from '../api/client'
import TaskStatus from '../components/TaskStatus'
import { useTask } from '../hooks/useTask'
import type {
  DuplicateCandidate,
  FullTextStaging,
  LibraryFile,
  PaperItem,
  RemoveSourceBlockedDetail,
} from '../api/types'

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

const REFERENCE_LABELS: Record<string, string> = {
  claims: 'claims',
  study_notes: 'study notes',
  evidence_links: 'evidence links',
  dataset_packet_papers: 'dataset links',
  grouping_links: 'grouping links',
  plan_steps: 'study plan steps',
}

function ReferenceBlockerPanel({
  detail,
  replacementValue,
  onReplacementChange,
  onDeleteReferences,
  onReplaceReferences,
  isPending,
}: {
  detail: RemoveSourceBlockedDetail
  replacementValue: string
  onReplacementChange: (value: string) => void
  onDeleteReferences: () => void
  onReplaceReferences: () => void
  isPending: boolean
}) {
  const references = Object.entries(detail.blocking_references)
    .filter(([, count]) => count > 0)

  return (
    <div
      role="alert"
      style={{
        marginTop: 8,
        padding: 8,
        border: '1px solid #f59e0b',
        background: '#fffbeb',
        color: '#78350f',
        borderRadius: 6,
        display: 'grid',
        gap: 6,
        fontSize: 12,
      }}
    >
      <div>{detail.message}</div>
      {references.length > 0 && (
        <div>
          {references
            .map(([key, count]) => `${REFERENCE_LABELS[key] ?? key}: ${count}`)
            .join(' · ')}
        </div>
      )}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
        <button
          onClick={onDeleteReferences}
          disabled={isPending}
          style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer', color: '#b91c1c' }}
        >
          Delete references and remove
        </button>
        <input
          aria-label="Replacement paper ID"
          value={replacementValue}
          onChange={event => onReplacementChange(event.target.value)}
          placeholder="Replacement paper ID"
          inputMode="numeric"
          style={{ fontSize: 12, padding: '3px 6px', width: 150 }}
        />
        <button
          onClick={onReplaceReferences}
          disabled={isPending || replacementValue.trim() === ''}
          style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
        >
          Replace references and remove
        </button>
      </div>
    </div>
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

function FullTextStatusBadge() {
  return (
    <span
      title="Full text verified"
      style={{
        fontSize: 10,
        lineHeight: '16px',
        padding: '1px 6px',
        border: '1px solid #bbf7d0',
        background: '#dcfce7',
        color: '#166534',
        borderRadius: 10,
        fontWeight: 600,
      }}
    >
      full text verified
    </span>
  )
}

function SupplyLinkInput({
  value,
  onChange,
  onSubmit,
  onSubmitPath,
  isPending,
}: {
  value: string
  onChange: (v: string) => void
  onSubmit: () => void
  onSubmitPath: (name: string) => void
  isPending: boolean
}) {
  const [selectedFile, setSelectedFile] = useState('')

  const {
    data: libraryFiles = [],
    refetch: refetchLibraryFiles,
  } = useQuery<LibraryFile[]>({
    queryKey: ['library-files'],
    queryFn: () => api.listLibraryFiles(),
  })

  const canSubmitUrl = !isPending && value.trim() !== ''
  const canSubmitFile = !isPending && selectedFile !== ''
  const canSubmit = canSubmitUrl || canSubmitFile

  function handleAcquire() {
    if (selectedFile) {
      onSubmitPath(selectedFile)
      setSelectedFile('')
    } else if (value.trim()) {
      onSubmit()
    }
  }

  return (
    <div style={{ display: 'flex', gap: 4, marginTop: 4, alignItems: 'center', flexWrap: 'wrap' }}>
      <input
        type="url"
        placeholder="PDF or HTML URL"
        value={value}
        disabled={selectedFile !== ''}
        onChange={e => onChange(e.target.value)}
        style={{
          fontSize: 11,
          padding: '2px 6px',
          border: '1px solid #cbd5e1',
          borderRadius: 4,
          minWidth: 220,
          opacity: selectedFile !== '' ? 0.4 : 1,
        }}
      />
      <select
        value={selectedFile}
        disabled={value.trim() !== ''}
        onChange={e => {
          setSelectedFile(e.target.value)
          if (e.target.value !== '') {
            onChange('')
          }
        }}
        style={{
          fontSize: 11,
          padding: '2px 6px',
          border: '1px solid #cbd5e1',
          borderRadius: 4,
          opacity: value.trim() !== '' ? 0.4 : 1,
        }}
        aria-label="Pick library file"
      >
        <option value="">— or pick library file —</option>
        {libraryFiles.map(f => (
          <option key={f.name} value={f.name}>{f.name}</option>
        ))}
      </select>
      <button
        onClick={() => refetchLibraryFiles()}
        title="Refresh library file list"
        style={{
          fontSize: 11,
          padding: '2px 6px',
          cursor: 'pointer',
          background: '#f1f5f9',
          color: '#475569',
          border: '1px solid #cbd5e1',
          borderRadius: 4,
        }}
      >
        ↻
      </button>
      {libraryFiles.length === 0 && (
        <span style={{ fontSize: 10, color: '#94a3b8' }}>
          No files in library — drop a file in knowledge_library_files/
        </span>
      )}
      <button
        onClick={handleAcquire}
        disabled={!canSubmit}
        style={{
          fontSize: 11,
          padding: '2px 8px',
          cursor: !canSubmit ? 'default' : 'pointer',
          background: '#0f172a',
          color: '#fff',
          border: 'none',
          borderRadius: 4,
          opacity: !canSubmit ? 0.5 : 1,
        }}
      >
        {isPending ? 'Acquiring…' : 'Supply link / upload PDF'}
      </button>
    </div>
  )
}

function ParseReviewPanel({
  staging,
  parseConfidence,
  onConfirm,
  onReject,
  isPending,
}: {
  staging: FullTextStaging
  parseConfidence: number | null | undefined
  onConfirm: () => void
  onReject: () => void
  isPending: boolean
}) {
  const confidencePct =
    parseConfidence != null ? `${Math.round(parseConfidence * 100)}%` : 'unknown'
  return (
    <div
      style={{
        background: '#f8fafc',
        border: '1px solid #e2e8f0',
        borderRadius: 6,
        padding: 10,
        marginTop: 8,
        fontSize: 12,
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: 6 }}>Parse review</div>
      <div style={{ marginBottom: 4 }}>
        <strong>Confidence:</strong> {confidencePct}
        {staging.fetched_url && (
          <span style={{ marginLeft: 8 }}>
            <strong>Source:</strong>{' '}
            <a href={staging.fetched_url} target="_blank" rel="noreferrer" style={{ color: '#1d4ed8' }}>
              {staging.fetched_url}
            </a>
          </span>
        )}
      </div>
      {staging.sections.length > 0 && (
        <details style={{ marginTop: 4 }}>
          <summary style={{ cursor: 'pointer', color: '#475569' }}>
            {staging.sections.length} section{staging.sections.length !== 1 ? 's' : ''} parsed
          </summary>
          <div style={{ marginTop: 6, display: 'grid', gap: 4 }}>
            {staging.sections.map((sec, idx) => (
              <div key={idx} style={{ borderLeft: '2px solid #e2e8f0', paddingLeft: 8 }}>
                <div style={{ fontWeight: 600, color: '#475569' }}>{sec.label}</div>
                <div style={{ color: '#64748b', whiteSpace: 'pre-wrap', maxHeight: 80, overflow: 'hidden' }}>
                  {sec.text.slice(0, 200)}{sec.text.length > 200 ? '…' : ''}
                </div>
              </div>
            ))}
          </div>
        </details>
      )}
      <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
        <button
          onClick={onConfirm}
          disabled={isPending}
          style={{
            fontSize: 11,
            padding: '2px 10px',
            cursor: isPending ? 'default' : 'pointer',
            background: '#166534',
            color: '#fff',
            border: 'none',
            borderRadius: 4,
          }}
        >
          Confirm
        </button>
        <button
          onClick={onReject}
          disabled={isPending}
          style={{
            fontSize: 11,
            padding: '2px 10px',
            cursor: isPending ? 'default' : 'pointer',
            background: '#dc2626',
            color: '#fff',
            border: 'none',
            borderRadius: 4,
          }}
        >
          Reject
        </button>
      </div>
    </div>
  )
}

export default function KnowledgeLibraryPanel() {
  const [statusFilter, setStatusFilter] = useState('all')
  const [searchParams] = useSearchParams()
  const focusId = Number(searchParams.get('focus')) || null
  const [highlightedId, setHighlightedId] = useState<number | null>(null)
  const [approveWarnings, setApproveWarnings] = useState<Record<number, string>>({})
  const [duplicateWarnings, setDuplicateWarnings] = useState<Record<number, DuplicateCandidate[]>>({})
  const [acquireWarnings, setAcquireWarnings] = useState<Record<number, string>>({})
  const [supplyLinkInputs, setSupplyLinkInputs] = useState<Record<number, string>>({})
  const [reviewPanelOpen, setReviewPanelOpen] = useState<Record<number, boolean>>({})
  const [removeBlockers, setRemoveBlockers] = useState<Record<number, RemoveSourceBlockedDetail>>({})
  const [replacementInputs, setReplacementInputs] = useState<Record<number, string>>({})
  const [hasPending, setHasPending] = useState(false)
  const [taskId, setTaskId] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data = [], isLoading, isError, error } = useQuery({
    queryKey: ['knowledge-library', statusFilter],
    queryFn: () => api.getKnowledgeLibrary(statusFilter),
    // Poll when any item is in pending full_text_status
    refetchInterval: hasPending ? 5000 : false,
  })

  // Track whether any item needs polling
  useEffect(() => {
    const anyPending = data.some(item => item.full_text_status === 'pending')
    setHasPending(anyPending)
  }, [data])

  useEffect(() => {
    if (focusId === null) return
    const present = data.some(item => item.id === focusId)
    if (!present) {
      if (statusFilter !== 'all') setStatusFilter('all')
      return
    }

    const el = document.getElementById(`kl-paper-${focusId}`)
    if (!el) return
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setHighlightedId(focusId)
    const timer = window.setTimeout(() => setHighlightedId(null), 2500)
    return () => window.clearTimeout(timer)
  }, [focusId, data, statusFilter])

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
    mutationFn: (
      input: { id: number; action?: string; replacement_source_id?: number | null },
    ) => api.removeSource(input.id, input.action ? {
      action: input.action,
      replacement_source_id: input.replacement_source_id ?? null,
    } : undefined),
    onSuccess: (_data, input) => {
      setRemoveBlockers(prev => {
        const next = { ...prev }
        delete next[input.id]
        return next
      })
      setReplacementInputs(prev => {
        const next = { ...prev }
        delete next[input.id]
        return next
      })
      queryClient.invalidateQueries({ queryKey: ['knowledge-library'] })
    },
    onError: (error, input) => {
      const detail = error instanceof ApiError ? error.detail : null
      if (isRemoveSourceBlockedDetail(detail)) {
        setRemoveBlockers(prev => ({ ...prev, [input.id]: detail }))
      }
    },
  })
  const restore = useMutation({
    mutationFn: (id: number) => api.restoreSource(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['knowledge-library'] }),
  })

  function handleAcquireResult(data: PaperItem, id: number) {
    queryClient.invalidateQueries({ queryKey: ['knowledge-library'] })
    if (data.full_text_status === 'unavailable' && data.warnings?.[0]) {
      setAcquireWarnings(prev => ({ ...prev, [id]: data.warnings![0] }))
    } else {
      setAcquireWarnings(prev => {
        const next = { ...prev }
        delete next[id]
        return next
      })
    }
  }

  const acquireFullText = useMutation({
    mutationFn: (id: number) => api.acquireFullText(id),
    onSuccess: (data, id) => handleAcquireResult(data, id),
  })

  const acquireFullTextWithUrl = useMutation({
    mutationFn: ({ id, url }: { id: number; url: string }) =>
      api.acquireFullTextWithUrl(id, url),
    onSuccess: (data, { id }) => {
      setSupplyLinkInputs(prev => {
        const next = { ...prev }
        delete next[id]
        return next
      })
      handleAcquireResult(data, id)
    },
  })

  const acquireFullTextWithPath = useMutation({
    mutationFn: ({ id, path }: { id: number; path: string }) =>
      api.acquireFullTextWithPath(id, path),
    onSuccess: (data, { id }) => handleAcquireResult(data, id),
  })

  const reviewFullText = useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: 'confirm' | 'reject' }) =>
      api.reviewFullText(id, decision),
    onSuccess: (_data, { id }) => {
      setReviewPanelOpen(prev => {
        const next = { ...prev }
        delete next[id]
        return next
      })
      queryClient.invalidateQueries({ queryKey: ['knowledge-library'] })
    },
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
          id={`kl-paper-${item.id}`}
          data-testid={`kl-card-${item.id}`}
          data-focused={highlightedId === item.id ? 'true' : 'false'}
          style={{
            border: highlightedId === item.id ? '2px solid #f59e0b' : '1px solid #e2e8f0',
            borderRadius: 8,
            padding: 12,
            marginBottom: 8,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, color: '#94a3b8' }}>#{item.id}</span>
            <span style={{ fontWeight: 600, fontSize: 13 }}>{item.title}</span>
            <TierBadge tier={item.data_tier} />
            {item.full_text_status === 'verified' && <FullTextStatusBadge />}
          </div>
          <div style={{ fontSize: 11, color: '#64748b', margin: '2px 0' }}>
            {item.source_type} · {item.topic_context.slice(0, 80)}
          </div>
          {item.full_text_status && item.full_text_status !== 'verified' && (
            <div style={{ fontSize: 11, color: '#92400e', margin: '2px 0' }}>
              Full text: {item.full_text_status}
              {item.full_text_status === 'unavailable' && (acquireWarnings[item.id] || item.warnings?.[0]) && (
                <span style={{ marginLeft: 4, color: '#92400e' }}>— {acquireWarnings[item.id] ?? item.warnings![0]}</span>
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
                onClick={() => remove.mutate({ id: item.id })}
                disabled={remove.isPending}
                style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer', color: '#dc2626' }}
              >
                Remove
              </button>
            </div>
          ) : item.status !== 'removed' ? (
            <div style={{ marginTop: 4 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 11, color: '#94a3b8' }}>
                  {item.status} · {item.reviewed_at?.slice(0, 10) ?? ''}
                </span>
                {item.status === 'approved' && (() => {
                  const fts = item.full_text_status
                  if (fts === 'pending') {
                    return (
                      <span style={{ fontSize: 11, color: '#64748b', fontStyle: 'italic' }}>
                        Acquiring…
                      </span>
                    )
                  }
                  if (fts === 'needs_review') {
                    return (
                      <button
                        onClick={() => setReviewPanelOpen(prev => ({ ...prev, [item.id]: !prev[item.id] }))}
                        style={{
                          fontSize: 11, padding: '2px 8px', cursor: 'pointer',
                          background: '#92400e', color: '#fff', border: 'none', borderRadius: 4,
                        }}
                      >
                        Review parse
                      </button>
                    )
                  }
                  if (fts === 'verified') {
                    return (
                      <button
                        onClick={() => acquireFullText.mutate(item.id)}
                        disabled={acquireFullText.isPending}
                        style={{
                          fontSize: 11, padding: '2px 8px', cursor: 'pointer',
                          background: '#0f172a', color: '#fff', border: 'none', borderRadius: 4,
                        }}
                      >
                        Re-acquire
                      </button>
                    )
                  }
                  // metadata | abstract | unavailable | failed | null — show Acquire or recovery
                  if (fts === 'unavailable' || fts === 'failed') {
                    return null  // supply-link rendered below
                  }
                  // No full_text_status or metadata/abstract tier — primary acquire button
                  return (
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
                  )
                })()}
                <button
                  onClick={() => remove.mutate({ id: item.id })}
                  disabled={remove.isPending}
                  style={{ fontSize: 11, padding: '2px 6px', cursor: 'pointer', color: '#dc2626' }}
                >
                  Remove
                </button>
              </div>
              {/* Supply-link affordance for unavailable/failed recovery, and secondary for metadata/abstract */}
              {item.status === 'approved' && (() => {
                const fts = item.full_text_status
                const showSupplyLink =
                  fts === 'unavailable' ||
                  fts === 'failed' ||
                  fts == null ||
                  fts === 'metadata' ||
                  fts === 'abstract'
                if (!showSupplyLink) return null
                return (
                  <SupplyLinkInput
                    value={supplyLinkInputs[item.id] ?? ''}
                    onChange={v => setSupplyLinkInputs(prev => ({ ...prev, [item.id]: v }))}
                    onSubmit={() => {
                      const url = supplyLinkInputs[item.id] ?? ''
                      if (url.trim()) {
                        acquireFullTextWithUrl.mutate({ id: item.id, url: url.trim() })
                      }
                    }}
                    onSubmitPath={path => acquireFullTextWithPath.mutate({ id: item.id, path })}
                    isPending={acquireFullTextWithUrl.isPending || acquireFullTextWithPath.isPending}
                  />
                )
              })()}
              {/* Parse review panel for needs_review items */}
              {item.status === 'approved' &&
                item.full_text_status === 'needs_review' &&
                reviewPanelOpen[item.id] &&
                item.fulltext_staging && (
                  <ParseReviewPanel
                    staging={item.fulltext_staging}
                    parseConfidence={item.parse_confidence}
                    onConfirm={() => reviewFullText.mutate({ id: item.id, decision: 'confirm' })}
                    onReject={() => reviewFullText.mutate({ id: item.id, decision: 'reject' })}
                    isPending={reviewFullText.isPending}
                  />
                )}
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              <span style={{ fontSize: 11, color: '#94a3b8' }}>removed</span>
              <button
                onClick={() => restore.mutate(item.id)}
                disabled={restore.isPending}
                style={{ fontSize: 11, padding: '2px 6px', cursor: 'pointer' }}
              >
                Restore
              </button>
              <button
                onClick={() => remove.mutate({ id: item.id })}
                disabled={remove.isPending}
                style={{ fontSize: 11, padding: '2px 6px', cursor: 'pointer', color: '#dc2626' }}
              >
                Delete
              </button>
            </div>
          )}
          {removeBlockers[item.id] && (
            <ReferenceBlockerPanel
              detail={removeBlockers[item.id]}
              replacementValue={replacementInputs[item.id] ?? ''}
              onReplacementChange={value =>
                setReplacementInputs(prev => ({ ...prev, [item.id]: value }))}
              onDeleteReferences={() =>
                remove.mutate({ id: item.id, action: 'delete_with_references' })}
              onReplaceReferences={() => {
                const replacement = Number.parseInt(replacementInputs[item.id] ?? '', 10)
                if (Number.isInteger(replacement)) {
                  remove.mutate({
                    id: item.id,
                    action: 'replace_references',
                    replacement_source_id: replacement,
                  })
                }
              }}
              isPending={remove.isPending}
            />
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
