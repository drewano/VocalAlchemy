import { useEffect, useState, useCallback } from 'react'
import * as api from '@/services/api'
import type { AnalysisSummary } from '@/types'

export function usePaginatedAnalysisHistory(pageSize = 20) {
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<{ message: string; status: number } | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  const fetchAnalyses = useCallback(async (page: number) => {
    setIsLoading(true)
    setError(null)
    try {
      const { items, total } = await api.listAnalyses({ page, pageSize })
      setAnalyses(items)
      setCurrentPage(page)
      setTotalPages(Math.max(1, Math.ceil(total / pageSize)))
    } catch (e: any) {
      setError(e)
      console.error('Erreur chargement historique paginé', e)
    } finally {
      setIsLoading(false)
    }
  }, [pageSize])

  useEffect(() => {
    fetchAnalyses(1)
  }, [fetchAnalyses])

  const goToPage = (page: number) => {
    const p = Math.max(1, page)
    fetchAnalyses(p)
  }

  return {
    analyses,
    isLoading,
    error,
    currentPage,
    totalPages,
    goToPage,
    refresh: () => fetchAnalyses(currentPage),
  }
}
