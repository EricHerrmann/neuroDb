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

function makeControlledSseResponse() {
  const encoder = new TextEncoder()
  let controllerRef!: ReadableStreamDefaultController<Uint8Array>
  const stream = new ReadableStream({
    start(controller) {
      controllerRef = controller
    },
  })
  return {
    response: new Response(stream, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    }),
    enqueue(event: Record<string, unknown>) {
      controllerRef.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`))
    },
    close() {
      controllerRef.close()
    },
  }
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
    expect(result.current.thinkingState).toBe('idle')
    expect(result.current.activeTool).toBeNull()
  })

  it('starts in thinking state while waiting for first stream event', async () => {
    let resolveFetch!: (value: Response) => void
    const pendingFetch = new Promise<Response>(resolve => {
      resolveFetch = resolve
    })
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(pendingFetch))
    const { result } = renderHook(() => useChat('local_db'), { wrapper: makeWrapper() })

    await act(async () => {
      void result.current.sendMessage('hi')
      await Promise.resolve()
    })

    expect(result.current.thinkingState).toBe('thinking')
    expect(result.current.activeTool).toBeNull()

    await act(async () => {
      resolveFetch(makeSseResponse([{ type: 'done' }]))
      await Promise.resolve()
    })
  })

  it('tracks active tool and transitions to streaming text', async () => {
    const controlled = makeControlledSseResponse()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(controlled.response))
    const { result } = renderHook(() => useChat('local_db'), { wrapper: makeWrapper() })

    await act(async () => {
      void result.current.sendMessage('count')
      await Promise.resolve()
    })

    await act(async () => {
      controlled.enqueue({ type: 'tool_start', tool_name: 'query_db', tool_input: { sql: 'SELECT 1' } })
      await Promise.resolve()
    })

    expect(result.current.thinkingState).toBe('tool')
    expect(result.current.activeTool).toBe('query_db')

    await act(async () => {
      controlled.enqueue({ type: 'text_delta', text: 'Done' })
      await Promise.resolve()
    })

    expect(result.current.thinkingState).toBe('streaming')
    expect(result.current.activeTool).toBeNull()

    await act(async () => {
      controlled.enqueue({ type: 'done' })
      controlled.close()
      await Promise.resolve()
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
    expect(result.current.thinkingState).toBe('idle')
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

describe('useChat evidenceSummary', () => {
  beforeEach(() => { vi.restoreAllMocks() })

  it('attaches evidenceSummary to message when context_summary event arrives', async () => {
    const sseLines = [
      'data: {"type":"context_summary","context_mode":"contextual","papers_count":3,"notes_count":2,"claims_count":1,"datasets_count":0,"gaps_count":1}',
      'data: {"type":"done","text":"Here is my answer."}',
    ].join('\n') + '\n'

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(sseLines, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      }),
    ))

    const { result } = renderHook(() => useChat('neuro_tutor'), { wrapper: makeWrapper() })

    await act(async () => {
      await result.current.sendMessage('What is LTP?')
    })

    const assistantMsg = result.current.messages.find(m => m.role === 'assistant')
    expect(assistantMsg?.evidenceSummary).toEqual({
      mode: 'contextual',
      papers: 3,
      notes: 2,
      claims: 1,
      datasets: 0,
      gaps: 1,
    })
  })

  it('evidenceSummary is null when no context_summary event', async () => {
    const sseLines = 'data: {"type":"done","text":"answer"}\n'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(sseLines, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      }),
    ))

    const { result } = renderHook(() => useChat('neuro_tutor'), { wrapper: makeWrapper() })

    await act(async () => {
      await result.current.sendMessage('test')
    })

    const assistantMsg = result.current.messages.find(m => m.role === 'assistant')
    expect(assistantMsg?.evidenceSummary ?? null).toBeNull()
  })
})
