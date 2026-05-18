import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, it, expect, vi } from 'vitest'

import KnowledgeLibraryPanel from './KnowledgeLibraryPanel'

function makeWrapper(data: unknown) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  qc.setQueryData(['knowledge-library', 'all'], data)
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('KnowledgeLibraryPanel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows empty state', () => {
    render(<KnowledgeLibraryPanel />, { wrapper: makeWrapper([]) })
    expect(screen.getByText(/No sources/)).toBeTruthy()
  })

  it('renders pending source with approve and reject buttons', () => {
    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 1,
        title: 'LTP Review',
        doi: null,
        url: null,
        source_type: 'paper',
        topic_context: 'plasticity',
        status: 'pending',
        queued_at: '2026-01-01',
        reviewed_at: null,
        summary: null,
      }]),
    })
    expect(screen.getByText('LTP Review')).toBeTruthy()
    expect(screen.getByText('Approve')).toBeTruthy()
    expect(screen.getByText('Reject')).toBeTruthy()
  })

  it('renders bare DOI as resolver link', () => {
    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 1,
        title: 'LTP Review',
        doi: '10.1234/test',
        url: null,
        source_type: 'paper',
        topic_context: 'plasticity',
        status: 'approved',
        queued_at: '2026-01-01',
        reviewed_at: '2026-01-02',
        summary: null,
      }]),
    })

    const link = screen.getByRole('link', { name: '10.1234/test' })
    expect(link.getAttribute('href')).toBe('https://doi.org/10.1234/test')
  })

  it('starts summary task when approve has no duplicates', async () => {
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path.includes('/duplicates')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ candidates: [] }),
        })
      }
      if (path.includes('/approve-with-summary') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ task_id: 'task-1' }),
        })
      }
      if (path.includes('/api/tasks/task-1')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ status: 'running', result: null, error: null }),
        })
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => [] })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 1, title: 'LTP Review', doi: null, url: null,
        source_type: 'paper', topic_context: 'plasticity',
        status: 'pending', queued_at: '2026-01-01',
        reviewed_at: null, summary: null,
      }]),
    })
    fireEvent.click(screen.getByText('Approve'))

    await waitFor(() => {
      expect(screen.getByText(/Running/)).toBeTruthy()
    })
  })
})
