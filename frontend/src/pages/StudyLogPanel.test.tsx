import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { afterEach, describe, it, expect, vi } from 'vitest'

import StudyLogPanel from './StudyLogPanel'

function makeWrapper(studyLog: unknown = [], sessions: unknown = []) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  qc.setQueryData(['study-log'], studyLog)
  qc.setQueryData(['sessions'], sessions)
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('StudyLogPanel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders view dropdown with Study Tags selected by default', () => {
    render(<StudyLogPanel />, { wrapper: makeWrapper() })
    const select = screen.getByRole('combobox')
    expect((select as HTMLSelectElement).value).toBe('study-tags')
  })

  it('shows empty state in Study Tags view', () => {
    render(<StudyLogPanel />, { wrapper: makeWrapper([]) })
    expect(screen.getByText(/No study tags yet/)).toBeTruthy()
  })

  it('renders a study tag row', () => {
    const tag = {
      id: 1,
      source: 'pubmed',
      source_id: '123',
      concept_tag: 'LTP',
      section_ref: '3.1',
      note_text: null,
      tagged_at: '2026-01-15T00:00:00',
    }
    render(<StudyLogPanel />, { wrapper: makeWrapper([tag]) })
    expect(screen.getByText('LTP')).toBeTruthy()
    expect(screen.getByText('pubmed:123')).toBeTruthy()
  })

  it('switching to Chat History shows sessions', () => {
    const session = {
      id: 1,
      session_id: 'abc',
      inferred_topic: 'Synaptic plasticity',
      agent_mode: 'neuro_tutor',
      started_at: '2026-05-01T10:00:00',
      message_count: 5,
      summary_preview: 'Discussed LTP mechanisms',
    }
    render(<StudyLogPanel />, { wrapper: makeWrapper([], [session]) })
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'chat-history' } })
    expect(screen.getByText('Synaptic plasticity')).toBeTruthy()
    expect(screen.getByText('5 messages')).toBeTruthy()
    expect(screen.getByText('Session summary')).toBeTruthy()
    expect(screen.getByText('Discussed LTP mechanisms')).toBeTruthy()
  })

  it('hides session summary expander when no summary exists', () => {
    const session = {
      id: 1,
      session_id: 'abc',
      inferred_topic: 'Synaptic plasticity',
      agent_mode: 'neuro_tutor',
      started_at: '2026-05-01T10:00:00',
      message_count: 5,
      summary_preview: null,
    }
    render(<StudyLogPanel />, { wrapper: makeWrapper([], [session]) })
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'chat-history' } })
    expect(screen.queryByText('Session summary')).toBeNull()
  })

  it('shows empty state in Chat History view', () => {
    render(<StudyLogPanel />, { wrapper: makeWrapper([], []) })
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'chat-history' } })
    expect(screen.getByText(/No chat sessions yet/)).toBeTruthy()
  })

  it('shows Add Tag button in Study Tags view', () => {
    render(<StudyLogPanel />, { wrapper: makeWrapper([]) })
    expect(screen.getByText('Add Tag')).toBeTruthy()
  })

  it('shows inline error when submitting with empty concept_tag', () => {
    render(<StudyLogPanel />, { wrapper: makeWrapper([]) })
    fireEvent.click(screen.getByText('Add Tag'))
    fireEvent.change(screen.getByPlaceholderText('source_id'), { target: { value: 'ds001' } })
    fireEvent.click(screen.getByText('Save'))
    expect(screen.getByText('Concept tag is required')).toBeTruthy()
  })

  it('add-tag form submits POST /api/study-log', async () => {
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/study-log' && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            id: 1,
            source: 'openneuro',
            source_id: 'ds001',
            concept_tag: 'LTP',
            section_ref: null,
            note_text: null,
            tagged_at: '2026-01-01T00:00:00',
          }),
        })
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => [],
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<StudyLogPanel />, { wrapper: makeWrapper([]) })
    fireEvent.click(screen.getByText('Add Tag'))
    fireEvent.change(screen.getByPlaceholderText('source_id'), { target: { value: 'ds001' } })
    fireEvent.change(screen.getByPlaceholderText('concept_tag'), { target: { value: 'LTP' } })
    fireEvent.click(screen.getByText('Save'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/study-log',
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  it('shows warning banner when create returns a warning', async () => {
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/study-log' && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            id: 1,
            source: 'openneuro',
            source_id: 'ds001',
            concept_tag: 'LTP',
            section_ref: null,
            note_text: null,
            tagged_at: '2026-01-01T00:00:00',
            warnings: ['Vector embedding failed: chroma down'],
          }),
        })
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => [] })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<StudyLogPanel />, { wrapper: makeWrapper([]) })
    fireEvent.click(screen.getByText('Add Tag'))
    fireEvent.change(screen.getByPlaceholderText('source_id'), { target: { value: 'ds001' } })
    fireEvent.change(screen.getByPlaceholderText('concept_tag'), { target: { value: 'LTP' } })
    fireEvent.click(screen.getByText('Save'))

    await waitFor(() => {
      expect(screen.getByText(/Vector embedding failed/)).toBeTruthy()
    })
  })

  it('selecting a row pre-fills edit form', () => {
    const tag = {
      id: 12,
      source: 'openneuro',
      source_id: 'ds001',
      concept_tag: 'LTP',
      section_ref: '3.1',
      note_text: 'Existing note',
      tagged_at: '2026-01-15T00:00:00',
    }
    render(<StudyLogPanel />, { wrapper: makeWrapper([tag]) })

    fireEvent.click(screen.getByText('LTP'))

    expect(screen.getByText('Editing study tag #12')).toBeTruthy()
    expect((screen.getByPlaceholderText('source_id') as HTMLInputElement).value).toBe('ds001')
    expect((screen.getByPlaceholderText('concept_tag') as HTMLInputElement).value).toBe('LTP')
    expect((screen.getByPlaceholderText('section_ref (optional)') as HTMLInputElement).value).toBe('3.1')
    expect((screen.getByPlaceholderText('note (optional)') as HTMLTextAreaElement).value).toBe('Existing note')
  })

  it('edit form submits PATCH /api/study-log/{id}', async () => {
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/study-log/12' && init?.method === 'PATCH') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            id: 12,
            source: 'openneuro',
            source_id: 'ds001',
            concept_tag: 'LTD',
            section_ref: null,
            note_text: null,
            tagged_at: '2026-01-01T00:00:00',
            warnings: [],
          }),
        })
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => [] })
    })
    vi.stubGlobal('fetch', fetchMock)
    const tag = {
      id: 12,
      source: 'openneuro',
      source_id: 'ds001',
      concept_tag: 'LTP',
      section_ref: null,
      note_text: null,
      tagged_at: '2026-01-15T00:00:00',
    }
    render(<StudyLogPanel />, { wrapper: makeWrapper([tag]) })

    fireEvent.click(screen.getByText('LTP'))
    fireEvent.change(screen.getByPlaceholderText('concept_tag'), { target: { value: 'LTD' } })
    fireEvent.click(screen.getByText('Save Edit'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/study-log/12',
        expect.objectContaining({ method: 'PATCH' }),
      )
    })
  })
})
