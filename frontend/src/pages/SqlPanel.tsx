import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'

import { api } from '../api/client'
import type { SqlResult } from '../api/types'

const DEFAULT_SQL = 'SELECT * FROM v_dataset_summary ORDER BY n_datasets DESC;'
const TABLE_HINT = 'Tables: v_dataset_summary, openneuro_datasets, datasets_index, subjects, ingest_runs'

export default function SqlPanel() {
  const [sql, setSql] = useState(DEFAULT_SQL)
  const [result, setResult] = useState<SqlResult | null>(null)
  const [execError, setExecError] = useState<string | null>(null)

  const execute = useMutation({
    mutationFn: () => api.executeSQL(sql),
    onSuccess: data => {
      setResult(data)
      setExecError(null)
    },
    onError: (err: Error) => {
      setExecError(err.message)
      setResult(null)
    },
  })

  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 8 }}>SQL Query</h4>
      <textarea
        value={sql}
        onChange={event => setSql(event.target.value)}
        rows={5}
        style={{
          width: '100%',
          fontFamily: 'monospace',
          fontSize: 12,
          padding: 8,
          border: '1px solid #cbd5e1',
          borderRadius: 4,
          resize: 'vertical',
        }}
      />
      <div style={{ marginTop: 4, fontSize: 11, color: '#64748b' }}>
        {TABLE_HINT}
      </div>
      <button
        onClick={() => execute.mutate()}
        disabled={execute.isPending || !sql.trim()}
        style={{
          marginTop: 6,
          padding: '5px 14px',
          fontSize: 12,
          cursor: 'pointer',
          background: '#1e3a8a',
          color: '#fff',
          border: 'none',
          borderRadius: 4,
        }}
      >
        {execute.isPending ? 'Running...' : 'Run Query'}
      </button>

      {execError && (
        <div style={{
          marginTop: 8,
          padding: 8,
          background: '#fee2e2',
          borderRadius: 4,
          fontSize: 12,
          color: '#dc2626',
        }}>
          {execError}
        </div>
      )}

      {result && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>
            {result.row_count} row(s)
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e2e8f0', background: '#f8fafc' }}>
                  {result.columns.map(column => (
                    <th
                      key={column}
                      style={{ padding: '4px 8px', textAlign: 'left', whiteSpace: 'nowrap' }}
                    >
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, rowIndex) => (
                  <tr key={rowIndex} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    {row.map((cell, cellIndex) => (
                      <td
                        key={cellIndex}
                        style={{
                          padding: '4px 8px',
                          maxWidth: 300,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {cell === null ? <span style={{ color: '#94a3b8' }}>null</span> : String(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
