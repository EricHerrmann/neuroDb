import { useId, useState } from 'react'
import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import StatusChip from '../components/StatusChip'
import TaskStatus from '../components/TaskStatus'
import { useTask } from '../hooks/useTask'
import type { ClaimItem, EvidenceLinkItem, Hypothesis, HypothesisReviewItem, ResearchGapItem, ResearchQuestionDetail } from '../api/types'

type StatusTransition = { label: string; onSelect: () => void; description?: string }

const STATUS_DESCRIPTIONS: Record<string, string> = {
  active: 'This evidence relationship is currently counted in the hypothesis evidence set.',
  approved: 'This item has been accepted for use as trusted project evidence.',
  archived: 'This item is hidden from the active workflow but preserved for audit history.',
  candidate: 'This item was proposed or extracted and still needs review before it is trusted.',
  closed: 'This research question is no longer active.',
  complete: 'This hypothesis has completed its current workflow.',
  converted_to_hypothesis: 'This question has been promoted into a draft hypothesis.',
  draft: 'This hypothesis is still being shaped and is not ready for a plan.',
  needs_evidence: 'This hypothesis needs stronger supporting evidence before planning.',
  open: 'This item is still active and needs review or follow-up.',
  parked: 'This question is intentionally paused but kept for later review.',
  ready_for_plan: 'This hypothesis has enough structure to start a test plan.',
  rejected: 'This item was reviewed and should not be used as accepted support.',
  resolved: 'This gap has been addressed and is no longer active.',
  retracted: 'This evidence relationship is kept for audit but no longer counted as active support.',
  reviewed: 'This hypothesis has an agent review recorded for follow-up.',
}

const ACTION_DESCRIPTIONS: Record<string, string> = {
  Approve: 'Accept this item as usable project evidence.',
  Archive: 'Remove this item from the active workflow while keeping it in the audit trail.',
  Reject: 'Mark this item as not accepted so it should not support claims or hypotheses.',
  Resolve: 'Mark this gap as addressed so it no longer appears as active missing evidence.',
  Retract: 'Keep this evidence link for audit but remove it from active support.',
}

function describeStatus(status: string) {
  return STATUS_DESCRIPTIONS[status] ?? `Current workflow status: ${status}.`
}

function transition(label: string, onSelect: () => void): StatusTransition {
  return { label, onSelect, description: ACTION_DESCRIPTIONS[label] }
}

function Section({
  title,
  count,
  defaultOpen = true,
  children,
}: {
  title: string
  count?: number
  defaultOpen?: boolean
  children: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  const contentId = useId()
  const label = count === undefined ? title : `${title} (${count})`

  return (
    <section style={{ marginBottom: 12 }}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => setOpen(value => !value)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          padding: '3px 0',
          border: 'none',
          background: 'transparent',
          color: '#0f172a',
          cursor: 'pointer',
          fontWeight: 600,
          fontSize: 12,
          textAlign: 'left',
        }}
      >
        <span>{label}</span>
        <span style={{ fontSize: 11, color: '#64748b' }}>{open ? 'Collapse' : 'Expand'}</span>
      </button>
      {open && (
        <div id={contentId} style={{ marginTop: 6 }}>
          {children}
        </div>
      )}
    </section>
  )
}

function renderListValue(value: unknown): string {
  if (typeof value === 'string') return value
  return JSON.stringify(value)
}

function ReviewList({ label, values }: { label: string; values: unknown[] }) {
  if (values.length === 0) return null
  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#475569' }}>{label}</div>
      <ul style={{ margin: '3px 0 0 16px', padding: 0 }}>
        {values.map((value, index) => (
          <li key={`${label}-${index}`} style={{ fontSize: 11, color: '#334155' }}>
            {renderListValue(value)}
          </li>
        ))}
      </ul>
    </div>
  )
}

function StatusFilters({
  options,
  selected,
  counts,
  onToggle,
}: {
  options: string[]
  selected: string[]
  counts: Record<string, number>
  onToggle: (status: string) => void
}) {
  return (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
      {options.map(status => {
        const count = counts[status] ?? 0
        return (
          <button
            key={status}
            type="button"
            onClick={() => onToggle(status)}
            style={{
              fontSize: 11,
              padding: '2px 7px',
              border: '1px solid #cbd5e1',
              borderRadius: 4,
              background: selected.includes(status) ? '#1e3a8a' : '#fff',
              color: selected.includes(status) ? '#fff' : count === 0 ? '#94a3b8' : '#334155',
              cursor: 'pointer',
            }}
          >
            {status} ({count})
          </button>
        )
      })}
    </div>
  )
}

function QuestionStatusChip({ question }: { question: { id: number; status: string } }) {
  const queryClient = useQueryClient()
  const archive = useMutation({
    mutationFn: () => api.archiveQuestion(question.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-questions-detail'] }),
  })
  const transitions: StatusTransition[] = question.status !== 'archived'
    ? [transition('Archive', () => archive.mutate())]
    : []
  return (
    <StatusChip
      status={question.status}
      transitions={transitions}
      isPending={archive.isPending}
      statusDescription={describeStatus(question.status)}
    />
  )
}

function QuestionCreateForm({ onCreated }: { onCreated: () => void }) {
  const [question, setQuestion] = useState('')
  const [topicContext, setTopicContext] = useState('')
  const create = useMutation({
    mutationFn: () => api.createQuestion({ question, topic_context: topicContext || undefined }),
    onSuccess: () => {
      setQuestion('')
      setTopicContext('')
      onCreated()
    },
  })
  return (
    <form
      onSubmit={e => { e.preventDefault(); if (question.trim()) create.mutate() }}
      style={{ marginBottom: 12 }}
    >
      <textarea
        value={question}
        onChange={e => setQuestion(e.target.value)}
        placeholder="Enter a research question…"
        rows={3}
        style={{ width: '100%', fontSize: 12, padding: 6, boxSizing: 'border-box', resize: 'vertical' }}
      />
      <input
        value={topicContext}
        onChange={e => setTopicContext(e.target.value)}
        placeholder="Topic context (optional)"
        style={{ width: '100%', fontSize: 12, padding: 4, marginTop: 4, boxSizing: 'border-box' }}
      />
      <button
        type="submit"
        disabled={!question.trim() || create.isPending}
        style={{ marginTop: 6, fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
      >
        {create.isPending ? 'Saving…' : 'Save Question'}
      </button>
      {create.isError && (
        <div style={{ color: '#dc2626', fontSize: 11, marginTop: 4 }}>
          {String(create.error)}
        </div>
      )}
    </form>
  )
}

function QuestionRow({ question, onMutated }: { question: ResearchQuestionDetail; onMutated: () => void }) {
  const queryClient = useQueryClient()
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['research-questions-detail'] })

  const deleteQ = useMutation({
    mutationFn: () => api.deleteQuestion(question.id),
    onSuccess: () => { invalidate(); onMutated() },
  })
  const confirmTopic = useMutation({
    mutationFn: (topicId: number) => api.confirmQuestionTopic(question.id, topicId),
    onSuccess: invalidate,
  })
  const dismissTopic = useMutation({
    mutationFn: (topicId: number) => api.removeQuestionTopic(question.id, topicId),
    onSuccess: invalidate,
  })
  const confirmConcept = useMutation({
    mutationFn: (conceptId: number) => api.confirmQuestionConcept(question.id, conceptId),
    onSuccess: invalidate,
  })
  const dismissConcept = useMutation({
    mutationFn: (conceptId: number) => api.removeQuestionConcept(question.id, conceptId),
    onSuccess: invalidate,
  })

  const topics = question.topics ?? []
  const concepts = question.concepts ?? []
  const confirmedTopics = topics.filter(t => t.status === 'confirmed')
  const pendingTopics = topics.filter(t => t.status === 'pending')
  const confirmedConcepts = concepts.filter(c => c.status === 'confirmed')
  const pendingConcepts = concepts.filter(c => c.status === 'pending')

  return (
    <div style={{ border: '1px solid #e2e8f0', borderRadius: 6, padding: '8px 10px', marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ fontSize: 12, color: '#1e293b', flex: 1 }}>{question.question}</div>
        <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
          <QuestionStatusChip question={question} />
          <button
            type="button"
            onClick={() => {
              if (window.confirm('Delete this question and all its topic/concept links?')) {
                deleteQ.mutate()
              }
            }}
            disabled={deleteQ.isPending}
            style={{
              fontSize: 11, padding: '2px 7px', border: '1px solid #fca5a5',
              borderRadius: 4, background: '#fff', color: '#dc2626', cursor: 'pointer',
            }}
          >
            {deleteQ.isPending ? '…' : 'Delete'}
          </button>
        </div>
      </div>

      {(confirmedTopics.length > 0 || confirmedConcepts.length > 0) && (
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 6 }}>
          {confirmedTopics.map(t => (
            <span key={t.topic_id} style={{ fontSize: 10, padding: '1px 6px', background: '#dbeafe', color: '#1e40af', borderRadius: 10 }}>
              {t.topic_name}
            </span>
          ))}
          {confirmedConcepts.map(c => (
            <span key={c.concept_id} style={{ fontSize: 10, padding: '1px 6px', background: '#dcfce7', color: '#166534', borderRadius: 10 }}>
              {c.concept_name}
            </span>
          ))}
        </div>
      )}

      {(pendingTopics.length > 0 || pendingConcepts.length > 0) && (
        <div style={{ marginTop: 6 }}>
          <div style={{ fontSize: 10, color: '#64748b', marginBottom: 3 }}>Suggested — confirm or dismiss:</div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {pendingTopics.map(t => (
              <span key={t.topic_id} style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, padding: '1px 4px', border: '1px dashed #93c5fd', borderRadius: 10, color: '#1e40af' }}>
                {t.topic_name}
                {t.proposed && (
                  <span style={{ fontSize: 8, padding: '0 3px', background: '#fde68a', color: '#92400e', borderRadius: 6 }}>new</span>
                )}
                <button type="button" onClick={() => confirmTopic.mutate(t.topic_id)} style={{ fontSize: 9, border: 'none', background: 'transparent', cursor: 'pointer', color: '#16a34a', padding: 0 }}>✓</button>
                <button type="button" onClick={() => dismissTopic.mutate(t.topic_id)} style={{ fontSize: 9, border: 'none', background: 'transparent', cursor: 'pointer', color: '#dc2626', padding: 0 }}>✕</button>
              </span>
            ))}
            {pendingConcepts.map(c => (
              <span key={c.concept_id} style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, padding: '1px 4px', border: '1px dashed #86efac', borderRadius: 10, color: '#166534' }}>
                {c.concept_name}
                {c.proposed && (
                  <span style={{ fontSize: 8, padding: '0 3px', background: '#fde68a', color: '#92400e', borderRadius: 6 }}>new</span>
                )}
                <button type="button" onClick={() => confirmConcept.mutate(c.concept_id)} style={{ fontSize: 9, border: 'none', background: 'transparent', cursor: 'pointer', color: '#16a34a', padding: 0 }}>✓</button>
                <button type="button" onClick={() => dismissConcept.mutate(c.concept_id)} style={{ fontSize: 9, border: 'none', background: 'transparent', cursor: 'pointer', color: '#dc2626', padding: 0 }}>✕</button>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function HypothesisReviewCard({ review }: { review: HypothesisReviewItem }) {
  const queryClient = useQueryClient()
  const accept = useMutation({
    mutationFn: () => api.acceptHypothesisReview(review.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['research-hypotheses'] })
      queryClient.invalidateQueries({ queryKey: ['hypothesis-reviews', review.hypothesis_id] })
    },
  })
  const dismiss = useMutation({
    mutationFn: () => api.dismissHypothesisReview(review.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['research-hypotheses'] })
      queryClient.invalidateQueries({ queryKey: ['hypothesis-reviews', review.hypothesis_id] })
    },
  })

  return (
    <div style={{ marginTop: 8, padding: 8, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6 }}>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>
        {review.status} · {review.model} · {review.created_at?.slice(0, 10)}
      </div>
      <div style={{ fontSize: 12, color: '#1e293b', whiteSpace: 'pre-wrap' }}>
        {review.critique_text}
      </div>
      <ReviewList label="Unsupported claims" values={review.unsupported_claims} />
      <ReviewList label="Missing confounds" values={review.missing_confounds} />
      <div style={{ marginTop: 6 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: '#475569' }}>Suggested revisions</div>
        <div style={{ fontSize: 11, color: '#334155', whiteSpace: 'pre-wrap' }}>
          {review.suggested_revisions}
        </div>
      </div>
      {review.status === 'pending' && (
        <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
          <button
            onClick={() => accept.mutate()}
            disabled={accept.isPending || dismiss.isPending}
            style={{ fontSize: 11, padding: '2px 8px', cursor: 'pointer' }}
          >
            Accept Revisions
          </button>
          <button
            onClick={() => dismiss.mutate()}
            disabled={accept.isPending || dismiss.isPending}
            style={{ fontSize: 11, padding: '2px 8px', cursor: 'pointer' }}
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  )
}

function HypothesisDetails({ hypothesis }: { hypothesis: Hypothesis }) {
  const queryClient = useQueryClient()
  const { data: evidenceLinks = [] } = useQuery({
    queryKey: ['evidence-links', hypothesis.id],
    queryFn: () => api.getEvidenceLinks(hypothesis.id),
  })

  function LinkChip({ link }: { link: EvidenceLinkItem }) {
    const retract = useMutation({
      mutationFn: () => api.retractEvidenceLink(link.id),
      onSuccess: () => queryClient.invalidateQueries({ queryKey: ['evidence-links', hypothesis.id] }),
    })
    const transitions: StatusTransition[] = link.status === 'active'
      ? [transition('Retract', () => retract.mutate())]
      : []
    return (
      <StatusChip
        status={link.status}
        transitions={transitions}
        isPending={retract.isPending}
        statusDescription={describeStatus(link.status)}
      />
    )
  }

  return (
    <div style={{ marginTop: 8, padding: 8, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6 }}>
      {hypothesis.mechanism && (
        <div style={{ fontSize: 12, color: '#334155', marginBottom: 6 }}>
          <strong>Mechanism:</strong> {hypothesis.mechanism}
        </div>
      )}
      <ReviewList label="Evidence" values={hypothesis.evidence_json} />
      <ReviewList label="Predictions" values={hypothesis.predictions_json} />
      <ReviewList label="Relevant datasets" values={hypothesis.datasets_json} />
      <ReviewList label="Confounds" values={hypothesis.confounds_json} />
      {hypothesis.limitations && (
        <div style={{ marginTop: 6, fontSize: 11, color: '#334155' }}>
          <strong>Limitations:</strong> {hypothesis.limitations}
        </div>
      )}
      {evidenceLinks.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#475569', marginBottom: 4 }}>Evidence Links</div>
          {evidenceLinks.map(link => (
            <div key={link.id} style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', alignItems: 'center', columnGap: 8, padding: '3px 0', fontSize: 11, color: '#334155' }}>
              <LinkChip link={link} />
              <span>{link.link_type} · {link.paper_id != null ? `paper:${link.paper_id}` : link.claim_id != null ? `claim:${link.claim_id}` : link.packet_id != null ? `packet:${link.packet_id}` : `note:${link.note_id}`}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function HypothesisCard({ hypothesis }: { hypothesis: Hypothesis }) {
  const queryClient = useQueryClient()
  const [taskId, setTaskId] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)
  const { data: reviews = [] } = useQuery({
    queryKey: ['hypothesis-reviews', hypothesis.id],
    queryFn: () => api.getHypothesisReviews(hypothesis.id),
  })

  const reviewMutation = useMutation({
    mutationFn: () => api.runHypothesisReview(hypothesis.id),
    onSuccess: data => setTaskId(data.task_id),
  })

  const archiveMutation = useMutation({
    mutationFn: () => api.archiveHypothesis(hypothesis.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-hypotheses'] }),
  })

  const taskState = useTask(taskId, 180000, () => {
    queryClient.invalidateQueries({ queryKey: ['research-hypotheses'] })
    queryClient.invalidateQueries({ queryKey: ['hypothesis-reviews', hypothesis.id] })
  })

  const hypothesisTransitions: StatusTransition[] = hypothesis.status !== 'archived'
    ? [transition('Archive', () => archiveMutation.mutate())]
    : []

  return (
    <div style={{ padding: '6px 0', borderBottom: '1px solid #f1f5f9' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', alignItems: 'center', columnGap: 8 }}>
            <StatusChip
              status={hypothesis.status}
              transitions={hypothesisTransitions}
              isPending={archiveMutation.isPending}
              statusDescription={describeStatus(hypothesis.status)}
            />
            <div style={{ fontSize: 13, fontWeight: 500 }}>{hypothesis.title}</div>
          </div>
          <div style={{ fontSize: 11, color: '#94a3b8' }}>
            {hypothesis.created_at?.slice(0, 10)}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            onClick={() => setExpanded(value => !value)}
            style={{ fontSize: 11, padding: '2px 8px', cursor: 'pointer' }}
          >
            {expanded ? 'Hide' : 'Details'}
          </button>
          <button
            onClick={() => reviewMutation.mutate()}
            disabled={reviewMutation.isPending || taskState.status === 'running'}
            style={{ fontSize: 11, padding: '2px 8px', cursor: 'pointer' }}
          >
            Run Review
          </button>
        </div>
      </div>
      {expanded && <HypothesisDetails hypothesis={hypothesis} />}
      <TaskStatus
        status={taskState.status}
        error={taskState.error}
        successMessage="Review complete"
      />
      {reviewMutation.error && (
        <div style={{ fontSize: 11, color: '#dc2626', marginTop: 4 }}>
          {(reviewMutation.error as Error).message}
        </div>
      )}
      {reviews.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#1e293b' }}>
            Hypothesis Reviews
          </div>
          {reviews.map(review => (
            <HypothesisReviewCard key={review.id} review={review} />
          ))}
        </div>
      )}
    </div>
  )
}

function ClaimsSection() {
  const queryClient = useQueryClient()
  const [claimStatuses, setClaimStatuses] = useState<string[]>([])
  const { data: allClaims = [], isLoading } = useQuery({
    queryKey: ['research-claims'],
    queryFn: api.getClaims,
  })
  const claimCounts = allClaims.reduce<Record<string, number>>((acc, c) => {
    acc[c.status] = (acc[c.status] ?? 0) + 1
    return acc
  }, {})
  const claims = claimStatuses.length > 0
    ? allClaims.filter(c => claimStatuses.includes(c.status))
    : allClaims
  const toggleClaimStatus = (status: string) => {
    setClaimStatuses(current => current.includes(status)
      ? current.filter(s => s !== status)
      : [...current, status])
  }

  function ClaimChip({ claim }: { claim: ClaimItem }) {
    const approve = useMutation({
      mutationFn: () => api.approveClaim(claim.id),
      onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-claims'] }),
    })
    const reject = useMutation({
      mutationFn: () => api.rejectClaim(claim.id),
      onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-claims'] }),
    })
    const archive = useMutation({
      mutationFn: () => api.archiveClaim(claim.id),
      onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-claims'] }),
    })
    const transitions: StatusTransition[] = []
    if (claim.status === 'candidate' || claim.status === 'rejected') {
      transitions.push(transition('Approve', () => approve.mutate()))
    }
    if (claim.status === 'candidate' || claim.status === 'approved') {
      transitions.push(transition('Reject', () => reject.mutate()))
    }
    if (claim.status !== 'archived') {
      transitions.push(transition('Archive', () => archive.mutate()))
    }
    return (
      <StatusChip
        status={claim.status}
        transitions={transitions}
        isPending={approve.isPending || reject.isPending || archive.isPending}
        statusDescription={describeStatus(claim.status)}
      />
    )
  }

  return (
    <Section title="Claims" count={allClaims.length}>
      <StatusFilters
        options={['candidate', 'approved', 'rejected', 'archived']}
        selected={claimStatuses}
        counts={claimCounts}
        onToggle={toggleClaimStatus}
      />
      {isLoading ? (
        <span style={{ fontSize: 12, color: '#94a3b8' }}>Loading...</span>
      ) : claims.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 12 }}>No claims yet.</p>
      ) : claims.map(claim => (
        <div key={claim.id} style={{ padding: '6px 0', borderBottom: '1px solid #f1f5f9', display: 'grid', gridTemplateColumns: 'max-content 1fr', alignItems: 'flex-start', columnGap: 8 }}>
          <ClaimChip claim={claim} />
          <div>
            <div style={{ fontSize: 12, color: '#334155' }}>{claim.text}</div>
            <div style={{ fontSize: 10, color: '#94a3b8' }}>{claim.claim_type} · {claim.created_at?.slice(0, 10)}</div>
          </div>
        </div>
      ))}
    </Section>
  )
}

function GapsSection() {
  const queryClient = useQueryClient()
  const { data: gaps = [], isLoading } = useQuery({
    queryKey: ['research-gaps'],
    queryFn: api.getGaps,
  })

  function GapChip({ gap }: { gap: ResearchGapItem }) {
    const resolve = useMutation({
      mutationFn: () => api.resolveGap(gap.id),
      onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-gaps'] }),
    })
    const archive = useMutation({
      mutationFn: () => api.archiveGap(gap.id),
      onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-gaps'] }),
    })
    const transitions: StatusTransition[] = []
    if (gap.status === 'open') {
      transitions.push(transition('Resolve', () => resolve.mutate()))
    }
    if (gap.status !== 'archived') {
      transitions.push(transition('Archive', () => archive.mutate()))
    }
    return (
      <StatusChip
        status={gap.status}
        transitions={transitions}
        isPending={resolve.isPending || archive.isPending}
        statusDescription={describeStatus(gap.status)}
      />
    )
  }

  return (
    <Section title="Gaps" count={gaps.length}>
      {isLoading ? (
        <span style={{ fontSize: 12, color: '#94a3b8' }}>Loading...</span>
      ) : gaps.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 12 }}>No gaps yet.</p>
      ) : gaps.map(gap => (
        <div key={gap.id} style={{ padding: '6px 0', borderBottom: '1px solid #f1f5f9', display: 'grid', gridTemplateColumns: 'max-content 1fr', alignItems: 'flex-start', columnGap: 8 }}>
          <GapChip gap={gap} />
          <div>
            <div style={{ fontSize: 12, color: '#334155' }}>{gap.description}</div>
            <div style={{ fontSize: 10, color: '#94a3b8' }}>{gap.gap_type} · {gap.created_at?.slice(0, 10)}</div>
          </div>
        </div>
      ))}
    </Section>
  )
}

export default function ResearchPanel() {
  const queryClient = useQueryClient()
  const [selectedTopicId, setSelectedTopicId] = useState<number | undefined>(undefined)
  const [selectedQuestionStatuses, setSelectedQuestionStatuses] = useState<string[]>([])
  const [hypothesisStatuses, setHypothesisStatuses] = useState<string[]>([])

  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['research-metrics'],
    queryFn: api.getResearchMetrics,
  })
  const { data: questions = [], refetch: refetchQuestions } = useQuery({
    queryKey: ['research-questions-detail', selectedTopicId, selectedQuestionStatuses],
    queryFn: () => api.getResearchQuestionsDetail(selectedQuestionStatuses, selectedTopicId),
  })
  const { data: topicGroupings = [] } = useQuery({
    queryKey: ['groupings-for-filter', 'topic'],
    queryFn: () => api.listGroupings({ type: 'topic', status: 'active' }),
  })
  const topicOptions: Array<{ id: number; name: string }> =
    topicGroupings.map(g => ({ id: g.id, name: g.name }))
  const { data: allHypotheses = [], isLoading: hypothesesLoading } = useQuery({
    queryKey: ['research-hypotheses'],
    queryFn: () => api.getHypotheses([]),
  })
  const hypothesisCounts = allHypotheses.reduce<Record<string, number>>((acc, h) => {
    acc[h.status] = (acc[h.status] ?? 0) + 1
    return acc
  }, {})
  const hypotheses = hypothesisStatuses.length > 0
    ? allHypotheses.filter(h => hypothesisStatuses.includes(h.status))
    : allHypotheses

  const toggleHypothesisStatus = (status: string) => {
    setHypothesisStatuses(current => current.includes(status)
      ? current.filter(item => item !== status)
      : [...current, status])
  }

  const snapshot = useMutation({
    mutationFn: api.snapshotMetrics,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-metrics'] }),
  })

  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 8 }}>Research</h4>

      <Section title="Metrics">
        {metricsLoading ? (
          <span style={{ fontSize: 12, color: '#94a3b8' }}>Loading...</span>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
            {([
              ['Approved Sources', metrics?.approved_sources_count],
              ['Sessions', metrics?.chat_sessions_count],
              ['Lit Searches', metrics?.literature_searches_count],
              ['Hypotheses', metrics?.research_hypotheses_count],
            ] as [string, number | undefined][]).map(([label, value]) => (
              <div key={label} style={{ border: '1px solid #e2e8f0', borderRadius: 6, padding: '6px 10px' }}>
                <div style={{ fontSize: 18, fontWeight: 700 }}>{value ?? '-'}</div>
                <div style={{ fontSize: 11, color: '#64748b' }}>{label}</div>
              </div>
            ))}
          </div>
        )}
        <button
          onClick={() => snapshot.mutate()}
          disabled={snapshot.isPending}
          style={{ marginTop: 8, fontSize: 12, padding: '4px 10px', cursor: 'pointer' }}
        >
          Snapshot Metrics
        </button>
      </Section>

      <hr style={{ margin: '12px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />

      <Section title="Research Questions" count={questions.length}>
        <QuestionCreateForm onCreated={() => refetchQuestions()} />

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
          {(['open', 'active', 'candidate', 'archived'] as const).map(s => (
            <button
              key={s}
              type="button"
              onClick={() => setSelectedQuestionStatuses(prev =>
                prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]
              )}
              style={{
                fontSize: 11, padding: '2px 7px', border: '1px solid #cbd5e1', borderRadius: 4,
                background: selectedQuestionStatuses.includes(s) ? '#475569' : '#fff',
                color: selectedQuestionStatuses.includes(s) ? '#fff' : '#334155',
                cursor: 'pointer',
              }}
            >
              {s}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
          <button
            type="button"
            onClick={() => setSelectedTopicId(undefined)}
            style={{
              fontSize: 11, padding: '2px 7px', border: '1px solid #cbd5e1', borderRadius: 4,
              background: selectedTopicId === undefined ? '#1e3a8a' : '#fff',
              color: selectedTopicId === undefined ? '#fff' : '#334155',
              cursor: 'pointer',
            }}
          >
            All topics
          </button>
          {topicOptions.map(t => (
            <button
              key={t.id}
              type="button"
              onClick={() => setSelectedTopicId(selectedTopicId === t.id ? undefined : t.id)}
              style={{
                fontSize: 11, padding: '2px 7px', border: '1px solid #cbd5e1', borderRadius: 4,
                background: selectedTopicId === t.id ? '#1e3a8a' : '#fff',
                color: selectedTopicId === t.id ? '#fff' : '#334155',
                cursor: 'pointer',
              }}
            >
              {t.name}
            </button>
          ))}
        </div>

        {questions.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: 12 }}>No research questions yet.</p>
        ) : questions.map(q => (
          <QuestionRow key={q.id} question={q} onMutated={() => refetchQuestions()} />
        ))}
      </Section>

      <hr style={{ margin: '12px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />

      <ClaimsSection />

      <hr style={{ margin: '12px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />

      <GapsSection />

      <hr style={{ margin: '12px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />

      <Section title="Draft Hypotheses" count={allHypotheses.length}>
        <StatusFilters
          options={['draft', 'needs_evidence', 'ready_for_plan', 'archived', 'complete', 'reviewed']}
          selected={hypothesisStatuses}
          counts={hypothesisCounts}
          onToggle={toggleHypothesisStatus}
        />
        {hypothesesLoading ? (
          <span style={{ fontSize: 12, color: '#94a3b8' }}>Loading...</span>
        ) : hypotheses.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: 12 }}>No hypotheses yet.</p>
        ) : hypotheses.map(hypothesis => (
          <HypothesisCard key={hypothesis.id} hypothesis={hypothesis} />
        ))}
      </Section>
    </div>
  )
}
