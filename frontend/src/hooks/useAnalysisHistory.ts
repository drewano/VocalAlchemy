import { useEffect, useState } from 'react'
import * as api from '@/services/api'
import type { AnalysisSummary } from '@/types'

export type AnalysisHistoryItem = {
  id: string
  filename: string
  date: string
  status: 'completed' | 'processing' | 'failed'
}

export function useAnalysisHistory() {
  const [history, setHistory] = useState<AnalysisHistoryItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<{ message: string; status: number } | null>(null)

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const items: AnalysisSummary[] = await api.listAnalyses()
        const mapped: AnalysisHistoryItem[] = items.map((it) => ({
          id: it.id,
          filename: it.filename || 'fichier',
          date: new Date(it.created_at).toLocaleString(),
          status:
            it.status === 'COMPLETED'
              ? 'completed'
              : it.status === 'FAILED'
              ? 'failed'
              : 'processing',
        }))
        setHistory(mapped)
      } catch (e: any) {
        setError(e)
        console.error('Erreur chargement historique', e)
      } finally {
        setIsLoading(false)
      }
    }
    loadHistory()
  }, [])

  const submitNewAnalysis = async (file: File, prompt: string) => {
    setIsSubmitting(true)
    setError(null)
    try {
      const { analysis_id: analysisId } = await api.processAudio(file, prompt)
      const newItem: AnalysisHistoryItem = {
        id: analysisId,
        filename: file.name,
        date: new Date().toLocaleString(),
        status: 'processing',
      }
      setHistory((prev) => [newItem, ...prev])

      const poll = async () => {
        try {
          const st = await api.getTaskStatus(analysisId)
          setHistory((prev) =>
            prev.map((h) =>
              h.id === analysisId
                ? {
                    ...h,
                    status:
                      st.status === 'COMPLETED'
                        ? 'completed'
                        : st.status === 'FAILED'
                        ? 'failed'
                        : 'processing',
                  }
                : h
            )
          )
          if (st.status !== 'COMPLETED' && st.status !== 'FAILED') {
            setTimeout(poll, 1500)
          }
        } catch (e: any) {
          console.error('Polling status error', e)
          setTimeout(poll, 2000)
        }
      }
      poll()
    } catch (err: any) {
      setError(err)
      console.error("Erreur lors de l'analyse:", err)
    } finally {
      setIsSubmitting(false)
    }
  }

  return { history, isLoading, isSubmitting, error, submitNewAnalysis }
}
