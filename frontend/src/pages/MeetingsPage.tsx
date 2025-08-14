import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import StartMeetingDialog from '@/components/meetings/StartMeetingDialog'
import { usePaginatedAnalysisHistory } from '@/hooks/usePaginatedAnalysisHistory'
import DocumentCard from '@/components/DocumentCard'

export default function MeetingsPage() {
  const { analyses, isLoading, error, currentPage, totalPages, goToPage, refresh } = usePaginatedAnalysisHistory(12)
  const [searchTerm, setSearchTerm] = useState('')
  const [isStartOpen, setIsStartOpen] = useState(false)
  const navigate = useNavigate()

  const filtered = useMemo(() => {
    const term = searchTerm.trim().toLowerCase()
    if (!term) return analyses
    return analyses.filter((a) => (a.filename || '').toLowerCase().includes(term))
  }, [analyses, searchTerm])

  return (
    <div className="p-4">
      {/* Titre local (remplacé plus tard par le header dynamique) */}
      <h1 className="sr-only">Réunions</h1>

      {/* Barre d'actions supérieure (sticky) */}
      <div
        className="sticky top-0 z-20 -mx-4 md:-mx-6 lg:-mx-8 px-4 md:px-6 lg:px-8 py-4 mb-6
        bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-b"
      >
        <div className="flex items-center gap-2 justify-between">
        <div className="text-lg font-semibold">Réunions</div>
          <div className="flex-1 flex justify-center gap-2 px-4">
          <Input
            aria-label="Rechercher des réunions"
            placeholder="Rechercher"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="max-w-xl"
          />
            <Button variant="outline" aria-label="Ouvrir les tags" title="Tags">
              Tags
            </Button>
          </div>
          <div className="shrink-0">
            <Button onClick={() => setIsStartOpen(true)} aria-label="Démarrer une réunion" title="Démarrer">
              Démarrer
            </Button>
          </div>
        </div>
      </div>

      {/* Contenu principal allégé (style Upmeet) */}
      <section className="min-h-[60vh]">
        {isLoading ? (
          <div className="space-y-2">
            <div className="h-4 w-1/3 bg-muted animate-pulse rounded" />
            <div className="h-4 w-2/3 bg-muted animate-pulse rounded" />
            <div className="h-4 w-full bg-muted animate-pulse rounded" />
          </div>
        ) : error ? (
          <div className="text-destructive" role="alert">{error.message}</div>
        ) : filtered.length === 0 ? (
          <div className="flex justify-center">
            <div className="w-full max-w-3xl rounded-md border bg-card p-8 text-center text-sm text-muted-foreground">
              Démarrer votre première réunion en cliquant en haut à droite
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {filtered.map((a) => (
              <DocumentCard key={a.id} analysis={a} onDeleteSuccess={refresh} />
            ))}
          </div>
        )}
      </section>

      {/* Pagination simple (toujours en bas) */}
      <div className="mt-6 flex items-center justify-between">
        <div className="text-sm text-muted-foreground">Page {currentPage} sur {totalPages}</div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => goToPage(currentPage - 1)} disabled={currentPage <= 1 || isLoading} aria-label="Page précédente">
            Précédent
          </Button>
          <Button variant="outline" size="sm" onClick={() => goToPage(currentPage + 1)} disabled={currentPage >= totalPages || isLoading} aria-label="Page suivante">
            Suivant
          </Button>
        </div>
      </div>

      <StartMeetingDialog
        open={isStartOpen}
        onOpenChange={setIsStartOpen}
        onSuccess={(id) => {
          toast.success("L’analyse a bien été lancée.")
          refresh()
          navigate(`/analysis/${id}`)
        }}
      />
    </div>
  )
}


