import { useState, useCallback } from 'react'
import * as api from '@/services/api'

export function useAnalysisSubmit() {
  const [isSubmitting, setIsSubmitting] = useState(false)

  const submitAnalysis = useCallback(async (file: File, prompt: string): Promise<string> => {
    setIsSubmitting(true)
    try {
      const { analysis_id } = await api.processAudio(file, prompt)
      return analysis_id
    } catch (err) {
      // Propagate error to the caller
      throw err
    } finally {
      setIsSubmitting(false)
    }
  }, [])

  return { submitAnalysis, isSubmitting }
}
