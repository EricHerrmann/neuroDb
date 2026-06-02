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

    const link = screen.getAllByRole('link', { name: '10.1234/test' })[0]
    expect(link.getAttribute('href')).toBe('https://doi.org/10.1234/test')
  })

  it('renders expandable review details and source URL for pending papers', () => {
    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 16,
        title: 'Bridging Neuroscience and AI: CLS Theory',
        doi: null,
        url: 'https://example.org/cls-review',
        source_type: 'review',
        topic_context: 'CLS ↔ LLM pretraining/RAG',
        status: 'pending',
        queued_at: '2026-06-02',
        reviewed_at: null,
        summary: null,
        abstract: 'Candidate review requiring DOI verification.',
        year: null,
      }]),
    })

    expect(screen.getAllByRole('link', { name: 'https://example.org/cls-review' })[0].getAttribute('href'))
      .toBe('https://example.org/cls-review')

    fireEvent.click(screen.getByText('Review details'))

    expect(screen.getAllByText(/CLS ↔ LLM pretraining\/RAG/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Candidate review requiring DOI verification/)).toBeTruthy()
  })

  it('shows a title verification link when a pending paper has no DOI or URL', () => {
    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 17,
        title: 'Modern Hopfield Networks & Transformer Attention',
        doi: null,
        url: null,
        source_type: 'paper',
        topic_context: 'Formal attention = associative memory proof',
        status: 'pending',
        queued_at: '2026-06-02',
        reviewed_at: null,
        summary: null,
        abstract: null,
        year: 2020,
      }]),
    })

    fireEvent.click(screen.getByText('Review details'))

    const verifyLink = screen.getByRole('link', { name: 'Verify by title' })
    expect(verifyLink.getAttribute('href')).toContain('scholar.google.com/scholar?q=')
    expect(screen.getByText(/No DOI or URL is recorded yet/)).toBeTruthy()
    expect(screen.getByText('2020')).toBeTruthy()
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
