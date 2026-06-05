import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, fireEvent } from '@testing-library/react'
import { afterEach, describe, it, expect, vi } from 'vitest'

import StudyLogPanel from './StudyLogPanel'

function makeWrapper(plans: unknown = []) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  qc.setQueryData(['study-log'], [])
  qc.setQueryData(['sessions'], [])
  qc.setQueryData(['plans'], plans)
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('StudyLogPanel — Plans section', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders a proposed plan card with title and status', () => {
    const plan = {
      id: 1,
      title: 'Plasticity primer',
      status: 'proposed',
      origin_agent: 'tutor',
      percent_complete: 0,
      step_count: 0,
      pending_change_count: 0,
    }
    render(<StudyLogPanel />, { wrapper: makeWrapper([plan]) })
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'plans' } })
    expect(screen.getByText('Plasticity primer')).toBeTruthy()
    expect(screen.getByText(/proposed/i)).toBeTruthy()
  })
})
