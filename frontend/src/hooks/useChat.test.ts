import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import { useChat } from './useChat'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

function makeSseResponse(events: Array<Record<string, unknown>>) {
  const lines = events.map(event => `data: ${JSON.stringify(event)}\n\n`).join('')
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(lines))
      controller.close()
    },
  })
  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

describe('useChat', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('accumulates text_delta chunks into assistant message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      makeSseResponse([
        { type: 'text_delta', text: 'Hello' },
        { type: 'text_delta', text: ' world' },
        { type: 'done' },
      ]),
    ))
    const { result } = renderHook(() => useChat('local_db'), { wrapper: makeWrapper() })

    await act(async () => {
      await result.current.sendMessage('hi')
    })

    expect(result.current.messages).toHaveLength(2)
    expect(result.current.messages[0]).toMatchObject({ role: 'user', content: 'hi' })
    expect(result.current.messages[1]).toMatchObject({
      role: 'assistant',
      content: 'Hello world',
      streaming: false,
    })
  })

  it('marks message as error when fetch returns non-ok', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response('Bad request', { status: 400 }),
    ))
    const { result } = renderHook(() => useChat('local_db'), { wrapper: makeWrapper() })

    await act(async () => {
      await result.current.sendMessage('hi')
    })

    const last = result.current.messages[result.current.messages.length - 1]
    expect(last.error).toBe(true)
    expect(last.streaming).toBe(false)
  })

  it('does not send empty messages', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useChat('local_db'), { wrapper: makeWrapper() })

    await act(async () => {
      await result.current.sendMessage('   ')
    })

    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.current.messages).toHaveLength(0)
  })
})
