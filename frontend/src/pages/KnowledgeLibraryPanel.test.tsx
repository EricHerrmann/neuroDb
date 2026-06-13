import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, it, expect, vi } from 'vitest'

import KnowledgeLibraryPanel from './KnowledgeLibraryPanel'

function makeWrapper(data: unknown, libraryFiles: unknown = []) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  qc.setQueryData(['knowledge-library', 'all'], data)
  qc.setQueryData(['library-files'], libraryFiles)
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

  it('renders topic grouping link indicators for pending papers', () => {
    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 1,
        title: 'Linked Paper',
        doi: null,
        url: null,
        source_type: 'paper',
        topic_context: 'stroke',
        status: 'pending',
        queued_at: '2026-01-01',
        reviewed_at: null,
        summary: null,
        grouping_links: [{
          grouping_id: 7,
          grouping_type: 'topic',
          grouping_name: 'stroke recovery',
          status: 'confirmed',
        }],
      }]),
    })

    expect(screen.getByText('topic: stroke recovery')).toBeTruthy()
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

  it('renders tier badge from data_tier', () => {
    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 1,
        title: 'Full Text Paper',
        doi: null,
        url: null,
        source_type: 'paper',
        topic_context: 'plasticity',
        status: 'approved',
        queued_at: '2026-01-01',
        reviewed_at: '2026-01-02',
        summary: null,
        data_tier: 'full_text',
      }]),
    })
    expect(screen.getByTitle('Data tier: full_text')).toBeTruthy()
    expect(screen.getByText('full text')).toBeTruthy()
  })

  it('renders metadata tier badge for papers without data_tier', () => {
    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 2,
        title: 'Metadata Paper',
        doi: null,
        url: null,
        source_type: 'paper',
        topic_context: 'plasticity',
        status: 'approved',
        queued_at: '2026-01-01',
        reviewed_at: '2026-01-02',
        summary: null,
      }]),
    })
    expect(screen.getByTitle('Data tier: metadata')).toBeTruthy()
    expect(screen.getByText('metadata')).toBeTruthy()
  })

  it('shows Acquire full text button for approved papers', () => {
    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 3,
        title: 'Approved Paper',
        doi: null,
        url: null,
        source_type: 'paper',
        topic_context: 'memory',
        status: 'approved',
        queued_at: '2026-01-01',
        reviewed_at: '2026-01-02',
        summary: null,
        data_tier: 'metadata',
      }]),
    })
    expect(screen.getByText('Acquire full text')).toBeTruthy()
  })

  it('POSTs to acquire-full-text endpoint and refreshes on button click', async () => {
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path.includes('/acquire-full-text') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            id: 4,
            title: 'Acquired Paper',
            doi: null,
            url: null,
            source_type: 'paper',
            topic_context: 'memory',
            status: 'approved',
            queued_at: '2026-01-01',
            reviewed_at: '2026-01-02',
            summary: null,
            data_tier: 'full_text',
            full_text_status: 'verified',
          }),
        })
      }
      // Refresh query
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => [],
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 4,
        title: 'Acquired Paper',
        doi: null,
        url: null,
        source_type: 'paper',
        topic_context: 'memory',
        status: 'approved',
        queued_at: '2026-01-01',
        reviewed_at: '2026-01-02',
        summary: null,
        data_tier: 'metadata',
      }]),
    })

    fireEvent.click(screen.getByText('Acquire full text'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/acquire-full-text'),
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  it('shows deferral reason when acquire returns unavailable with a warning', async () => {
    const updatedItem = {
      id: 5,
      title: 'No PDF Paper',
      doi: null,
      url: null,
      source_type: 'paper',
      topic_context: 'memory',
      status: 'approved',
      queued_at: '2026-01-01',
      reviewed_at: '2026-01-02',
      summary: null,
      data_tier: 'metadata',
      full_text_status: 'unavailable',
      warnings: [],
    }
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path.includes('/acquire-full-text') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            ...updatedItem,
            warnings: ['No public PDF found; deferred for manual upload.'],
          }),
        })
      }
      // Refresh query returns the updated item (warnings not persisted, but full_text_status is)
      return Promise.resolve({ ok: true, status: 200, json: async () => [updatedItem] })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 5,
        title: 'No PDF Paper',
        doi: null,
        url: null,
        source_type: 'paper',
        topic_context: 'memory',
        status: 'approved',
        queued_at: '2026-01-01',
        reviewed_at: '2026-01-02',
        summary: null,
        data_tier: 'metadata',
      }]),
    })

    fireEvent.click(screen.getByText('Acquire full text'))

    await waitFor(() => {
      expect(screen.getByText(/No public PDF found; deferred for manual upload/)).toBeTruthy()
    })
  })

  it('verified item shows Re-acquire and does NOT show plain Acquire full text', () => {
    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 10,
        title: 'Verified Paper',
        doi: null,
        url: null,
        source_type: 'paper',
        topic_context: 'plasticity',
        status: 'approved',
        queued_at: '2026-01-01',
        reviewed_at: '2026-01-02',
        summary: null,
        data_tier: 'full_text',
        full_text_status: 'verified',
      }]),
    })
    expect(screen.getByText('Re-acquire')).toBeTruthy()
    expect(screen.queryByText('Acquire full text')).toBeNull()
  })

  it('needs_review item shows Review parse button', () => {
    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 11,
        title: 'Staged Paper',
        doi: null,
        url: null,
        source_type: 'paper',
        topic_context: 'plasticity',
        status: 'approved',
        queued_at: '2026-01-01',
        reviewed_at: '2026-01-02',
        summary: null,
        data_tier: 'full_text',
        full_text_status: 'needs_review',
        parse_confidence: 0.85,
        fulltext_staging: {
          source_id: 'src-1',
          text_source: 'pdf',
          parse_confidence: 0.85,
          fetched_url: 'https://example.com/paper.pdf',
          sections: [{ label: 'Abstract', text: 'Some text', char_start: 0, char_end: 9, page: 1 }],
        },
      }]),
    })
    expect(screen.getByText('Review parse')).toBeTruthy()
  })

  it('unavailable item offers supply-link affordance', () => {
    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 12,
        title: 'Unavailable Paper',
        doi: null,
        url: null,
        source_type: 'paper',
        topic_context: 'plasticity',
        status: 'approved',
        queued_at: '2026-01-01',
        reviewed_at: '2026-01-02',
        summary: null,
        data_tier: 'metadata',
        full_text_status: 'unavailable',
      }]),
    })
    // Should show a link/URL input affordance for recovery
    expect(screen.getByPlaceholderText(/PDF or HTML URL/i)).toBeTruthy()
  })

  it('lists library files in the supply-link dropdown for an unavailable paper', () => {
    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper(
        [{
          id: 20,
          title: 'File Picker Paper',
          doi: null,
          url: null,
          source_type: 'paper',
          topic_context: 'plasticity',
          status: 'approved',
          queued_at: '2026-01-01',
          reviewed_at: '2026-01-02',
          summary: null,
          data_tier: 'metadata',
          full_text_status: 'unavailable',
        }],
        [
          { name: 'paper-a.pdf', size: 12345, modified: 1700000000 },
          { name: 'paper-b.pdf', size: 67890, modified: 1700001000 },
        ],
      ),
    })

    // Dropdown should be present and list both files
    const select = screen.getByRole('combobox', { name: /pick library file/i })
    expect(select).toBeTruthy()
    expect(screen.getByRole('option', { name: 'paper-a.pdf' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'paper-b.pdf' })).toBeTruthy()
  })

  it('calls acquire with source_path when a library file is selected and acquire is clicked', async () => {
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path.includes('/acquire-full-text') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            id: 21,
            title: 'Path Paper',
            doi: null,
            url: null,
            source_type: 'paper',
            topic_context: 'memory',
            status: 'approved',
            queued_at: '2026-01-01',
            reviewed_at: '2026-01-02',
            summary: null,
            data_tier: 'full_text',
            full_text_status: 'verified',
          }),
        })
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => [] })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper(
        [{
          id: 21,
          title: 'Path Paper',
          doi: null,
          url: null,
          source_type: 'paper',
          topic_context: 'memory',
          status: 'approved',
          queued_at: '2026-01-01',
          reviewed_at: '2026-01-02',
          summary: null,
          data_tier: 'metadata',
          full_text_status: 'unavailable',
        }],
        [{ name: 'chosen.pdf', size: 1000, modified: 1700000000 }],
      ),
    })

    // Select the library file from the dropdown
    const select = screen.getByRole('combobox', { name: /pick library file/i })
    fireEvent.change(select, { target: { value: 'chosen.pdf' } })

    // Click the acquire button
    fireEvent.click(screen.getByText(/Supply link \/ upload PDF/i))

    await waitFor(() => {
      const acquireCalls = fetchMock.mock.calls.filter(
        (args: unknown[]) =>
          (args[0] as string).includes('/acquire-full-text') &&
          (args[1] as RequestInit)?.method === 'POST',
      )
      expect(acquireCalls.length).toBeGreaterThan(0)
      const body = JSON.parse((acquireCalls[0][1] as RequestInit).body as string)
      expect(body).toEqual({ source_path: 'chosen.pdf' })
    })
  })

  it('shows empty-library hint when listLibraryFiles returns empty array', () => {
    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper(
        [{
          id: 22,
          title: 'Empty Library Paper',
          doi: null,
          url: null,
          source_type: 'paper',
          topic_context: 'plasticity',
          status: 'approved',
          queued_at: '2026-01-01',
          reviewed_at: '2026-01-02',
          summary: null,
          data_tier: 'metadata',
          full_text_status: 'unavailable',
        }],
        [],
      ),
    })

    expect(screen.getByText(/No files in library — drop a file in knowledge_library_files\//)).toBeTruthy()
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
