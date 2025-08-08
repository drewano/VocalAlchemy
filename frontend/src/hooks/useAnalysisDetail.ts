import { useCallback, useEffect, useState } from 'react'
import * as api from '@/services/api'
import type { AnalysisDetail, AnalysisVersion, ActionPlanItem } from '@/types'

export function useAnalysisDetail(analysisId?: string) {
  const [analysisData, setAnalysisData] = useState<AnalysisDetail | null>(null)
  // Removed currentAnalysis; content now comes from step results directly
  const [currentPeople, setCurrentPeople] = useState<string>('')
  const [actionPlan, setActionPlan] = useState<ActionPlanItem[] | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [isRerunning, setIsRerunning] = useState<boolean>(false)
  const [error, setError] = useState<{ message: string; status: number } | null>(null)
  const [editedTranscript, setEditedTranscript] = useState<string>('')
  const [selectedFlowForRerun, setSelectedFlowForRerun] = useState<string>('')

  // Step 1: isolate full load in useCallback
  const load = useCallback(async () => {
    if (!analysisId) return
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.getAnalysisDetail(analysisId)
      setAnalysisData(data)
      // latest_analysis is no longer primary; steps will be displayed progressively
      setCurrentPeople(data.people_involved || 'Non spécifié')
      setActionPlan(data.action_plan || null)
      setEditedTranscript(data.transcript || '')
    } catch (e: any) {
      setError(e)
      console.error('Failed to load analysis detail', e)
    } finally {
      setIsLoading(false)
    }
  }, [analysisId])

  // Step 2: initial load once on analysisId change
  useEffect(() => {
    load()
  }, [analysisId, load])

  // Step 3: lightweight polling based on status
  useEffect(() => {
    if (!analysisId || !analysisData?.status) return

    const inProgressStatuses = new Set([
      'PENDING',
      'TRANSCRIPTION_IN_PROGRESS',
      'ANALYSIS_PENDING',
      'ANALYSIS_IN_PROGRESS',
    ])

    let intervalId: ReturnType<typeof setInterval> | null = null

    if (inProgressStatuses.has(analysisData.status)) {
      intervalId = setInterval(() => {
        api
          .checkAnalysisStatus(analysisId)
          .then((res) => {
            const newStatus = res.status
            setAnalysisData((prev) => (prev ? { ...prev, status: newStatus } : prev))
            if (!inProgressStatuses.has(newStatus)) {
              if (intervalId) clearInterval(intervalId)
              // Fetch full data one last time to get transcript/report
              load()
            }
          })
          .catch((e) => {
            // surface error but do not break UI completely
            setError(e)
          })
      }, 3000)
    }

    return () => {
      if (intervalId) clearInterval(intervalId)
    }
  }, [analysisData?.status, analysisId, load])

  const rerunAnalysis = useCallback(async () => {
    if (!analysisId || !selectedFlowForRerun) return
    setIsRerunning(true)
    setError(null)
    try {
      await api.rerunAnalysis(analysisId, selectedFlowForRerun)
      const data = await api.getAnalysisDetail(analysisId)
      setAnalysisData(data)
      setCurrentPeople(data.people_involved || 'Non spécifié')
      setActionPlan(data.action_plan || null)
    } catch (e: any) {
      setError(e)
      console.error('Failed to rerun analysis', e)
    } finally {
      setIsRerunning(false)
    }
  }, [analysisId, selectedFlowForRerun])

  const selectVersion = useCallback(async (v: AnalysisVersion) => {
    setCurrentPeople(v.people_involved || 'Non spécifié')
    try {
      // Version detail load still supported: latest_analysis view deprecated in UI
      await api.getVersionResult(v.id)
    } catch (e: any) {
      setError(e)
      console.error('Failed to load version result', e)
    }
  }, [])

  const saveTranscript = useCallback(async () => {
    if (!analysisId) return
    setError(null)
    try {
      await api.updateTranscript(analysisId, editedTranscript)
      const data = await api.getAnalysisDetail(analysisId)
      setAnalysisData(data)
      setEditedTranscript(data.transcript || '')
    } catch (e: any) {
      setError(e)
      console.error('Failed to update transcript', e)
    }
  }, [analysisId, editedTranscript])

  return {
    analysisData,
    currentPeople,
    isLoading,
    isRerunning,
    error,
    rerunAnalysis,
    selectVersion,
    actionPlan,
    editedTranscript,
    setEditedTranscript,
    saveTranscript,
    selectedFlowForRerun,
    setSelectedFlowForRerun,
  }
}
