import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import TaskStatus from '../components/TaskStatus'
import { useTask } from '../hooks/useTask'
import type { Hypothesis, HypothesisReviewItem } from '../api/types'

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

function HypothesisReviewCard({ review }: { review: HypothesisReviewItem }) {
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
    </div>
  )
}

function HypothesisCard({ hypothesis }: { hypothesis: Hypothesis }) {
  const queryClient = useQueryClient()
  const [taskId, setTaskId] = useState<string | null>(null)
  const { data: reviews = [] } = useQuery({
    queryKey: ['hypothesis-reviews', hypothesis.id],
    queryFn: () => api.getHypothesisReviews(hypothesis.id),
  })

  const reviewMutation = useMutation({
    mutationFn: () => api.runHypothesisReview(hypothesis.id),
    onSuccess: data => setTaskId(data.task_id),
  })

  const taskState = useTask(taskId, 180000, () => {
    queryClient.invalidateQueries({ queryKey: ['research-hypotheses'] })
    queryClient.invalidateQueries({ queryKey: ['hypothesis-reviews', hypothesis.id] })
  })

  return (
    <div style={{ padding: '6px 0', borderBottom: '1px solid #f1f5f9' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 500 }}>{hypothesis.title}</div>
          <div style={{ fontSize: 11, color: '#94a3b8' }}>
            {hypothesis.status} · {hypothesis.created_at?.slice(0, 10)}
          </div>
        </div>
        <button
          onClick={() => reviewMutation.mutate()}
          disabled={reviewMutation.isPending || taskState.status === 'running'}
          style={{ fontSize: 11, padding: '2px 8px', cursor: 'pointer' }}
        >
          Run Review
        </button>
      </div>
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

export default function ResearchPanel() {
  const queryClient = useQueryClient()

  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['research-metrics'],
    queryFn: api.getResearchMetrics,
  })
  const { data: questions = [], isLoading: questionsLoading } = useQuery({
    queryKey: ['research-questions'],
    queryFn: () => api.getResearchQuestions('all'),
  })
  const { data: hypotheses = [], isLoading: hypothesesLoading } = useQuery({
    queryKey: ['research-hypotheses'],
    queryFn: () => api.getHypotheses('all'),
  })

  const snapshot = useMutation({
    mutationFn: api.snapshotMetrics,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-metrics'] }),
  })

  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 8 }}>Research</h4>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>Metrics</div>
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
      </div>

      <hr style={{ margin: '12px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>
          Research Questions ({questions.length})
        </div>
        {questionsLoading ? (
          <span style={{ fontSize: 12, color: '#94a3b8' }}>Loading...</span>
        ) : questions.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: 12 }}>No research questions yet.</p>
        ) : questions.map(question => (
          <div key={question.id} style={{ padding: '6px 0', borderBottom: '1px solid #f1f5f9' }}>
            <div style={{ fontSize: 13 }}>{question.question}</div>
            <div style={{ fontSize: 11, color: '#94a3b8' }}>
              {question.status} · {question.created_at?.slice(0, 10)}
            </div>
          </div>
        ))}
      </div>

      <hr style={{ margin: '12px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />

      <div>
        <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>
          Draft Hypotheses ({hypotheses.length})
        </div>
        {hypothesesLoading ? (
          <span style={{ fontSize: 12, color: '#94a3b8' }}>Loading...</span>
        ) : hypotheses.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: 12 }}>No hypotheses yet.</p>
        ) : hypotheses.map(hypothesis => (
          <HypothesisCard key={hypothesis.id} hypothesis={hypothesis} />
        ))}
      </div>
    </div>
  )
}
