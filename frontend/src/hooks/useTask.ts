import { useEffect, useRef, useState } from 'react'

export interface TaskState {
  status: 'idle' | 'running' | 'done' | 'failed'
  result: unknown
  error: string | null
}

interface TaskPollResponse {
  status: 'running' | 'done' | 'failed'
  result: unknown
  error: string | null
}

export function useTask(
  taskId: string | null,
  timeoutMs: number,
  onSuccess?: (result: unknown) => void,
): TaskState {
  const [state, setState] = useState<TaskState>({ status: 'idle', result: null, error: null })
  const startedAtRef = useRef<number | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const onSuccessRef = useRef<typeof onSuccess>(onSuccess)

  useEffect(() => {
    onSuccessRef.current = onSuccess
  }, [onSuccess])

  useEffect(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }

    if (!taskId) {
      startedAtRef.current = null
      setState({ status: 'idle', result: null, error: null })
      return
    }

    startedAtRef.current = Date.now()
    setState({ status: 'running', result: null, error: null })

    const stop = () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }

    const poll = async () => {
      if (startedAtRef.current !== null && Date.now() - startedAtRef.current > timeoutMs) {
        stop()
        setState({ status: 'failed', result: null, error: 'Timed out' })
        return
      }

      try {
        const res = await fetch(`/api/tasks/${taskId}`)
        if (!res.ok) return
        const data = await res.json() as TaskPollResponse
        if (data.status === 'done') {
          stop()
          setState({ status: 'done', result: data.result, error: null })
          onSuccessRef.current?.(data.result)
        } else if (data.status === 'failed') {
          stop()
          setState({ status: 'failed', result: null, error: data.error ?? 'Unknown error' })
        }
      } catch {
        // Transient network failures keep polling until server or client timeout.
      }
    }

    void poll()
    intervalRef.current = setInterval(() => void poll(), 2000)

    return stop
  }, [taskId, timeoutMs])

  return state
}
