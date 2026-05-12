import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import RegistryPanel from './RegistryPanel'

function makeWrapper(data: unknown = []) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  qc.setQueryData(['registry'], data)
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('RegistryPanel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders source groups with items', () => {
    render(<RegistryPanel />, {
      wrapper: makeWrapper([
        { id: 1, source_type: 'paper', source_key: 'doi:test', display_name: 'LTP Paper', added_by: 'user', added_at: '2026-01-01T00:00:00' },
        { id: 2, source_type: 'book', source_key: 'isbn:test', display_name: 'Neuro Text', added_by: 'user', added_at: '2026-01-01T00:00:00' },
      ]),
    })
    expect(screen.getByText('LTP Paper')).toBeTruthy()
    expect(screen.getByText('Neuro Text')).toBeTruthy()
  })

  it('renders Remove buttons per item', () => {
    render(<RegistryPanel />, {
      wrapper: makeWrapper([
        { id: 1, source_type: 'paper', source_key: 'doi:test', display_name: 'LTP Paper', added_by: 'user', added_at: '2026-01-01T00:00:00' },
      ]),
    })
    expect(screen.getByText('Remove')).toBeTruthy()
  })

  it('remove fires DELETE /api/registry/{id}', async () => {
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/registry/1' && init?.method === 'DELETE') {
        return Promise.resolve({
          ok: true, status: 204,
          text: async () => '', json: async () => undefined,
        })
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => [] })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<RegistryPanel />, {
      wrapper: makeWrapper([
        { id: 1, source_type: 'paper', source_key: 'doi:test', display_name: 'LTP Paper', added_by: 'user', added_at: '2026-01-01T00:00:00' },
      ]),
    })
    fireEvent.click(screen.getByText('Remove'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/registry/1',
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
  })

  it('shows Add Source button', () => {
    render(<RegistryPanel />, { wrapper: makeWrapper([]) })
    expect(screen.getByText('Add Source')).toBeTruthy()
  })

  it('add-source form has topics field and no added_by field', () => {
    render(<RegistryPanel />, { wrapper: makeWrapper([]) })
    fireEvent.click(screen.getByText('Add Source'))
    expect(screen.getByPlaceholderText(/topics/i)).toBeTruthy()
    expect(screen.queryByPlaceholderText('added by')).toBeNull()
  })

  it('add-source form submits POST /api/registry with topics', async () => {
    const newItem = {
      id: 99, source_type: 'paper', source_key: 'doi:new',
      display_name: 'New Paper', added_by: 'user', added_at: '2026-01-01T00:00:00',
    }
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/registry' && init?.method === 'POST') {
        return Promise.resolve({ ok: true, status: 200, json: async () => newItem })
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => [] })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<RegistryPanel />, { wrapper: makeWrapper([]) })
    fireEvent.click(screen.getByText('Add Source'))
    fireEvent.change(screen.getByPlaceholderText('source key'), { target: { value: 'doi:new' } })
    fireEvent.change(screen.getByPlaceholderText('display name'), { target: { value: 'New Paper' } })
    fireEvent.change(screen.getByPlaceholderText(/topics/i), {
      target: { value: 'LTP, plasticity' },
    })
    fireEvent.click(screen.getByText('Save'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/registry',
        expect.objectContaining({ method: 'POST' }),
      )
      const postCall = fetchMock.mock.calls.find(
        (args) => args[0] === '/api/registry' && (args[1] as RequestInit)?.method === 'POST'
      )
      const body = JSON.parse((postCall![1] as RequestInit).body as string)
      expect(body.topics).toEqual(['LTP', 'plasticity'])
      expect(body.added_by).toBeUndefined()
    })
  })
})
