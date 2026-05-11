import { useState } from 'react'
import type { FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'

export default function DatasetsPanel() {
  const [keyword, setKeyword] = useState('')
  const [submitted, setSubmitted] = useState<string | undefined>(undefined)

  const { data = [], isLoading, isError, error } = useQuery({
    queryKey: ['datasets', submitted],
    queryFn: () => api.getDatasets(submitted),
  })

  const handleSearch = (event: FormEvent) => {
    event.preventDefault()
    setSubmitted(keyword.trim() || undefined)
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
                <th style={{ padding: '4px 8px' }}>Source</th>
                <th style={{ padding: '4px 8px' }}>ID</th>
              </tr>
            </thead>
            <tbody>
              {data.map(row => (
                <tr key={row.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '4px 8px', color: '#475569' }}>{row.source}</td>
                  <td style={{ padding: '4px 8px' }}>{row.source_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
