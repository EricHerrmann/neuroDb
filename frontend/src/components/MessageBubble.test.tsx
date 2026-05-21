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

  it('renders common rich markdown formatting', () => {
    render(
      <MessageBubble
        message={{
          role: 'assistant',
          content: '## Evidence\n\n**Local:** [Paper](https://example.test/paper) with `doi`.\n\n- first\n- second',
        }}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Evidence' })).toBeTruthy()
    expect(screen.getByText('Local:').tagName).toBe('STRONG')
    expect(screen.getByRole('link', { name: 'Paper' })).toHaveAttribute(
      'href',
      'https://example.test/paper',
    )
    expect(screen.getByText('doi').tagName).toBe('CODE')
    expect(screen.getByText('first').tagName).toBe('LI')
  })

  it('blocks unsafe markdown link protocols', () => {
    render(
      <MessageBubble
        message={{
          role: 'assistant',
          content: '[Unsafe](javascript:alert(1))',
        }}
      />,
    )

    expect(screen.getByRole('link', { name: 'Unsafe' })).toHaveAttribute('href', '#')
  })

  it('renders incomplete streamed headings as plain text instead of hanging', () => {
    render(
      <MessageBubble
        message={{
          role: 'assistant',
          content: 'Intro\n\n---\n\n## ',
          streaming: true,
        }}
      />,
    )

    expect(screen.getByText('Intro')).toBeTruthy()
    expect(screen.getByText('---')).toBeTruthy()
    expect(screen.getByText('##')).toBeTruthy()
  })

  it('renders standalone partial markdown constructs without hanging', () => {
    const partials = ['# ', '## ', '### ', '#### ', '```', '| Topic |\n|---']

    for (const partial of partials) {
      const { unmount } = render(
        <MessageBubble
          message={{
            role: 'assistant',
            content: partial,
            streaming: true,
          }}
        />,
      )

      expect(document.body.textContent).toBeTruthy()
      unmount()
    }
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
