import { useCallback, useEffect, useState, useRef } from 'react'
import * as api from '@/services/api'
import type { AnalysisDetail, AnalysisStatus } from '@/types'

export function useAnalysisDetail(analysisId?: string) {
  const [analysisData, setAnalysisData] = useState<AnalysisDetail | null>(null)
  // Removed currentAnalysis; content now comes from step results directly
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [isRerunning, setIsRerunning] = useState<boolean>(false)
  const [isSaving, setIsSaving] = useState<boolean>(false)
  const [error, setError] = useState<{ message: string; status: number } | null>(null)
  const [editedTranscript, setEditedTranscript] = useState<string>('')
  const [selectedFlowForRerun, setSelectedFlowForRerun] = useState<string>('')
  const wsRef = useRef<WebSocket | null>(null)

  // Step 1: isolate full load in useCallback
  const load = useCallback(async () => {
    if (!analysisId) return
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.getAnalysisDetail(analysisId)
      setAnalysisData(data)
      // latest_analysis is no longer primary; steps will be displayed progressively
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

  // Step 3: WebSocket connection for real-time status updates
  useEffect(() => {
    if (!analysisId) return

    // Close any existing WebSocket connection
    if (wsRef.current) {
      wsRef.current.close()
    }

    // Determine WebSocket URL
    const wsUrl = (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + 
                  window.location.host + `/api/analysis/ws/${analysisId}`

    // Create WebSocket connection
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      console.log(`Connected to WebSocket for analysis ${analysisId}`)
    }

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        const newStatus = message.status as AnalysisStatus
        const newErrorMessage = message.error_message

        // Update the analysis data with the new status
        setAnalysisData(prev => 
          prev ? { ...prev, status: newStatus, error_message: newErrorMessage } : null
        )

        // Terminal statuses that should trigger a full data reload
        const terminalStatuses = new Set([
          'COMPLETED',
          'TRANSCRIPTION_FAILED',
          'ANALYSIS_FAILED'
        ])

        // If we received a terminal status, reload the full data
        if (terminalStatuses.has(newStatus)) {
          load()
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message', e)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error', error)
      setError({ message: 'WebSocket connection error', status: 0 })
    }

    ws.onclose = () => {
      console.log(`WebSocket connection closed for analysis ${analysisId}`)
    }

    // Cleanup function to close the WebSocket connection
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [analysisId, load])

  const rerunAnalysis = useCallback(async () => {
    if (!analysisId || !selectedFlowForRerun) return
    setIsRerunning(true)
    setError(null)
    try {
      await api.rerunAnalysis(analysisId, selectedFlowForRerun)
      const data = await api.getAnalysisDetail(analysisId)
      setAnalysisData(data)
    } catch (e: any) {
      setError(e)
      console.error('Failed to rerun analysis', e)
    } finally {
      setIsRerunning(false)
    }
  }, [analysisId, selectedFlowForRerun])

  const saveTranscript = useCallback(async () => {
    if (!analysisId) return
    setIsSaving(true)
    setError(null)
    try {
      await api.updateTranscript(analysisId, editedTranscript)
      const data = await api.getAnalysisDetail(analysisId)
      setAnalysisData(data)
      setEditedTranscript(data.transcript || '')
    } catch (e: any) {
      setError(e)
      console.error('Failed to update transcript', e)
    } finally {
      setIsSaving(false)
    }
  }, [analysisId, editedTranscript])

  return {
    analysisData,
    isLoading,
    isRerunning,
    isSaving,
    error,
    rerunAnalysis,
    editedTranscript,
    setEditedTranscript,
    saveTranscript,
    selectedFlowForRerun,
    setSelectedFlowForRerun,
  }
}
