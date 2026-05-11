import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { api } from '../api/client'
import TaskStatus from '../components/TaskStatus'
import { useTask } from '../hooks/useTask'
import type { ImportQueueItem, SourceSuggestionItem } from '../api/types'

function ImportQueueRow({ item }: { item: ImportQueueItem }) {
  const queryClient = useQueryClient()
  const [taskId, setTaskId] = useState<string | null>(null)

  const dismiss = useMutation({
    mutationFn: () => api.dismissImportItem(item.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['suggestions'] }),
  })

  const importMutation = useMutation({
    mutationFn: () => api.importDataset(item.source, item.source_id),
    onSuccess: data => setTaskId(data.task_id),
  })

  const taskState = useTask(taskId, 180000, () => {
    queryClient.invalidateQueries({ queryKey: ['datasets'] })
  })

  return (
    <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, marginBottom: 8 }}>
      <strong>{item.title ?? item.source_id}</strong>
      {' '}
      <code style={{ fontSize: 11 }}>{item.source}:{item.source_id}</code>
      {item.chapter_ref && (
        <div style={{ fontSize: 12, color: '#64748b' }}>While reading: {item.chapter_ref}</div>
      )}
      {item.reason && (
        <p style={{ fontSize: 12, margin: '4px 0', color: '#475569' }}>{item.reason}</p>
      )}
      <div style={{ display: 'flex', gap: 6, marginTop: 6, alignItems: 'center' }}>
        <button
          onClick={() => dismiss.mutate()}
          disabled={dismiss.isPending}
          style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
        >
          Dismiss
        </button>
        <button
          onClick={() => importMutation.mutate()}
          disabled={importMutation.isPending || taskState.status === 'running'}
          style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
        >
          Import
        </button>
        <TaskStatus status={taskState.status} error={taskState.error} successMessage="Import complete" />
      </div>
      {importMutation.error && (
        <div style={{ fontSize: 11, color: '#dc2626', marginTop: 4 }}>
          {(importMutation.error as Error).message}
        </div>
      )}
    </div>
  )
}

function SourceSuggestionRow({ item }: { item: SourceSuggestionItem }) {
  const queryClient = useQueryClient()

  const dismiss = useMutation({
    mutationFn: () => api.dismissSourceSuggestion(item.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['suggestions'] }),
  })

  const promote = useMutation({
    mutationFn: () => api.promoteSourceSuggestion(item.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suggestions'] })
      queryClient.invalidateQueries({ queryKey: ['registry'] })
    },
  })

  return (
    <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, marginBottom: 8 }}>
      <strong>{item.display_name ?? item.reference ?? '-'}</strong>
      {' '}
      <code style={{ fontSize: 11 }}>({item.suggestion_type})</code>
      {item.reason && (
        <p style={{ fontSize: 12, margin: '4px 0', color: '#475569' }}>{item.reason}</p>
      )}
      <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
        <button
          onClick={() => dismiss.mutate()}
          disabled={dismiss.isPending}
          style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
        >
          Dismiss
        </button>
        <button
          onClick={() => promote.mutate()}
          disabled={promote.isPending}
          style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
        >
          Promote
        </button>
      </div>
      {promote.error && (
        <div style={{ fontSize: 11, color: '#dc2626', marginTop: 4 }}>
          {(promote.error as Error).message}
        </div>
      )}
    </div>
  )
}

export default function SuggestionsPanel() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['suggestions'],
    queryFn: api.getSuggestions,
  })

  if (isLoading) return <div style={{ padding: 12 }}>Loading...</div>
  if (isError) {
    return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>
  }

  const { import_queue, source_suggestions } = data!
  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 8 }}>Dataset Import Requests</h4>
      {import_queue.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 13 }}>No pending import suggestions.</p>
      ) : import_queue.map(item => (
        <ImportQueueRow key={item.id} item={item} />
      ))}

      <hr style={{ margin: '12px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />

      <h4 style={{ marginBottom: 8 }}>Connector Requests</h4>
      {source_suggestions.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 13 }}>No pending source suggestions.</p>
      ) : source_suggestions.map(item => (
        <SourceSuggestionRow key={item.id} item={item} />
      ))}
    </div>
  )
}
