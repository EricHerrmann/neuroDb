import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import DatasetsPanel from './DatasetsPanel'

function makeWrapper(data: unknown = []) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  qc.setQueryData(['datasets', undefined, 'all'], data)
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('DatasetsPanel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders dataset metadata and tag action', () => {
    render(<DatasetsPanel />, {
      wrapper: makeWrapper([{
        id: 1,
        source: 'openneuro',
        source_id: 'ds001',
        title: 'Plasticity Dataset',
        modality: 'fMRI',
        n_subjects: 12,
      }]),
    })

    expect(screen.getByText('Plasticity Dataset')).toBeTruthy()
    expect(screen.getAllByText('fMRI').length).toBeGreaterThan(0)
    expect(screen.getByText('12 subjects')).toBeTruthy()
    expect(screen.getByText('Tag')).toBeTruthy()
  })

  it('inline tag submits study-log create request', async () => {
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/study-log' && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            id: 99,
            source: 'openneuro',
            source_id: 'ds001',
            concept_tag: 'LTP',
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

    render(<DatasetsPanel />, {
      wrapper: makeWrapper([{
        id: 1,
        source: 'openneuro',
        source_id: 'ds001',
        title: 'Plasticity Dataset',
        modality: 'fMRI',
        n_subjects: 12,
      }]),
    })

    fireEvent.click(screen.getByText('Tag'))
    fireEvent.change(screen.getByPlaceholderText('concept_tag'), { target: { value: 'LTP' } })
    fireEvent.click(screen.getByText('Save'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/study-log',
        expect.objectContaining({ method: 'POST' }),
      )
      const postCall = fetchMock.mock.calls.find(
        args => args[0] === '/api/study-log' && (args[1] as RequestInit)?.method === 'POST',
      )
      const body = JSON.parse((postCall![1] as RequestInit).body as string)
      expect(body).toEqual({
        source: 'openneuro',
        source_id: 'ds001',
        concept_tag: 'LTP',
      })
    })
  })
})

function makeFetchWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('DatasetsPanel usefulness badge', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    Element.prototype.scrollIntoView = vi.fn()
  })

  it('shows sparse label for sparse dataset', async () => {
    const mockDataset = {
      id: 1, source: 'openneuro', source_id: 'ds001',
      title: 'Stroke fMRI', modality: 'fMRI', n_subjects: 42,
      usefulness_state: 'sparse', missing_context: 'no linked paper',
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify([mockDataset]), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ))
    render(<DatasetsPanel />, { wrapper: makeFetchWrapper() })
    const searchBtn = await screen.findByRole('button', { name: /Search/i })
    searchBtn.click()
    await waitFor(() => {
      expect(screen.getByText(/sparse/)).toBeTruthy()
      expect(screen.getByText(/no linked paper/)).toBeTruthy()
    })
  })

  it('shows no badge for dataset without usefulness_state', async () => {
    const mockDataset = {
      id: 2, source: 'openneuro', source_id: 'ds002',
      title: 'Motor fMRI', modality: 'fMRI', n_subjects: 10,
      usefulness_state: null, missing_context: null,
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify([mockDataset]), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ))
    render(<DatasetsPanel />, { wrapper: makeFetchWrapper() })
    const searchBtn = await screen.findByRole('button', { name: /Search/i })
    searchBtn.click()
    await waitFor(() => {
      expect(screen.queryByText(/sparse/)).toBeNull()
      expect(screen.queryByText(/partial/)).toBeNull()
    })
  })
})
