import { useCallback, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

export interface Message {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  error?: boolean
}

export function useChat(agentMode: string) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
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
          const event = JSON.parse(payload) as { type: string; text?: string }
          if (event.type === 'text_delta') {
            setMessages(prev => {
              const next = [...prev]
              const last = { ...next[next.length - 1] }
              last.content = `${last.content ?? ''}${event.text ?? ''}`
              next[next.length - 1] = last
              return next
            })
          } else if (event.type === 'done') {
            setMessages(prev => {
              const next = [...prev]
              next[next.length - 1] = { ...next[next.length - 1], streaming: false }
              return next
            })
            queryClient.invalidateQueries({ queryKey: ['sessions'] })
          } else if (event.type === 'error') {
            throw new Error(event.text ?? 'Chat stream error')
          }
        }
      }

      setMessages(prev => {
        const next = [...prev]
        next[next.length - 1] = { ...next[next.length - 1], streaming: false }
        return next
      })
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return
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

  return { messages, isStreaming, sendMessage }
}
