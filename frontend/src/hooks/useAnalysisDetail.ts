import { useCallback, useEffect, useState } from 'react'
import * as api from '@/services/api'
import type { AnalysisDetail, AnalysisVersion, ActionPlanItem } from '@/types'

export function useAnalysisDetail(analysisId?: string) {
  const [analysisData, setAnalysisData] = useState<AnalysisDetail | null>(null)
  const [currentPrompt, setCurrentPrompt] = useState<string>('')
  const [currentAnalysis, setCurrentAnalysis] = useState<string>('')
  const [currentPeople, setCurrentPeople] = useState<string>('')
  const [actionPlan, setActionPlan] = useState<ActionPlanItem[] | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [isRerunning, setIsRerunning] = useState<boolean>(false)
  const [error, setError] = useState<{ message: string; status: number } | null>(null)

  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout> | null = null

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
        setActionPlan(data.action_plan || null)
        if (
          data.status === 'PENDING' ||
          data.status === 'TRANSCRIPTION_IN_PROGRESS' ||
          data.status === 'ANALYSIS_PENDING' ||
          data.status === 'ANALYSIS_IN_PROGRESS'
        ) {
          timeoutId = setTimeout(load, 3000)
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
      setActionPlan(data.action_plan || null)
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
    actionPlan,
  }
}
