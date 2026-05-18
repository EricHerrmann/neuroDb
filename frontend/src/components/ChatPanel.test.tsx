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

function makeWrapperWithClient() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
  return { qc, wrapper }
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

  it('renders prior context banner when active context exists', async () => {
    const fetchMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/sessions/active-context') {
        return Promise.resolve(new Response(JSON.stringify({ active_prior_topic: 'LTP basics' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }))
      }
      return Promise.resolve(new Response('{}', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<ChatPanel agentMode="neuro_tutor" />, { wrapper: makeWrapper() })

    await waitFor(() => {
      expect(screen.getByText('Prior context: LTP basics')).toBeTruthy()
    })
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

  it('changing agent mode updates preferences cache immediately', async () => {
    const fetchMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/sessions/active-context') {
        return Promise.resolve(new Response(JSON.stringify({ active_prior_topic: null }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }))
      }
      return Promise.resolve(new Response(JSON.stringify({ agent_mode: 'external_db' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))
    })
    vi.stubGlobal('fetch', fetchMock)
    const { qc, wrapper } = makeWrapperWithClient()
    qc.setQueryData(['preferences'], {
      agent_mode: 'local_db',
      relevance_threshold: 0.75,
    })

    render(<ChatPanel agentMode="local_db" />, { wrapper })
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'external_db' } })

    await waitFor(() => {
      expect(qc.getQueryData(['preferences'])).toEqual({
        agent_mode: 'external_db',
        relevance_threshold: 0.75,
      })
    })
  })

  it('select is disabled while mode change is in flight', async () => {
    let resolveFetch!: (value: Response) => void
    const pendingFetch = new Promise<Response>(resolve => {
      resolveFetch = resolve
    })
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(pendingFetch))

    render(<ChatPanel agentMode="neuro_tutor" />, { wrapper: makeWrapper() })
    const select = screen.getByRole('combobox')

    fireEvent.change(select, { target: { value: 'local_db' } })

    await waitFor(() => {
      expect((select as HTMLSelectElement).disabled).toBe(true)
    })

    resolveFetch(new Response(JSON.stringify({ agent_mode: 'local_db' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }))
  })
})
