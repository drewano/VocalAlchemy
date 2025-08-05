import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { AnalysisSummary } from '@/types'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import AudioPlayer from '@/components/AudioPlayer'
import { Trash2, Pencil } from 'lucide-react'
import { deleteAnalysis, renameAnalysis } from '@/services/api'
import { AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction } from '@/components/ui/alert-dialog'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { toast } from 'sonner'

type Props = {
  analysis: AnalysisSummary
  onDeleteSuccess: () => void
}

export default function DocumentCard({ analysis, onDeleteSuccess }: Props) {
  const createdLabel = new Date(analysis.created_at).toLocaleString()
  const [isDeleting, setIsDeleting] = useState(false)
  const [isConfirmOpen, setIsConfirmOpen] = useState(false)

  const [isRenameOpen, setIsRenameOpen] = useState(false)
  const [newFilename, setNewFilename] = useState(analysis.filename || '')
  const [isRenaming, setIsRenaming] = useState(false)

  const handleDelete = async () => {
    setIsDeleting(true)
    try {
      await deleteAnalysis(analysis.id)
      toast.success('Document supprimé.')
      setIsConfirmOpen(false)
      onDeleteSuccess()
    } catch (e: any) {
      toast.error(e?.message || 'Échec de la suppression')
    } finally {
      setIsDeleting(false)
    }
  }

  const handleRename = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsRenaming(true)
    try {
      await renameAnalysis(analysis.id, newFilename)
      toast.success('Nom mis à jour.')
      setIsRenameOpen(false)
      onDeleteSuccess()
    } catch (e: any) {
      toast.error(e?.message || "Échec du renommage")
    } finally {
      setIsRenaming(false)
    }
  }

  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="truncate" title={analysis.filename}>{analysis.filename || 'Document'}</CardTitle>
        <CardDescription>{createdLabel}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <AudioPlayer analysisId={analysis.id} />

        {analysis.transcript_snippet && (
          <div>
            <div className="text-sm font-medium mb-1">Extrait de la transcription</div>
            <p className="text-sm text-muted-foreground line-clamp-3 whitespace-pre-wrap">
              {analysis.transcript_snippet}
            </p>
          </div>
        )}

        {analysis.analysis_snippet && (
          <div>
            <div className="text-sm font-medium mb-1">Extrait de l'analyse</div>
            <p className="text-sm text-muted-foreground line-clamp-3 whitespace-pre-wrap">
              {analysis.analysis_snippet}
            </p>
          </div>
        )}
      </CardContent>
      <CardFooter className="border-t justify-between">
        <Button asChild size="sm" variant="outline">
          <Link to={`/analysis/${analysis.id}`}>Voir les détails</Link>
        </Button>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            aria-label="Renommer"
            onClick={() => {
              setNewFilename(analysis.filename || '')
              setIsRenameOpen(true)
            }}
          >
            <Pencil className="size-4" />
          </Button>

          <AlertDialog open={isConfirmOpen} onOpenChange={setIsConfirmOpen}>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="icon" onClick={() => setIsConfirmOpen(true)} disabled={isDeleting} aria-label="Supprimer">
                <Trash2 className="size-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Êtes-vous sûr ?</AlertDialogTitle>
                <AlertDialogDescription>
                  Cette action est irréversible et supprimera le document et toutes ses données associées.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel disabled={isDeleting}>Annuler</AlertDialogCancel>
                <AlertDialogAction onClick={handleDelete} disabled={isDeleting}>
                  {isDeleting ? 'Suppression...' : 'Confirmer'}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </CardFooter>

      <Dialog open={isRenameOpen} onOpenChange={setIsRenameOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Renommer le document</DialogTitle>
            <DialogDescription>Entrez un nouveau nom pour ce document.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleRename} className="space-y-4">
            <Input
              value={newFilename}
              onChange={(e) => setNewFilename(e.target.value)}
              placeholder="Nouveau nom"
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setIsRenameOpen(false)} disabled={isRenaming}>
                Annuler
              </Button>
              <Button type="submit" disabled={isRenaming || !newFilename.trim()}>
                {isRenaming ? 'Enregistrement...' : 'Enregistrer'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
