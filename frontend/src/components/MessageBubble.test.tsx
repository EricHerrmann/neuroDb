import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import MessageBubble from './MessageBubble'

describe('MessageBubble', () => {
  it('renders markdown tables as tables', () => {
    render(
      <MessageBubble
        message={{
          role: 'assistant',
          content: '| Field | Value |\n|---|---|\n| DOI | 10.1/test |',
        }}
      />,
    )

    expect(screen.getByRole('table')).toBeTruthy()
    expect(screen.getByText('DOI')).toBeTruthy()
    expect(screen.getByText('10.1/test')).toBeTruthy()
  })

  it('renders tool activity separately from answer text', () => {
    render(
      <MessageBubble
        message={{
          role: 'assistant',
          content: 'Answer text',
          activity: [{
            id: 'tool-1',
            toolName: 'query_db',
            input: { sql: 'SELECT 1' },
            result: '[{"x": 1}]',
            status: 'done',
          }],
        }}
      />,
    )

    expect(screen.getByText('Answer text')).toBeTruthy()
    expect(screen.getByText('1 tool call(s)')).toBeTruthy()
  })
})
