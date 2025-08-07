import { useEffect, useState } from 'react'
import * as api from '@/services/api'

export type AnalysisHistoryItem = {
  id: string
  filename: string
  date: string
  status: 'completed' | 'processing' | 'failed'
}

export function useAnalysisHistory() {
  const [history, setHistory] = useState<AnalysisHistoryItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<{ message: string; status: number } | null>(null)

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const { items } = await api.listAnalyses({ page: 1, pageSize: 100 })
        const mapped: AnalysisHistoryItem[] = items.map((it) => ({
          id: it.id,
          filename: it.filename || 'fichier',
          date: new Date(it.created_at).toLocaleString(),
          status:
            it.status === 'COMPLETED'
              ? 'completed'
              : (it.status === 'TRANSCRIPTION_FAILED' || it.status === 'ANALYSIS_FAILED')
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

  return { history, isLoading, error }
}
