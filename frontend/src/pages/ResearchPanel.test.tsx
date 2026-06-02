import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ResearchPanel from './ResearchPanel'
import { api } from '../api/client'

function makeWrapper(data: {
  hypotheses?: unknown[]
  reviews?: Record<number, unknown[]>
  metrics?: unknown
  questions?: unknown[]
  groupings?: unknown[]
} = {}) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  qc.setQueryData(['research-hypotheses'], data.hypotheses ?? [])
  for (const [hypothesisId, reviews] of Object.entries(data.reviews ?? {})) {
    qc.setQueryData(['hypothesis-reviews', Number(hypothesisId)], reviews)
  }
  qc.setQueryData(['research-metrics'], data.metrics ?? {
    approved_sources_count: 0,
    chat_sessions_count: 0,
    literature_searches_count: 0,
    research_hypotheses_count: 0,
    caveats: [],
  })
  qc.setQueryData(['research-questions-detail', undefined, []], data.questions ?? [])
  qc.setQueryData(['groupings-for-filter', 'topic'], data.groupings ?? [])
  qc.setQueryData(['groupings-all', 'topic'], data.groupings ?? [])
  qc.setQueryData(['research-claims'], [])
  qc.setQueryData(['research-gaps'], [])
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

  it('marks a proposed pending topic with a "new" badge', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
    qc.setQueryData(['research-hypotheses'], [])
    qc.setQueryData(['research-metrics'], {
      approved_sources_count: 0, chat_sessions_count: 0,
      literature_searches_count: 0, research_hypotheses_count: 0, caveats: [],
    })
    qc.setQueryData(['research-claims'], [])
    qc.setQueryData(['research-gaps'], [])
    qc.setQueryData(['groupings-for-filter', 'topic'], [])
    qc.setQueryData(['research-questions-detail', undefined, []], [
      {
        id: 1, question: 'Q?', status: 'open', topic_context: '', origin_session_id: null,
        created_at: '2026-06-01',
        topics: [{ topic_id: 9, topic_name: 'plasticity', status: 'pending', proposed: true }],
        concepts: [],
      },
    ])
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: qc }, children)
    render(<ResearchPanel />, { wrapper })
    expect(screen.getByText('plasticity')).toBeTruthy()
    expect(screen.getByText('new')).toBeTruthy()
  })

  it('renders topic filter buttons from the groupings endpoint', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
    qc.setQueryData(['research-hypotheses'], [])
    qc.setQueryData(['research-metrics'], {
      approved_sources_count: 0, chat_sessions_count: 0,
      literature_searches_count: 0, research_hypotheses_count: 0, caveats: [],
    })
    qc.setQueryData(['research-questions-detail', undefined, []], [])
    qc.setQueryData(['research-claims'], [])
    qc.setQueryData(['research-gaps'], [])
    qc.setQueryData(['groupings-for-filter', 'topic'], [
      { id: 7, type: 'topic', name: 'plasticity', parent_id: null, status: 'active', description: null },
    ])
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: qc }, children)
    render(<ResearchPanel />, { wrapper })
    expect(screen.getByRole('button', { name: 'plasticity' })).toBeTruthy()
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

  it('renders persisted review results under a hypothesis', () => {
    render(<ResearchPanel />, {
      wrapper: makeWrapper({
        hypotheses: [{
          id: 1,
          title: 'LTP Hypothesis',
          mechanism: null,
          status: 'draft',
          created_at: '2026-01-01',
        }],
        reviews: {
          1: [{
            id: 10,
            hypothesis_id: 1,
            model: 'test-model',
            critique_text: 'Needs stronger evidence.',
            unsupported_claims: ['Claim A'],
            missing_confounds: ['Age'],
            suggested_revisions: 'Narrow the claim.',
            status: 'pending',
            created_at: '2026-01-02',
          }],
        },
      }),
    })
    expect(screen.getByText('Hypothesis Reviews')).toBeTruthy()
    expect(screen.getByText('Needs stronger evidence.')).toBeTruthy()
    expect(screen.getByText('Claim A')).toBeTruthy()
    expect(screen.getByText('Age')).toBeTruthy()
    expect(screen.getByText('Narrow the claim.')).toBeTruthy()
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

  it('refreshes suggestions after creating a research question', async () => {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } },
    })
    qc.setQueryData(['research-hypotheses'], [])
    qc.setQueryData(['research-metrics'], {
      approved_sources_count: 0,
      chat_sessions_count: 0,
      literature_searches_count: 0,
      research_hypotheses_count: 0,
      caveats: [],
    })
    qc.setQueryData(['research-questions-detail', undefined, []], [])
    qc.setQueryData(['groupings-for-filter', 'topic'], [])
    qc.setQueryData(['groupings-all', 'topic'], [])
    qc.setQueryData(['research-claims'], [])
    qc.setQueryData(['research-gaps'], [])
    vi.spyOn(api, 'createQuestion').mockResolvedValue({
      id: 1,
      question: 'Does LTP predict recovery?',
      status: 'open',
      topic_context: null,
      origin_session_id: null,
      created_at: '2026-06-02',
      topics: [],
      concepts: [],
    })
    vi.spyOn(api, 'getResearchQuestionsDetail').mockResolvedValue([])
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: qc }, children)

    render(<ResearchPanel />, { wrapper })
    fireEvent.change(screen.getByPlaceholderText('Enter a research question…'), {
      target: { value: 'Does LTP predict recovery?' },
    })
    fireEvent.click(screen.getByText('Save Question'))

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['suggestions'] })
    })
  })
})

function makeFetchWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('ResearchPanel retract UI', () => {
  beforeEach(() => { vi.restoreAllMocks() })

  it('renders status chip on research question cards', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((path: string) => {
      if (typeof path === 'string' && path.includes('/api/research/questions')) {
        return Promise.resolve(new Response(JSON.stringify([
          { id: 1, question: 'Does LTP correlate with recovery?', status: 'open', topic_context: 'ctx', created_at: '2026-01-01T00:00:00', updated_at: '2026-01-01T00:00:00' }
        ]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }))
    render(<ResearchPanel />, { wrapper: makeFetchWrapper() })
    await waitFor(() => {
      expect(screen.getByText('Does LTP correlate with recovery?')).toBeTruthy()
    })
    // Status chip should be rendered (status 'open' shown as clickable chip)
    expect(screen.getAllByText(/open/).length).toBeGreaterThan(0)
  })

  it('renders the status chip and delete button alongside the research question text', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((path: string) => {
      if (typeof path === 'string' && path.includes('/api/research/questions')) {
        return Promise.resolve(new Response(JSON.stringify([
          { id: 1, question: 'Does LTP correlate with recovery?', status: 'open', topic_context: 'ctx', created_at: '2026-01-01T00:00:00', updated_at: '2026-01-01T00:00:00' }
        ]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }))
    render(<ResearchPanel />, { wrapper: makeFetchWrapper() })
    const question = await screen.findByText('Does LTP correlate with recovery?')
    // The outer question row contains both the question text and the status chip
    const row = question.closest('[style*="border"]')
    expect(row?.textContent).toContain('open')
    expect(row?.textContent).toContain('Delete')
  })

  it('collapses and expands research panel sections', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((path: string) => {
      if (typeof path === 'string' && path.includes('/api/research/questions')) {
        return Promise.resolve(new Response(JSON.stringify([
          { id: 1, question: 'Does LTP correlate with recovery?', status: 'open', topic_context: 'ctx', created_at: '2026-01-01T00:00:00', updated_at: '2026-01-01T00:00:00' }
        ]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }))
    render(<ResearchPanel />, { wrapper: makeFetchWrapper() })
    await screen.findByText('Does LTP correlate with recovery?')
    const sectionToggle = screen.getByRole('button', { name: /Research Questions/ })

    fireEvent.click(sectionToggle)
    expect(screen.queryByText('Does LTP correlate with recovery?')).toBeNull()

    fireEvent.click(sectionToggle)
    expect(await screen.findByText('Does LTP correlate with recovery?')).toBeTruthy()
  })

  it('collapses topic hierarchy separately from research questions', async () => {
    render(<ResearchPanel />, {
      wrapper: makeWrapper({
        questions: [
          {
            id: 1,
            question: 'Does LTP correlate with recovery?',
            status: 'open',
            topic_context: 'ctx',
            created_at: '2026-01-01T00:00:00',
            updated_at: '2026-01-01T00:00:00',
            topics: [],
            concepts: [],
          },
        ],
        groupings: [
          { id: 1, type: 'topic', name: 'plasticity', parent_id: null, status: 'active', description: null },
          { id: 2, type: 'topic', name: 'neuroplasticity', parent_id: 1, status: 'active', description: null },
        ],
      }),
    })

    expect(screen.getByLabelText('parent of plasticity')).toBeTruthy()
    expect(screen.getByText('Does LTP correlate with recovery?')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /Topic Hierarchy/ }))
    expect(screen.queryByLabelText('parent of plasticity')).toBeNull()
    expect(screen.getByText('Does LTP correlate with recovery?')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /Research Questions/ }))
    expect(screen.queryByText('Does LTP correlate with recovery?')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: /Topic Hierarchy/ }))
    expect(screen.getByLabelText('parent of plasticity')).toBeTruthy()
  })

  it('renders Claims section heading', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((path: string) => {
      if (typeof path === 'string' && path.includes('/api/research/claims')) {
        return Promise.resolve(new Response(JSON.stringify([
          { id: 1, paper_id: 1, text: 'Synaptic density decreases', claim_type: 'finding', status: 'candidate', created_at: '2026-01-01', updated_at: '2026-01-01' }
        ]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }))
    render(<ResearchPanel />, { wrapper: makeFetchWrapper() })
    await waitFor(() => {
      expect(screen.getByText(/Claims/)).toBeTruthy()
    })
  })

  it('explains claim status actions before the user selects them', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((path: string) => {
      if (typeof path === 'string' && path.includes('/api/research/claims')) {
        return Promise.resolve(new Response(JSON.stringify([
          { id: 1, paper_id: 1, text: 'Synaptic density decreases', claim_type: 'finding', status: 'candidate', created_at: '2026-01-01', updated_at: '2026-01-01' }
        ]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }))
    render(<ResearchPanel />, { wrapper: makeFetchWrapper() })
    await screen.findByText('Synaptic density decreases')

    fireEvent.click(screen.getByLabelText(/candidate: This item was proposed/))

    expect(screen.getByText('Accept this item as usable project evidence.')).toBeTruthy()
    expect(screen.getByText('Mark this item as not accepted so it should not support claims or hypotheses.')).toBeTruthy()
    expect(screen.getByText('Remove this item from the active workflow while keeping it in the audit trail.')).toBeTruthy()
  })

  it('renders Gaps section heading', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((path: string) => {
      if (typeof path === 'string' && path.includes('/api/research/gaps')) {
        return Promise.resolve(new Response(JSON.stringify([
          { id: 1, hypothesis_id: 1, question_id: null, description: 'Missing lesion data', gap_type: 'missing_data', status: 'open', created_at: '2026-01-01', updated_at: '2026-01-01' }
        ]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }))
    render(<ResearchPanel />, { wrapper: makeFetchWrapper() })
    await waitFor(() => {
      expect(screen.getByText(/Gaps/)).toBeTruthy()
    })
  })
})
