import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import SuggestionsPanel from './SuggestionsPanel'

function makeWrapper(data: unknown) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  qc.setQueryData(['suggestions'], data)
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('SuggestionsPanel', () => {
  it('shows empty state when no suggestions', () => {
    render(<SuggestionsPanel />, {
      wrapper: makeWrapper({ import_queue: [], source_suggestions: [] }),
    })
    expect(screen.getByText(/No pending import suggestions/)).toBeTruthy()
  })

  it('renders import queue items', () => {
    render(<SuggestionsPanel />, {
      wrapper: makeWrapper({
        import_queue: [{
          id: 1,
          source: 'openneuro',
          source_id: 'ds001',
          title: 'Test DS',
          status: 'pending',
          suggested_at: '2026-01-01',
          reason: null,
          chapter_ref: null,
        }],
        source_suggestions: [],
      }),
    })
    expect(screen.getByText(/Test DS/)).toBeTruthy()
  })
})
