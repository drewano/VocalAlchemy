import React, { useContext } from 'react'
import { useNavigate } from 'react-router-dom'
import AuthContext from '@/contexts/AuthContext'
import { UploadForm } from '@/components/UploadForm'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useAnalysisHistory } from '@/hooks/useAnalysisHistory'
import { usePrompts } from '@/hooks/usePrompts'

const DashboardPage: React.FC = () => {
  const { history, isLoading, isSubmitting, submitNewAnalysis } = useAnalysisHistory()
  const { prompts, isLoading: isLoadingPrompts } = usePrompts()

  const authContext = useContext(AuthContext)
  const navigate = useNavigate()

  if (!authContext) {
    throw new Error('DashboardPage must be used within an AuthProvider')
  }

  // Profil/déconnexion gérés via /profile, pas d'usage ici

  return (
    <div className="container mx-auto py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Tableau de bord</h1>
        {/* Profil et déconnexion gérés désormais via la page Profil */}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Formulaire d'upload */}
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
                  onSubmit={submitNewAnalysis}
                  isLoading={isSubmitting}
                />
              )}
            </CardContent>
          </Card>
        </div>

        {/* Historique des analyses */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle>Historique des analyses</CardTitle>
              <CardDescription>Liste de vos analyses récentes</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Fichier</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Statut</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((item) => (
                    <TableRow
                      key={item.id}
                      className="cursor-pointer hover:bg-muted/40"
                      onClick={() => navigate(`/analysis/${item.id}`)}
                    >
                      <TableCell className="font-medium">{item.filename}</TableCell>
                      <TableCell>{item.date}</TableCell>
                      <TableCell>
                        <span
                          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                            item.status === 'completed'
                              ? 'bg-green-100 text-green-800'
                              : item.status === 'failed'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-yellow-100 text-yellow-800'
                          }`}
                        >
                          {item.status === 'completed'
                            ? 'Terminé'
                            : item.status === 'failed'
                            ? 'Échoué'
                            : 'En cours'}
                        </span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

export default DashboardPage