import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ResearchPanel from './ResearchPanel'

function makeWrapper(data: {
  hypotheses?: unknown[]
  metrics?: unknown
  questions?: unknown[]
} = {}) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  qc.setQueryData(['research-hypotheses'], data.hypotheses ?? [])
  qc.setQueryData(['research-metrics'], data.metrics ?? {
    approved_sources_count: 0,
    chat_sessions_count: 0,
    literature_searches_count: 0,
    research_hypotheses_count: 0,
    caveats: [],
  })
  qc.setQueryData(['research-questions'], data.questions ?? [])
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('ResearchPanel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows empty state when no hypotheses', () => {
    render(<ResearchPanel />, { wrapper: makeWrapper({ hypotheses: [] }) })
    expect(screen.getByText(/No hypotheses yet/)).toBeTruthy()
  })

  it('renders Run Review button per hypothesis', () => {
    render(<ResearchPanel />, {
      wrapper: makeWrapper({
        hypotheses: [{
          id: 1,
          title: 'LTP Hypothesis',
          mechanism: null,
          status: 'draft',
          created_at: '2026-01-01',
        }],
      }),
    })
    expect(screen.getByText('Run Review')).toBeTruthy()
  })

  it('shows Running status after clicking Run Review', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((path: string) => {
      if (path === '/api/research/hypotheses/1/review') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ task_id: 'test-task-id' }),
        })
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({ status: 'running', result: null, error: null }),
      })
    }))

    render(<ResearchPanel />, {
      wrapper: makeWrapper({
        hypotheses: [{
          id: 1,
          title: 'LTP Hypothesis',
          mechanism: null,
          status: 'draft',
          created_at: '2026-01-01',
        }],
      }),
    })
    fireEvent.click(screen.getByText('Run Review'))

    await waitFor(() => {
      expect(screen.getByText('Running...')).toBeTruthy()
    })
  })
})
