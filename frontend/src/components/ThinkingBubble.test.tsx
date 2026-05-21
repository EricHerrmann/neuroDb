import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import ThinkingBubble from './ThinkingBubble'

describe('ThinkingBubble', () => {
  it('renders thinking state', () => {
    render(<ThinkingBubble state="thinking" activeTool={null} />)

    expect(screen.getByRole('status')).toHaveTextContent('Thinking')
  })

  it('renders active tool state', () => {
    render(<ThinkingBubble state="tool" activeTool="query_db" />)

    expect(screen.getByRole('status')).toHaveTextContent('▸ query_db')
  })

  it('does not render while idle or streaming', () => {
    const { rerender } = render(<ThinkingBubble state="idle" activeTool={null} />)

    expect(screen.queryByRole('status')).toBeNull()

    rerender(<ThinkingBubble state="streaming" activeTool={null} />)
    expect(screen.queryByRole('status')).toBeNull()
  })
})
