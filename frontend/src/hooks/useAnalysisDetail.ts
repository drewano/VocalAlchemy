import { useCallback, useEffect, useState } from 'react'
import * as api from '@/services/api'
import type { AnalysisDetail, AnalysisVersion } from '@/types'

export function useAnalysisDetail(analysisId?: string) {
  const [analysisData, setAnalysisData] = useState<AnalysisDetail | null>(null)
  const [currentPrompt, setCurrentPrompt] = useState<string>('')
  const [currentAnalysis, setCurrentAnalysis] = useState<string>('')
  const [currentPeople, setCurrentPeople] = useState<string>('')
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [isRerunning, setIsRerunning] = useState<boolean>(false)
  const [error, setError] = useState<{ message: string; status: number } | null>(null)

  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout> | null = null

    const pollStatus = async () => {
      if (!analysisId) return
      try {
        const st = await api.getTaskStatus(analysisId)
        if (st.status === 'COMPLETED' || st.status === 'FAILED') {
          // Final state reached, refresh full detail on COMPLETED and stop polling
          if (st.status === 'COMPLETED') {
            const fresh = await api.getAnalysisDetail(analysisId)
            setAnalysisData(fresh)
            setCurrentPrompt(fresh.prompt || '')
            setCurrentAnalysis(fresh.latest_analysis || 'Aucune analyse disponible.')
            setCurrentPeople(fresh.people_involved || 'Non spécifié')
          } else {
            // FAILED: only update status if we already have some data
            setAnalysisData((prev) => (prev ? { ...prev, status: 'FAILED' as any } : prev))
          }
          return
        }
        // Still processing or pending: update status only and schedule next poll
        setAnalysisData((prev) => (prev ? { ...prev, status: st.status as any } : prev))
        timeoutId = setTimeout(pollStatus, 3000)
      } catch (e) {
        // On error, try again later
        timeoutId = setTimeout(pollStatus, 3000)
      }
    }

    const load = async () => {
      if (!analysisId) return
      setIsLoading(true)
      setError(null)
      try {
        const data = await api.getAnalysisDetail(analysisId)
        setAnalysisData(data)
        setCurrentPrompt(data.prompt || '')
        setCurrentAnalysis(data.latest_analysis || 'Aucune analyse disponible.')
        setCurrentPeople(data.people_involved || 'Non spécifié')
        if (data.status === 'PROCESSING' || data.status === 'PENDING') {
          timeoutId = setTimeout(pollStatus, 3000)
        }
      } catch (e: any) {
        setError(e)
        console.error('Failed to load analysis detail', e)
      } finally {
        setIsLoading(false)
      }
    }
    load()

    return () => {
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [analysisId])

  const rerunAnalysis = useCallback(async () => {
    if (!analysisId || !currentPrompt.trim()) return
    setIsRerunning(true)
    setError(null)
    try {
      await api.rerunAnalysis(analysisId, currentPrompt)
      const data = await api.getAnalysisDetail(analysisId)
      setAnalysisData(data)
      setCurrentAnalysis(data.latest_analysis || 'Aucune analyse disponible.')
      setCurrentPeople(data.people_involved || 'Non spécifié')
    } catch (e: any) {
      setError(e)
      console.error('Failed to rerun analysis', e)
    } finally {
      setIsRerunning(false)
    }
  }, [analysisId, currentPrompt])

  const selectVersion = useCallback(async (v: AnalysisVersion) => {
    setCurrentPeople(v.people_involved || 'Non spécifié')
    setCurrentPrompt(v.prompt_used || '')
    try {
      const content = await api.getVersionResult(v.id)
      setCurrentAnalysis(content || 'Aucune analyse disponible.')
    } catch (e: any) {
      setError(e)
      console.error('Failed to load version result', e)
    }
  }, [])

  return {
    analysisData,
    currentAnalysis,
    currentPrompt,
    currentPeople,
    isLoading,
    isRerunning,
    error,
    setCurrentPrompt,
    rerunAnalysis,
    selectVersion,
  }
}
