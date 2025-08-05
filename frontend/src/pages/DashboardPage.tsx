import React, { useContext } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import AuthContext from '@/contexts/AuthContext'
import { UploadForm } from '@/components/UploadForm'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Input } from '@/components/ui/input'
import { usePaginatedAnalysisHistory } from '@/hooks/usePaginatedAnalysisHistory'
import { usePrompts } from '@/hooks/usePrompts'
import { History, Search, CheckCircle2, Hourglass, XCircle } from 'lucide-react'
import { useAnalysisSubmit } from '@/hooks/useAnalysisSubmit'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

const DashboardPage: React.FC = () => {
  const { analyses: history, isLoading, refresh } = usePaginatedAnalysisHistory(10)
  const { prompts, isLoading: isLoadingPrompts } = usePrompts()
  const { searchTerm } = useOutletContext<any>()

  const authContext = useContext(AuthContext)
  const navigate = useNavigate()
  const { submitAnalysis, isSubmitting } = useAnalysisSubmit()

  const handleAnalysisSubmit = async (file: File, prompt: string) => {
    try {
      const analysisId = await submitAnalysis(file, prompt)
      toast.success("L'analyse a bien été lancée.")
      refresh()
      navigate(`/analysis/${analysisId}`)
    } catch (error: any) {
      toast.error("Échec de l'envoi : " + (error?.message || 'Erreur inconnue'))
    }
  }

  if (!authContext) {
    throw new Error('DashboardPage must be used within an AuthProvider')
  }

  const filtered = history.filter((h) =>
    !searchTerm ? true : h.filename.toLowerCase().includes(String(searchTerm).toLowerCase())
  )

  return (
    <div className="container mx-auto p-8">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
        {/* Colonne 1: Formulaire d'upload */}
        <div>
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Nouvelle analyse</CardTitle>
              <CardDescription>
                Téléchargez un fichier audio pour lancer une nouvelle analyse
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading || isLoadingPrompts ? (
                <div className="space-y-4">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : (
                <UploadForm
                  prompts={prompts}
                  onSubmit={handleAnalysisSubmit}
                  isLoading={isSubmitting}
                />
              )}
            </CardContent>
          </Card>
        </div>

        {/* Colonne 2: Historique des analyses */}
        <div>
          <div className="bg-white rounded-xl shadow-sm p-8">
            {/* Header */}
            <div className="flex items-center mb-6">
              <div className="bg-purple-100 text-purple-600 p-3 rounded-full mr-4">
                <History className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">Historique des analyses</h3>
                <p className="text-sm text-gray-600">Liste de vos analyses récentes</p>
              </div>
            </div>

            {/* Search input */}
            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                value={searchTerm || ''}
                onChange={() => { /* Read-only; provient du layout via Outlet context */ }}
                placeholder="Rechercher..."
                className="pl-9"
                readOnly
              />
            </div>

            {/* List */}
            {filtered.length === 0 ? (
              <p className="text-sm text-gray-500">Aucun résultat pour la recherche.</p>
            ) : (
              <ul className="divide-y divide-gray-200">
                {filtered.map((item) => {
                  const statusIcon = item.status === 'completed'
                    ? <CheckCircle2 className="text-green-500" />
                    : item.status === 'failed'
                      ? <XCircle className="text-red-500" />
                      : <Hourglass className="text-yellow-500" />

                  const isProcessing = item.status === 'processing'

                  return (
                    <li key={item.id} className="flex items-center py-4 space-x-4">
                      <div className="shrink-0">
                        {statusIcon}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">{item.filename}</p>
                        <p className="text-xs text-gray-500">{new Date(item.created_at).toLocaleString()}</p>
                      </div>
                      {item.status === 'failed' ? (
                        <Button variant="ghost" size="sm" onClick={() => navigate(`/analysis/${item.id}`)}>
                          Réessayer
                        </Button>
                      ) : (
                        <Button variant="ghost" size="sm" onClick={() => !isProcessing && navigate(`/analysis/${item.id}`)} disabled={isProcessing}>
                          Voir
                        </Button>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}

            {/* Footer link */}
            <div className="mt-6">
              <a href="/history" className="text-sm font-medium text-blue-600 hover:text-blue-700">Voir tout l'historique →</a>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DashboardPage
