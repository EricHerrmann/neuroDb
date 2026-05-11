import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import TaskStatus from './TaskStatus'

describe('TaskStatus', () => {
  it('renders nothing when idle', () => {
    const { container } = render(
      <TaskStatus status="idle" error={null} successMessage="Done" />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('shows Running text when running', () => {
    render(<TaskStatus status="running" error={null} successMessage="Done" />)
    expect(screen.getByText('Running...')).toBeTruthy()
  })

  it('shows successMessage when done', () => {
    render(<TaskStatus status="done" error={null} successMessage="Import complete" />)
    expect(screen.getByText('Import complete')).toBeTruthy()
  })

  it('shows error text when failed with error', () => {
    render(<TaskStatus status="failed" error="Something broke" successMessage="Done" />)
    expect(screen.getByText('Something broke')).toBeTruthy()
  })

  it('shows fallback text when failed with null error', () => {
    render(<TaskStatus status="failed" error={null} successMessage="Done" />)
    expect(screen.getByText('Failed')).toBeTruthy()
  })
})
