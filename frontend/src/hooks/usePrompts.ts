import { useEffect, useState } from 'react'
import * as api from '@/services/api'
import type { PredefinedPrompts } from '@/types'

export function usePrompts() {
  const [prompts, setPrompts] = useState<PredefinedPrompts>({})
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api.getPrompts()
        setPrompts(data)
      } catch (e: any) {
        // Harmonise with api error shape if needed; keep Error type per spec
        const err = e instanceof Error ? e : new Error(e?.message || 'Failed to load prompts')
        setError(err)
        console.error('Erreur chargement des prompts', e)
      } finally {
        setIsLoading(false)
      }
    }
    load()
  }, [])

  return { prompts, isLoading, error }
}
