import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import { useChat } from '../hooks/useChat'
import MessageBubble from './MessageBubble'

export default function ChatPanel({ agentMode }: { agentMode: string }) {
  const { messages, isStreaming, sendMessage } = useChat(agentMode)
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!input.trim()) return
    sendMessage(input)
    setInput('')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 12 }}>
      <h3 style={{ margin: '0 0 8px', fontSize: 15, color: '#0f172a' }}>
        Chat <span style={{ fontSize: 12, color: '#64748b', fontWeight: 400 }}>({agentMode})</span>
      </h3>
      <div style={{ flex: 1, overflowY: 'auto', marginBottom: 8 }}>
        {messages.length === 0 && (
          <p style={{ color: '#94a3b8', fontSize: 13, textAlign: 'center', marginTop: 32 }}>
            Start a conversation...
          </p>
        )}
        {messages.map((message, index) => <MessageBubble key={index} message={message} />)}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 8 }}>
        <input
          value={input}
          onChange={event => setInput(event.target.value)}
          placeholder="Type a message..."
          disabled={isStreaming}
          style={{
            flex: 1,
            padding: '8px 10px',
            border: '1px solid #cbd5e1',
            borderRadius: 6,
            fontSize: 13,
          }}
        />
        <button
          type="submit"
          disabled={isStreaming || !input.trim()}
          style={{
            padding: '8px 14px',
            background: '#1e3a8a',
            color: '#fff',
            border: 'none',
            borderRadius: 6,
            cursor: 'pointer',
            fontSize: 13,
          }}
        >
          Send
        </button>
      </form>
    </div>
  )
}
