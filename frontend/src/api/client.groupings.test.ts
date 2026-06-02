import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './client'

describe('groupings API client', () => {
  afterEach(() => vi.restoreAllMocks())

  it('listGroupings builds a type+status query', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    await api.listGroupings({ type: 'topic', status: 'active' })
    const url = String(fetchSpy.mock.calls[0][0])
    expect(url).toContain('/api/research/groupings?')
    expect(url).toContain('type=topic')
    expect(url).toContain('status=active')
  })

  it('patchGrouping issues PATCH with parent_id', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: 2, type: 'topic', name: 'np', parent_id: 1, status: 'active', description: null }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    const out = await api.patchGrouping(2, { parent_id: 1 })
    const [, init] = fetchSpy.mock.calls[0]
    expect((init as RequestInit).method).toBe('PATCH')
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ parent_id: 1 })
    expect(out.parent_id).toBe(1)
  })
})
