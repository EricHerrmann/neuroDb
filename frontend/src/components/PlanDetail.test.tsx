import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import PlanDetail from './PlanDetail'
import type { PlanDetail as PlanDetailData } from '../api/types'

const handlers = {
  onStepProgress: vi.fn(),
  onStepLifecycle: vi.fn(),
  onConfirmChanges: vi.fn(),
  onDismissChanges: vi.fn(),
}

function makePlan(overrides: Partial<PlanDetailData> = {}): PlanDetailData {
  return {
    id: 1,
    title: 'Plasticity plan',
    origin_prompt: 'Learn plasticity',
    origin_agent: 'tutor',
    research_question_id: null,
    status: 'active',
    created_at: '2026-06-06T00:00:00Z',
    updated_at: '2026-06-06T00:00:00Z',
    percent_complete: 0,
    step_count: 2,
    pending_change_count: 0,
    groupings: [],
    steps: [
      {
        id: 10,
        plan_id: 1,
        order_index: 0,
        step_type: 'read',
        paper_id: 42,
        source_ref: null,
        source_title: 'LTP Review',
        source_type: 'paper',
        topic_context: 'plasticity',
        action_text: null,
        lifecycle: 'confirmed',
        progress: 'todo',
        note: null,
      },
      {
        id: 11,
        plan_id: 1,
        order_index: 1,
        step_type: 'action',
        paper_id: null,
        source_ref: null,
        source_title: null,
        source_type: null,
        topic_context: null,
        action_text: 'Write synthesis',
        lifecycle: 'confirmed',
        progress: 'todo',
        note: null,
      },
    ],
    ...overrides,
  }
}

describe('PlanDetail', () => {
  it('renders confirmed read-step source titles instead of paper ids', () => {
    render(<PlanDetail plan={makePlan()} {...handlers} />)

    expect(screen.getByText('Read: LTP Review')).toBeTruthy()
    expect(screen.queryByText('Read: source #42')).toBeNull()
  })
})
