import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import type { ModelInfo, Preferences } from '../api/types'
import { useChat } from '../hooks/useChat'
import MessageBubble from './MessageBubble'

const MODES = [
  { value: 'local_db', label: 'Local DB' },
  { value: 'external_db', label: 'External DB' },
  { value: 'neuro_tutor', label: 'Neuro Tutor' },
  { value: 'neuro_research', label: 'Neuro Research' },
] as const

const MODEL_TIERS = [
  { key: 'low', label: 'Low' },
  { key: 'mid', label: 'Mid' },
  { key: 'high', label: 'High' },
] as const

type AgentModeValue = typeof MODES[number]['value']

export default function ChatPanel({ agentMode }: { agentMode: AgentModeValue }) {
  const queryClient = useQueryClient()
  const { messages, isStreaming, sendMessage, clearChat } = useChat(agentMode)
  const { data: activeContext } = useQuery({
    queryKey: ['active-context'],
    queryFn: api.getActiveContext,
  })
  const { data: modelInfo } = useQuery<ModelInfo>({
    queryKey: ['model-info'],
    queryFn: api.getModelInfo,
    staleTime: Infinity,
  })
  const [input, setInput] = useState('')
  const [clearError, setClearError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const setMode = useMutation({
    mutationFn: (mode: string) => api.setAgentMode(mode),
    onSuccess: data => {
      queryClient.setQueryData<Preferences>(['preferences'], old => ({
        relevance_threshold: old?.relevance_threshold ?? 0.5,
        agent_mode: data.agent_mode as Preferences['agent_mode'],
      }))
      queryClient.invalidateQueries({ queryKey: ['preferences'] })
    },
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

  const handleClear = async () => {
    setClearError(null)
    try {
      await clearChat()
    } catch (err) {
      setClearError(err instanceof Error ? err.message : 'Clear failed')
    }
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
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {modelInfo?.tiers && (
            <div
              aria-label="Active model tiers"
              style={{
                display: 'flex',
                gap: 6,
                alignItems: 'center',
                flexWrap: 'wrap',
                justifyContent: 'flex-end',
              }}
            >
              {MODEL_TIERS.map(tier => (
                <span
                  key={tier.key}
                  style={{ fontSize: 10, color: '#0f172a', fontWeight: 600, whiteSpace: 'nowrap' }}
                >
                  {tier.label}: {modelInfo.tiers[tier.key].model}
                </span>
              ))}
            </div>
          )}
          <button
            type="button"
            onClick={handleClear}
            disabled={isStreaming || messages.length === 0}
            style={{ fontSize: 11, padding: '3px 8px', cursor: 'pointer' }}
          >
            Clear
          </button>
          <select
            value={agentMode}
            onChange={event => setMode.mutate(event.target.value)}
            disabled={setMode.isPending}
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
      </div>
      {clearError && (
        <div style={{ color: '#dc2626', background: '#fee2e2', padding: '4px 12px', fontSize: 11 }}>
          {clearError}
        </div>
      )}
      {activeContext?.active_prior_topic && (
        <div style={{
          color: '#1d4ed8',
          background: '#eff6ff',
          borderBottom: '1px solid #bfdbfe',
          padding: '4px 12px',
          fontSize: 11,
        }}>
          Prior context: {activeContext.active_prior_topic}
        </div>
      )}
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
