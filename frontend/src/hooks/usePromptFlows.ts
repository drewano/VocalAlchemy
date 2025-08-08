import { useEffect, useState, useCallback } from 'react'
import { getPromptFlows } from '@/services/promptFlows.api'
import type { PromptFlow } from '@/types'

export function usePromptFlows() {
  const [flows, setFlows] = useState<PromptFlow[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const fetchFlows = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await getPromptFlows()
      setFlows(data)
    } catch (e) {
      setError(e as Error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchFlows()
  }, [fetchFlows])

  return { flows, isLoading, error, refresh: fetchFlows }
}


