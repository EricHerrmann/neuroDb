import type { Message } from '../hooks/useChat'

export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  return (
    <div style={{
      marginBottom: 8,
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
    }}>
      <div style={{
        maxWidth: '80%',
        padding: '6px 12px',
        borderRadius: 8,
        background: isUser ? '#1e3a8a' : message.error ? '#fee2e2' : '#f1f5f9',
        color: isUser ? '#fff' : message.error ? '#dc2626' : '#0f172a',
        fontSize: 13,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}>
        {message.content}
        {message.streaming && <span style={{ opacity: 0.5 }}>▋</span>}
      </div>
    </div>
  )
}
