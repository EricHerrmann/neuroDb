import { useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import type { CreateStudyNoteRequest, DatasetItem } from '../api/types'

export default function DatasetsPanel() {
  const queryClient = useQueryClient()
  const [keyword, setKeyword] = useState('')
  const [submitted, setSubmitted] = useState<string | undefined>(undefined)
  const [modality, setModality] = useState('all')
  const [taggingId, setTaggingId] = useState<number | null>(null)
  const [tagConcept, setTagConcept] = useState('')
  const [tagWarning, setTagWarning] = useState<Record<number, string>>({})
  const [taggedRows, setTaggedRows] = useState<Record<number, boolean>>({})

  const { data = [], isLoading, isError, error } = useQuery<DatasetItem[]>({
    queryKey: ['datasets', submitted, modality],
    queryFn: () => api.getDatasets(submitted, modality),
  })

  const tagDataset = useMutation({
    mutationFn: ({ row, concept }: { row: DatasetItem; concept: string }) => {
      const body: CreateStudyNoteRequest = {
        source: row.source,
        source_id: row.source_id,
        concept_tag: concept,
      }
      return api.createStudyNote(body)
    },
    onSuccess: (note, { row }) => {
      queryClient.invalidateQueries({ queryKey: ['study-log'] })
      setTaggedRows(prev => ({ ...prev, [row.id]: true }))
      setTagWarning(prev => ({
        ...prev,
        [row.id]: note.warnings?.[0] ?? '',
      }))
      setTagConcept('')
      setTaggingId(null)
    },
  })

  const handleSearch = (event: FormEvent) => {
    event.preventDefault()
    setSubmitted(keyword.trim() || undefined)
  }

  const openTagForm = (row: DatasetItem) => {
    setTaggingId(row.id)
    setTagConcept('')
  }

  const submitTag = (event: FormEvent, row: DatasetItem) => {
    event.preventDefault()
    if (!tagConcept.trim()) return
    tagDataset.mutate({ row, concept: tagConcept.trim() })
  }

  if (isLoading) return <div style={{ padding: 12 }}>Loading...</div>
  if (isError) {
    return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>
  }

  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 8 }}>Datasets</h4>
      <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input
          value={keyword}
          onChange={event => setKeyword(event.target.value)}
          placeholder="Search by source ID..."
          style={{
            flex: 1,
            padding: '5px 8px',
            border: '1px solid #cbd5e1',
            borderRadius: 4,
            fontSize: 12,
          }}
        />
        <button type="submit" style={{ padding: '5px 12px', fontSize: 12, cursor: 'pointer' }}>
          Search
        </button>
      </form>
      <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
        {['all', 'MRI', 'fMRI', 'EEG', 'MEG', 'ISH'].map(value => (
          <button
            key={value}
            type="button"
            onClick={() => setModality(value)}
            style={{
              fontSize: 11,
              padding: '3px 8px',
              border: '1px solid #cbd5e1',
              borderRadius: 4,
              background: modality === value ? '#1e3a8a' : '#fff',
              color: modality === value ? '#fff' : '#334155',
              cursor: 'pointer',
            }}
          >
            {value === 'all' ? 'All modalities' : value}
          </button>
        ))}
      </div>
      {data.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 13 }}>No datasets found.</p>
      ) : (
        <>
          <p style={{ fontSize: 12, color: '#64748b', marginBottom: 6 }}>
            {data.length} dataset(s)
          </p>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
                <th style={{ padding: '4px 8px' }}>Dataset</th>
                <th style={{ padding: '4px 8px' }}>Metadata</th>
                <th style={{ padding: '4px 8px' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {data.map(row => (
                <tr key={row.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '4px 8px' }}>
                    <div style={{ fontWeight: 600 }}>{row.title || row.source_id}</div>
                    <div style={{ color: '#64748b', fontSize: 11 }}>{row.source}:{row.source_id}</div>
                  </td>
                  <td style={{ padding: '4px 8px', color: '#475569' }}>
                    <span>{row.modality || 'unknown modality'}</span>
                    <span style={{ marginLeft: 8 }}>{row.n_subjects ?? '-'} subjects</span>
                  </td>
                  <td style={{ padding: '4px 8px', minWidth: 180 }}>
                    {taggingId === row.id ? (
                      <form onSubmit={event => submitTag(event, row)} style={{ display: 'flex', gap: 4 }}>
                        <input
                          value={tagConcept}
                          onChange={event => setTagConcept(event.target.value)}
                          placeholder="concept_tag"
                          style={{ minWidth: 0, flex: 1, fontSize: 11, padding: '2px 5px' }}
                        />
                        <button
                          type="submit"
                          disabled={tagDataset.isPending || !tagConcept.trim()}
                          style={{ fontSize: 11, padding: '2px 6px', cursor: 'pointer' }}
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          onClick={() => setTaggingId(null)}
                          style={{ fontSize: 11, padding: '2px 6px', cursor: 'pointer' }}
                        >
                          Cancel
                        </button>
                      </form>
                    ) : (
                      <button
                        type="button"
                        onClick={() => openTagForm(row)}
                        style={{ fontSize: 11, padding: '2px 8px', cursor: 'pointer' }}
                      >
                        Tag
                      </button>
                    )}
                    {taggedRows[row.id] && !tagWarning[row.id] && (
                      <div style={{ fontSize: 11, color: '#15803d', marginTop: 3 }}>Tagged</div>
                    )}
                    {tagWarning[row.id] && (
                      <div style={{ fontSize: 11, color: '#92400e', marginTop: 3 }}>{tagWarning[row.id]}</div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
