import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import type { CreateLearningSourceRequest, LearningSourceItem } from '../api/types'

function SourceGroup({
  title,
  items,
  onRemove,
  isRemoving,
}: {
  title: string
  items: LearningSourceItem[]
  onRemove: (id: number) => void
  isRemoving: boolean
}) {
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
          style={{
            padding: '6px 8px',
            border: '1px solid #e2e8f0',
            borderRadius: 6,
            marginBottom: 4,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 8,
          }}
        >
          <div>
            <div style={{ fontSize: 13 }}>{item.display_name}</div>
            <div style={{ fontSize: 11, color: '#64748b' }}>
              {item.source_key} · added by {item.added_by} on {item.added_at.slice(0, 10)}
            </div>
          </div>
          <button
            onClick={() => onRemove(item.id)}
            disabled={isRemoving}
            style={{ fontSize: 11, padding: '2px 6px', cursor: 'pointer', color: '#dc2626' }}
          >
            Remove
          </button>
        </div>
      ))}
    </div>
  )
}

export default function RegistryPanel() {
  const queryClient = useQueryClient()
  const { data = [], isLoading, isError, error } = useQuery({
    queryKey: ['registry'],
    queryFn: api.getRegistry,
  })
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    source_type: 'paper',
    source_key: '',
    display_name: '',
    topics_raw: '',
  })

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteRegistryEntry(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['registry'] }),
  })

  const create = useMutation({
    mutationFn: (body: CreateLearningSourceRequest) => api.createRegistryEntry(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['registry'] })
      setShowForm(false)
      setForm({ source_type: 'paper', source_key: '', display_name: '', topics_raw: '' })
    },
  })

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    const topics = form.topics_raw
      .split(',')
      .map(t => t.trim())
      .filter(t => t.length > 0)
    create.mutate({
      source_type: form.source_type,
      source_key: form.source_key,
      display_name: form.display_name,
      topics: topics.length > 0 ? topics : undefined,
    })
  }

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
      <SourceGroup title="Books" items={books} onRemove={id => remove.mutate(id)} isRemoving={remove.isPending} />
      <SourceGroup title="Papers & Studies" items={papers} onRemove={id => remove.mutate(id)} isRemoving={remove.isPending} />
      <SourceGroup title="Datasets" items={datasets} onRemove={id => remove.mutate(id)} isRemoving={remove.isPending} />
      {other.length > 0 && (
        <SourceGroup title="Other" items={other} onRemove={id => remove.mutate(id)} isRemoving={remove.isPending} />
      )}
      <button
        onClick={() => setShowForm(value => !value)}
        style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer', marginTop: 8 }}
      >
        {showForm ? 'Cancel' : 'Add Source'}
      </button>
      {showForm && (
        <form
          onSubmit={handleSubmit}
          style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}
        >
          <select
            value={form.source_type}
            onChange={event => setForm(current => ({ ...current, source_type: event.target.value }))}
            style={{ fontSize: 12, padding: '3px 6px' }}
          >
            <option value="book">book</option>
            <option value="paper">paper</option>
            <option value="dataset">dataset</option>
            <option value="arxiv">arxiv</option>
            <option value="other">other</option>
          </select>
          <input
            value={form.source_key}
            onChange={event => setForm(current => ({ ...current, source_key: event.target.value }))}
            placeholder="source key"
            required
            style={{ fontSize: 12, padding: '3px 6px' }}
          />
          <input
            value={form.display_name}
            onChange={event => setForm(current => ({ ...current, display_name: event.target.value }))}
            placeholder="display name"
            required
            style={{ fontSize: 12, padding: '3px 6px' }}
          />
          <textarea
            value={form.topics_raw}
            onChange={event => setForm(current => ({ ...current, topics_raw: event.target.value }))}
            placeholder="topics (comma separated, optional)"
            style={{ fontSize: 12, padding: '3px 6px' }}
          />
          {create.error && (
            <span style={{ fontSize: 11, color: '#dc2626' }}>
              {(create.error as Error).message}
            </span>
          )}
          <button
            type="submit"
            disabled={create.isPending}
            style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
          >
            Save
          </button>
        </form>
      )}
    </div>
  )
}
