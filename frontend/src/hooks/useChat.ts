import { useCallback, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { EvidenceSummary } from '../api/types'

export interface Message {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  error?: boolean
  activity?: ToolActivity[]
  notices?: ProviderNotice[]
  evidenceSummary?: EvidenceSummary | null
}

export interface ProviderNotice {
  id: string
  text: string
  failedProvider?: string
  fallbackProvider?: string
}

export interface ToolActivity {
  id: string
  toolName: string
  input?: unknown
  result?: string
  status: 'running' | 'done'
}

export type ThinkingState = 'idle' | 'thinking' | 'tool' | 'streaming'

export function useChat(agentMode: string) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [thinkingState, setThinkingState] = useState<ThinkingState>('idle')
  const [activeTool, setActiveTool] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID())
  const queryClient = useQueryClient()
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isStreaming) return

    const history = messages.map(message => ({
      role: message.role,
      content: message.content,
    }))

    setMessages(prev => [
      ...prev,
      { role: 'user', content: trimmed },
      { role: 'assistant', content: '', streaming: true },
    ])
    setIsStreaming(true)
    setThinkingState('thinking')
    setActiveTool(null)
    abortRef.current = new AbortController()

    try {
      const res = await fetch('/api/chat/turn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmed, agent_mode: agentMode, history }),
        signal: abortRef.current.signal,
      })

      if (!res.ok) throw new Error(await res.text() || `${res.status}`)
      if (!res.body) throw new Error('Empty chat stream')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()
          if (!payload) continue
          const event = JSON.parse(payload) as {
            type: string
            text?: string
            tool_name?: string
            tool_input?: unknown
            result?: string
            context_mode?: string
            papers_count?: number
            notes_count?: number
            claims_count?: number
            datasets_count?: number
            gaps_count?: number
            failed_provider?: string
            fallback_provider?: string
          }
          if (event.type === 'text_delta') {
            setThinkingState('streaming')
            setActiveTool(null)
            setMessages(prev => {
              const next = [...prev]
              const last = { ...next[next.length - 1] }
              last.content = `${last.content ?? ''}${event.text ?? ''}`
              next[next.length - 1] = last
              return next
            })
          } else if (event.type === 'tool_start') {
            setThinkingState('tool')
            setActiveTool(event.tool_name ?? 'tool')
            setMessages(prev => {
              const next = [...prev]
              const last = { ...next[next.length - 1] }
              const activity = [...(last.activity ?? [])]
              activity.push({
                id: `${event.tool_name ?? 'tool'}-${activity.length}`,
                toolName: event.tool_name ?? 'tool',
                input: event.tool_input,
                status: 'running',
              })
              last.activity = activity
              next[next.length - 1] = last
              return next
            })
          } else if (event.type === 'tool_result') {
            setMessages(prev => {
              const next = [...prev]
              const last = { ...next[next.length - 1] }
              const activity = [...(last.activity ?? [])]
              let index = -1
              for (let i = activity.length - 1; i >= 0; i -= 1) {
                if (activity[i].toolName === (event.tool_name ?? 'tool') && activity[i].status === 'running') {
                  index = i
                  break
                }
              }
              if (index >= 0) {
                activity[index] = {
                  ...activity[index],
                  result: event.result ?? '',
                  status: 'done',
                }
              }
              last.activity = activity
              next[next.length - 1] = last
              return next
            })
          } else if (event.type === 'context_summary') {
            setMessages(prev => {
              const next = [...prev]
              const last = { ...next[next.length - 1] }
              last.evidenceSummary = {
                mode: event.context_mode ?? 'unknown',
                papers: event.papers_count ?? 0,
                notes: event.notes_count ?? 0,
                claims: event.claims_count ?? 0,
                datasets: event.datasets_count ?? 0,
                gaps: event.gaps_count ?? 0,
              }
              next[next.length - 1] = last
              return next
            })
          } else if (event.type === 'provider_fallback') {
            setThinkingState('thinking')
            setActiveTool(null)
            setMessages(prev => {
              const next = [...prev]
              const last = { ...next[next.length - 1] }
              const notices = [...(last.notices ?? [])]
              notices.push({
                id: `provider-fallback-${notices.length}`,
                text: event.text ?? 'Primary model provider failed; using fallback.',
                failedProvider: event.failed_provider,
                fallbackProvider: event.fallback_provider,
              })
              last.notices = notices
              next[next.length - 1] = last
              return next
            })
          } else if (event.type === 'done') {
            setThinkingState('idle')
            setActiveTool(null)
            setMessages(prev => {
              const next = [...prev]
              if (event.text) {
                next[next.length - 1] = { ...next[next.length - 1], content: event.text }
              }
              next[next.length - 1] = { ...next[next.length - 1], streaming: false }
              return next
            })
            queryClient.invalidateQueries({ queryKey: ['sessions'] })
            queryClient.invalidateQueries({ queryKey: ['active-context'] })
          } else if (event.type === 'error') {
            setThinkingState('idle')
            setActiveTool(null)
            throw new Error(event.text ?? 'Chat stream error')
          }
        }
      }

      setMessages(prev => {
        const next = [...prev]
        next[next.length - 1] = { ...next[next.length - 1], streaming: false }
        return next
      })
      setThinkingState('idle')
      setActiveTool(null)
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        setThinkingState('idle')
        setActiveTool(null)
        return
      }
      setThinkingState('idle')
      setActiveTool(null)
      setMessages(prev => {
        const next = [...prev]
        next[next.length - 1] = {
          ...next[next.length - 1],
          content: err instanceof Error ? err.message : 'Unknown error',
          streaming: false,
          error: true,
        }
        return next
      })
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }, [agentMode, isStreaming, messages, queryClient])

  const clearChat = useCallback(async () => {
    if (isStreaming) return
    const endedSessionId = sessionId
    const conversation = messages.map(message => ({
      role: message.role,
      content: message.content,
    }))
    await fetch(`/api/sessions/${endedSessionId}/end`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: conversation, agent_mode: agentMode }),
    }).then(async res => {
      if (!res.ok) throw new Error(await res.text() || `${res.status}`)
    })
    setMessages([])
    setThinkingState('idle')
    setActiveTool(null)
    setSessionId(crypto.randomUUID())
    queryClient.invalidateQueries({ queryKey: ['sessions'] })
    queryClient.invalidateQueries({ queryKey: ['active-context'] })
  }, [agentMode, isStreaming, messages, queryClient, sessionId])

  return { messages, isStreaming, thinkingState, activeTool, sendMessage, clearChat }
}
