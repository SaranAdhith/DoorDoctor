import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError } from '../api/client'

interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

/**
 * Runs an async loader and exposes loading / error / data states so every page
 * handles those three cases the same way.
 */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, error: null })
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const run = useCallback(
    async (options: { quiet?: boolean } = {}) => {
      if (!options.quiet) setState((current) => ({ ...current, loading: true, error: null }))
      try {
        const data = await loader()
        if (mounted.current) setState({ data, loading: false, error: null })
        return data
      } catch (error) {
        const message =
          error instanceof ApiError ? error.message : 'Something went wrong. Please try again.'
        if (mounted.current) setState((current) => ({ ...current, loading: false, error: message }))
        return null
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    deps,
  )

  useEffect(() => {
    void run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { ...state, reload: run, setData: (data: T) => setState({ data, loading: false, error: null }) }
}
