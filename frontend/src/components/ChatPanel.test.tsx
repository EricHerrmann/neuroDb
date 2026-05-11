import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import ChatPanel from './ChatPanel'

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('ChatPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response('{}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    // Mock scrollIntoView for JSDOM
    Element.prototype.scrollIntoView = vi.fn()
  })

  it('renders agent mode select with current mode selected', () => {
    render(<ChatPanel agentMode="neuro_tutor" />, { wrapper: makeWrapper() })
    const select = screen.getByRole('combobox')
    expect((select as HTMLSelectElement).value).toBe('neuro_tutor')
  })

  it('changing agent mode fires PUT /api/preferences/agent-mode', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ agent_mode: 'local_db' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<ChatPanel agentMode="neuro_tutor" />, { wrapper: makeWrapper() })
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'local_db' } })

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/preferences/agent-mode',
        expect.objectContaining({ method: 'PUT' }),
      )
    })
  })
})
