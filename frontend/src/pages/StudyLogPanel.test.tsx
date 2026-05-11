import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

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
    expect(screen.getByText('Discussed LTP mechanisms')).toBeTruthy()
  })

  it('shows empty state in Chat History view', () => {
    render(<StudyLogPanel />, { wrapper: makeWrapper([], []) })
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'chat-history' } })
    expect(screen.getByText(/No chat sessions yet/)).toBeTruthy()
  })
})
