import type { ThinkingState } from '../hooks/useChat'

function Dots() {
  return (
    <span aria-hidden="true" style={{ display: 'inline-flex', gap: 2, marginLeft: 3 }}>
      {[0, 1, 2].map(index => (
        <span
          key={index}
          style={{
            animation: 'neurodb-thinking-dot 1s infinite',
            animationDelay: `${index * 0.18}s`,
          }}
        >
          ·
        </span>
      ))}
    </span>
  )
}

export default function ThinkingBubble({
  state,
  activeTool,
}: {
  state: ThinkingState
  activeTool: string | null
}) {
  if (state !== 'thinking' && state !== 'tool') return null

  return (
    <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'flex-start' }}>
      <style>
        {'@keyframes neurodb-thinking-dot { 0%, 80%, 100% { opacity: 0.25; } 40% { opacity: 1; } }'}
      </style>
      <div
        role="status"
        aria-live="polite"
        style={{
          maxWidth: '80%',
          padding: '6px 12px',
          borderRadius: 8,
          background: '#f1f5f9',
          color: '#475569',
          fontSize: 13,
          wordBreak: 'break-word',
        }}
      >
        {state === 'tool' ? `▸ ${activeTool ?? 'tool'}` : 'Thinking'}
        <Dots />
      </div>
    </div>
  )
}
