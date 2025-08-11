import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@/components/ui/select'
import { usePromptFlows } from '@/hooks/usePromptFlows'
import { useAnalysisSubmit } from '@/hooks/useAnalysisSubmit'
import { renameAnalysis } from '@/services/api'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: (analysisId: string) => void
}

const MAX_FILE_BYTES = 500 * 1024 * 1024 // 500 Mo

export default function StartMeetingDialog({ open, onOpenChange, onSuccess }: Props) {
  const { flows, isLoading: isLoadingPrompts, error: promptsError } = usePromptFlows()
  const { submitAnalysis, isSubmitting } = useAnalysisSubmit()

  const [selectedPrompt, setSelectedPrompt] = useState<string>('')
  const [meetingName, setMeetingName] = useState('')
  const [file, setFile] = useState<File | null>(null)

  const fileInputRef = useRef<HTMLInputElement | null>(null)

  // Reset form when the dialog opens/closes
  useEffect(() => {
    if (!open) {
      setSelectedPrompt('')
      setMeetingName('')
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }, [open])

  const promptOptions = useMemo(() => flows, [flows])

  const canSubmit = !!selectedPrompt && !!file && !isSubmitting

  const handleFileChange: React.ChangeEventHandler<HTMLInputElement> = (e) => {
    const f = e.target.files?.[0] || null
    if (!f) {
      setFile(null)
      return
    }
    if (!f.type.startsWith('audio/')) {
      toast.error('Le fichier sélectionné doit être un fichier audio.')
      e.target.value = ''
      setFile(null)
      return
    }
    if (f.size > MAX_FILE_BYTES) {
      toast.error('La taille maximale autorisée est de 500 Mo.')
      e.target.value = ''
      setFile(null)
      return
    }
    setFile(f)
  }

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit || !file) {
      toast.error('Veuillez sélectionner un prompt et un fichier audio.')
      return
    }
    try {
      const analysisId = await submitAnalysis(file, selectedPrompt)
      if (meetingName.trim()) {
        try {
          await renameAnalysis(analysisId, meetingName.trim())
        } catch (err: any) {
          // Tolérer un échec de renommage (non-bloquant) + toast
          console.warn('Rename failed (tolerated):', err)
          toast.error("Le renommage a échoué, la réunion a été démarrée avec le nom d'origine.")
        }
      }
      toast.success('Réunion démarrée. Le traitement est en cours.')
      onSuccess(analysisId)
      onOpenChange(false)
    } catch (err: any) {
      toast.error(err?.message || "Échec du démarrage de la réunion")
    }
  }

  useEffect(() => {
    if (promptsError) {
      toast.error(promptsError.message)
    }
  }, [promptsError])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby={undefined}>
        <DialogHeader>
          <DialogTitle>Démarrer une réunion</DialogTitle>
          <DialogDescription>
            Importez un fichier audio (500 Mo max) et choisissez un prompt pour lancer l'analyse.
          </DialogDescription>
        </DialogHeader>

        <form className="space-y-4" onSubmit={handleStart}>
          <div className="space-y-2">
            <Label htmlFor="prompt">Flux de prompt</Label>
            <Select
              value={selectedPrompt}
              onValueChange={setSelectedPrompt}
              disabled={isSubmitting || isLoadingPrompts}
            >
              <SelectTrigger id="prompt" aria-label="Nom du prompt">
                <SelectValue placeholder={isLoadingPrompts ? 'Chargement…' : 'Sélectionner un prompt'} />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectLabel>Prompts disponibles</SelectLabel>
                  {promptOptions.length === 0 ? (
                    <SelectItem disabled value="__none__">Aucun prompt</SelectItem>
                  ) : (
                    promptOptions.map((flow) => (
                      <SelectItem key={flow.id} value={flow.id}>{flow.name}</SelectItem>
                    ))
                  )}
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="meetingName">Nom de la réunion (facultatif)</Label>
            <Input
              id="meetingName"
              placeholder="Ex: Sync Produit - 12/03"
              value={meetingName}
              onChange={(e) => setMeetingName(e.target.value)}
              disabled={isSubmitting}
              aria-label="Nom de la réunion"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="audioFile">Fichier audio (500 Mo max)</Label>
            <Input
              id="audioFile"
              ref={fileInputRef}
              type="file"
              accept="audio/*"
              onChange={handleFileChange}
              disabled={isSubmitting}
              aria-label="Importer un fichier audio"
              required
            />
            <p className="text-xs text-muted-foreground">Formats audio pris en charge. Taille maximale 500 Mo.</p>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting} aria-label="Annuler">
              Annuler
            </Button>
            <Button type="submit" disabled={!canSubmit} aria-label="Démarrer la réunion" data-state={isSubmitting ? 'loading' : undefined}>
              {isSubmitting ? 'Démarrage…' : 'Démarrer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}


