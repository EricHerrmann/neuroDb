import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import GroupingHierarchy from './GroupingHierarchy'
import { api } from '../api/client'

function wrapperWith(groupings: unknown[]) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  qc.setQueryData(['groupings-all', 'topic'], groupings)
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

const PARENT = { id: 1, type: 'topic', name: 'plasticity', parent_id: null, status: 'active', description: null }
const CHILD = { id: 2, type: 'topic', name: 'neuroplasticity', parent_id: 1, status: 'active', description: null }
const LOOSE = { id: 3, type: 'topic', name: 'stroke', parent_id: null, status: 'active', description: null }
const LOOSE_CHILD = { id: 4, type: 'topic', name: 'rehab', parent_id: 3, status: 'active', description: null }

describe('GroupingHierarchy', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renders top-level groupings with nested children', () => {
    render(<GroupingHierarchy type="topic" />, { wrapper: wrapperWith([PARENT, CHILD, LOOSE]) })
    // A row exists per grouping (unique aria-labelled parent selects).
    expect(screen.getByLabelText('parent of plasticity')).toBeTruthy()
    expect(screen.getByLabelText('parent of neuroplasticity')).toBeTruthy()
    expect(screen.getByLabelText('parent of stroke')).toBeTruthy()
    // The child is nested under its parent: its row's select value is the parent id.
    expect((screen.getByLabelText('parent of neuroplasticity') as HTMLSelectElement).value).toBe('1')
  })

  it('re-parents a grouping via patchGrouping', async () => {
    const spy = vi.spyOn(api, 'patchGrouping').mockResolvedValue(
      { ...CHILD, parent_id: 3 } as never,
    )
    render(<GroupingHierarchy type="topic" />, { wrapper: wrapperWith([PARENT, LOOSE,
      { ...CHILD, parent_id: null }]) })
    const select = screen.getByLabelText('parent of neuroplasticity')
    fireEvent.change(select, { target: { value: '3' } })
    await waitFor(() => expect(spy).toHaveBeenCalledWith(2, { parent_id: 3 }))
  })

  it('shows an inline error when re-parent is rejected (422)', async () => {
    vi.spyOn(api, 'patchGrouping').mockRejectedValue(new Error('Parent must be top-level'))
    render(<GroupingHierarchy type="topic" />, { wrapper: wrapperWith([PARENT, LOOSE,
      { ...CHILD, parent_id: null }]) })
    const select = screen.getByLabelText('parent of neuroplasticity')
    fireEvent.change(select, { target: { value: '3' } })
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Parent must be top-level'))
  })

  it('collapses each top-level grouping independently', () => {
    render(<GroupingHierarchy type="topic" />, { wrapper: wrapperWith([PARENT, CHILD, LOOSE, LOOSE_CHILD]) })

    fireEvent.click(screen.getByRole('button', { name: 'Collapse plasticity' }))
    expect(screen.queryByLabelText('parent of neuroplasticity')).toBeNull()
    expect(screen.getByLabelText('parent of rehab')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Collapse stroke' }))
    expect(screen.queryByLabelText('parent of rehab')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Expand plasticity' }))
    expect(screen.getByLabelText('parent of neuroplasticity')).toBeTruthy()
    expect(screen.queryByLabelText('parent of rehab')).toBeNull()
  })
})
