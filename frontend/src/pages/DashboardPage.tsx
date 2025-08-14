import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { usePaginatedAnalysisHistory } from '@/hooks/usePaginatedAnalysisHistory'
import { History, CheckCircle2, Hourglass, XCircle } from 'lucide-react'

const DashboardPage: React.FC = () => {
  const { analyses: history, isLoading } = usePaginatedAnalysisHistory(10)
  const navigate = useNavigate()

  return (
    <div className="container mx-auto p-8">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
        {/* Colonne 1: Message d'invitation */}
        <div>
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Nouvelle analyse</CardTitle>
              <CardDescription>
                Lancez une nouvelle analyse de réunion
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="mb-4 text-sm text-gray-600">
                Pour démarrer une nouvelle analyse, rendez-vous sur la page "Réunions" où vous pourrez 
                enregistrer ou importer un fichier audio.
              </p>
              <Button onClick={() => navigate('/meetings')} className="w-full">
                Aller à la page Réunions
              </Button>
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

            {/* List */}
            {isLoading ? (
              <p className="text-sm text-gray-500">Chargement...</p>
            ) : history.length === 0 ? (
              <p className="text-sm text-gray-500">Aucune analyse trouvée.</p>
            ) : (
              <ul className="divide-y divide-gray-200">
                {history.slice(0, 5).map((item) => {
                  const isCompleted = item.status === 'COMPLETED'
                  const isFailed = item.status === 'TRANSCRIPTION_FAILED' || item.status === 'ANALYSIS_FAILED'
                  const isProcessing = !isCompleted && !isFailed

                  const statusIcon = isCompleted
                    ? <CheckCircle2 className="text-green-500" />
                    : isFailed
                      ? <XCircle className="text-red-500" />
                      : <Hourglass className="text-yellow-500" />

                  return (
                    <li key={item.id} className="flex items-center py-4 space-x-4">
                      <div className="shrink-0">
                        {statusIcon}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">{item.filename}</p>
                        <p className="text-xs text-gray-500">{new Date(item.created_at).toLocaleString()}</p>
                      </div>
                      {isFailed ? (
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
