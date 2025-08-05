import { Link } from 'react-router-dom'
import { usePaginatedAnalysisHistory } from '@/hooks/usePaginatedAnalysisHistory'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '@/components/ui/table'
import { Button } from '@/components/ui/button'

export default function HistoryPage() {
  const { analyses, isLoading, error, currentPage, totalPages, goToPage } = usePaginatedAnalysisHistory(20)

  return (
    <div className="p-4">
      <Card>
        <CardHeader className="border-b">
          <CardTitle>Historique des Analyses</CardTitle>
          <CardDescription>Consultez vos analyses récentes et accédez aux détails.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              <div className="h-4 w-1/3 bg-muted animate-pulse rounded" />
              <div className="h-4 w-2/3 bg-muted animate-pulse rounded" />
              <div className="h-4 w-full bg-muted animate-pulse rounded" />
            </div>
          ) : error ? (
            <div className="text-destructive">{error.message}</div>
          ) : analyses.length === 0 ? (
            <div className="text-muted-foreground">Aucune analyse pour le moment.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nom du fichier</TableHead>
                  <TableHead>Date de création</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {analyses.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="max-w-[320px] truncate">{a.filename || 'fichier'}</TableCell>
                    <TableCell>{new Date(a.created_at).toLocaleString()}</TableCell>
                    <TableCell>
                      <span
                        className={
                          a.status === 'COMPLETED'
                            ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300 px-2 py-0.5 rounded text-xs'
                            : a.status === 'FAILED'
                            ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 px-2 py-0.5 rounded text-xs'
                            : 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300 px-2 py-0.5 rounded text-xs'
                        }
                      >
                        {a.status === 'COMPLETED' ? 'Terminé' : a.status === 'FAILED' ? 'Échec' : 'En cours'}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="outline">
                        <Link to={`/analysis/${a.id}`}>Voir</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
        <CardFooter className="border-t justify-between">
          <div className="text-sm text-muted-foreground">Page {currentPage} sur {totalPages}</div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => goToPage(currentPage - 1)} disabled={currentPage <= 1 || isLoading}>
              Précédent
            </Button>
            <Button variant="outline" size="sm" onClick={() => goToPage(currentPage + 1)} disabled={currentPage >= totalPages || isLoading}>
              Suivant
            </Button>
          </div>
        </CardFooter>
      </Card>
    </div>
  )
}
