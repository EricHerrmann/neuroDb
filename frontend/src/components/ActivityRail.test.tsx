import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'

import ActivityRail from './ActivityRail'

function makePanelRef(collapsed: boolean) {
  return {
    current: {
      isCollapsed: () => collapsed,
      expand: vi.fn(),
    },
  }
}

describe('ActivityRail', () => {
  it('renders 7 navigation links', () => {
    render(
      <MemoryRouter>
        <ActivityRail panelRef={makePanelRef(false)} />
      </MemoryRouter>,
    )
    expect(screen.getAllByRole('link')).toHaveLength(7)
  })

  it('suggestions link has aria-current=page at /suggestions route', () => {
    render(
      <MemoryRouter initialEntries={['/suggestions']}>
        <ActivityRail panelRef={makePanelRef(false)} />
      </MemoryRouter>,
    )
    expect(screen.getByTitle('Suggestions')).toHaveAttribute('aria-current', 'page')
  })

  it('clicking an icon while panel is collapsed calls expand', () => {
    const ref = makePanelRef(true)
    render(
      <MemoryRouter>
        <ActivityRail panelRef={ref} />
      </MemoryRouter>,
    )
    fireEvent.click(screen.getByTitle('Suggestions'))
    expect(ref.current.expand).toHaveBeenCalledOnce()
  })
})
