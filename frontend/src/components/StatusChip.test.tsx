import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import StatusChip from './StatusChip'

describe('StatusChip', () => {
  it('renders current status', () => {
    render(
      <StatusChip
        status="candidate"
        transitions={[{ label: 'Approve', onSelect: vi.fn() }]}
      />
    )
    expect(screen.getByText(/candidate/)).toBeTruthy()
  })

  it('opens dropdown on click', () => {
    render(
      <StatusChip
        status="candidate"
        transitions={[
          { label: 'Approve', onSelect: vi.fn() },
          { label: 'Reject', onSelect: vi.fn() },
        ]}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /candidate/ }))
    expect(screen.getByText('Approve')).toBeTruthy()
    expect(screen.getByText('Reject')).toBeTruthy()
  })

  it('shows action impact descriptions in the dropdown', () => {
    render(
      <StatusChip
        status="candidate"
        transitions={[
          { label: 'Approve', description: 'Accept this item as usable project evidence.', onSelect: vi.fn() },
        ]}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /candidate/ }))
    expect(screen.getByText('Accept this item as usable project evidence.')).toBeTruthy()
  })

  it('shows a tooltip for the current status', () => {
    render(
      <StatusChip
        status="candidate"
        statusDescription="This item needs review before it is trusted."
        transitions={[{ label: 'Approve', onSelect: vi.fn() }]}
      />
    )
    fireEvent.mouseEnter(screen.getByRole('button', { name: /candidate/ }))
    expect(screen.getByRole('tooltip')).toHaveTextContent('This item needs review before it is trusted.')
  })

  it('calls onSelect and closes dropdown when transition clicked', () => {
    const onApprove = vi.fn()
    render(
      <StatusChip
        status="candidate"
        transitions={[{ label: 'Approve', onSelect: onApprove }]}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /candidate/ }))
    fireEvent.click(screen.getByText('Approve'))
    expect(onApprove).toHaveBeenCalledOnce()
    expect(screen.queryByText('Approve')).toBeNull()
  })

  it('shows disabled state when isPending', () => {
    render(
      <StatusChip
        status="candidate"
        transitions={[{ label: 'Approve', onSelect: vi.fn() }]}
        isPending={true}
      />
    )
    const chip = screen.getByRole('button', { name: /candidate/ }) as HTMLButtonElement
    expect(chip.disabled).toBe(true)
  })

  it('applies green color for approved status', () => {
    render(
      <StatusChip status="approved" transitions={[]} />
    )
    // approved renders as a span (no transitions), so query by text
    const el = screen.getByText('approved')
    // Browser converts hex #14532d to rgb(20, 83, 45)
    expect(el.style.background).toContain('rgb(20, 83, 45)')
  })
})
