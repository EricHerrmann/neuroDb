import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import { useChat } from '../hooks/useChat'
import MessageBubble from './MessageBubble'

const MODES = [
  { value: 'local_db', label: 'Local DB' },
  { value: 'external_db', label: 'External DB' },
  { value: 'neuro_tutor', label: 'Neuro Tutor' },
  { value: 'neuro_research', label: 'Neuro Research' },
]

export default function ChatPanel({ agentMode }: { agentMode: string }) {
  const queryClient = useQueryClient()
  const { messages, isStreaming, sendMessage } = useChat(agentMode)
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const setMode = useMutation({
    mutationFn: (mode: string) => api.setAgentMode(mode),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['preferences'] }),
  })

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
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{
        padding: '8px 12px',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
      }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: '#475569', letterSpacing: '0.05em' }}>
          CHAT
        </span>
        <select
          value={agentMode}
          onChange={event => setMode.mutate(event.target.value)}
          style={{
            padding: '3px 6px',
            fontSize: 11,
            border: '1px solid #cbd5e1',
            borderRadius: 4,
          }}
        >
          {MODES.map(mode => (
            <option key={mode.value} value={mode.value}>{mode.label}</option>
          ))}
        </select>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
        {messages.length === 0 && (
          <p style={{ color: '#94a3b8', fontSize: 13, textAlign: 'center', marginTop: 32 }}>
            Start a conversation...
          </p>
        )}
        {messages.map((message, index) => <MessageBubble key={index} message={message} />)}
        <div ref={bottomRef} />
      </div>
      <form
        onSubmit={handleSubmit}
        style={{
          display: 'flex',
          gap: 8,
          padding: 12,
          borderTop: '1px solid #e2e8f0',
          flexShrink: 0,
        }}
      >
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
