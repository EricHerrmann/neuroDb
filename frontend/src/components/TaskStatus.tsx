export interface TaskStatusProps {
  status: 'idle' | 'running' | 'done' | 'failed'
  error: string | null
  successMessage: string
}

export default function TaskStatus({ status, error, successMessage }: TaskStatusProps) {
  if (status === 'idle') return null

  if (status === 'running') {
    return <span style={{ fontSize: 12, color: '#64748b' }}>Running...</span>
  }

  if (status === 'done') {
    return <span style={{ fontSize: 12, color: '#16a34a' }}>{successMessage}</span>
  }

  return <span style={{ fontSize: 12, color: '#dc2626' }}>{error ?? 'Failed'}</span>
}
