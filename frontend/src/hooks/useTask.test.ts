import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useTask } from './useTask'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('useTask', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('returns idle when taskId is null', () => {
    const { result } = renderHook(() => useTask(null, 10000), { wrapper: makeWrapper() })
    expect(result.current.status).toBe('idle')
  })

  it('transitions to running immediately when taskId is set', () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'running', result: null, error: null }),
    }))
    const { result } = renderHook(() => useTask('abc', 10000), { wrapper: makeWrapper() })
    expect(result.current.status).toBe('running')
  })

  it('transitions to done and calls onSuccess when poll returns done', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'done', result: { imported: true }, error: null }),
    }))
    const onSuccess = vi.fn()
    const { result } = renderHook(() => useTask('abc', 10000, onSuccess), { wrapper: makeWrapper() })

    await act(async () => {
      await vi.runOnlyPendingTimersAsync()
    })

    expect(result.current.status).toBe('done')
    expect(onSuccess).toHaveBeenCalledWith({ imported: true })
  })

  it('transitions to failed when poll returns failed', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'failed', result: null, error: 'Something broke' }),
    }))
    const { result } = renderHook(() => useTask('abc', 10000), { wrapper: makeWrapper() })

    await act(async () => {
      await vi.runOnlyPendingTimersAsync()
    })

    expect(result.current.status).toBe('failed')
    expect(result.current.error).toBe('Something broke')
  })

  it('times out when timeoutMs elapses before done', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'running', result: null, error: null }),
    }))
    const { result } = renderHook(() => useTask('abc', 500), { wrapper: makeWrapper() })

    await act(async () => {
      vi.advanceTimersByTime(2001)
      await vi.runOnlyPendingTimersAsync()
    })

    expect(result.current.status).toBe('failed')
    expect(result.current.error).toBe('Timed out')
  })
})
