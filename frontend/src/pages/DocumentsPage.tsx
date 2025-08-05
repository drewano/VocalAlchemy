import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { usePaginatedAnalysisHistory } from '@/hooks/usePaginatedAnalysisHistory'
import DocumentCard from '@/components/DocumentCard'

export default function DocumentsPage() {
  const { analyses, isLoading, error, currentPage, totalPages, goToPage, refresh } = usePaginatedAnalysisHistory(12)

  return (
    <div className="p-4">
      <Card>
        <CardHeader className="border-b">
          <CardTitle>Mes Documents</CardTitle>
          <CardDescription>Gérez et consultez vos documents générés ou importés.</CardDescription>
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
            <div className="text-muted-foreground">Aucun document à afficher pour le moment.</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {analyses.map((a) => (
                <DocumentCard key={a.id} analysis={a} onDeleteSuccess={refresh} />
              ))}
            </div>
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
