import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { LoaderCircle } from 'lucide-react'
import * as api from '@/services/api'
import { downloadBlobAsFile } from '@/lib/utils'

interface TranscriptionTabProps {
  analysisId: string
  transcript: string
  onTranscriptChange: (value: string) => void
  onSave: () => void
  isSaving: boolean
}

export function TranscriptionTab({ analysisId, transcript, onTranscriptChange, onSave, isSaving }: TranscriptionTabProps) {
  const [isDownloading, setIsDownloading] = useState(false)
  const [isRelaunching, setIsRelaunching] = useState(false)

  const handleDownloadWord = async () => {
    try {
      setIsDownloading(true)
      const blob = await api.downloadWordDocument(analysisId, 'transcription')
      downloadBlobAsFile(blob, `transcription_${analysisId}.docx`)
    } catch (error) {
      console.error('Erreur lors du téléchargement du document Word:', error)
      // Vous pouvez ajouter une notification d'erreur ici
    } finally {
      setIsDownloading(false)
    }
  }

  const handleRelaunchTranscription = async () => {
    try {
      setIsRelaunching(true)
      await api.relaunchTranscription(analysisId)
      // Vous pouvez ajouter une notification de succès ici
    } catch (error) {
      console.error('Erreur lors du relancement de la transcription:', error)
      // Vous pouvez ajouter une notification d'erreur ici
    } finally {
      setIsRelaunching(false)
    }
  }

  return (
    <div className="space-y-4">
      <Textarea
        value={transcript}
        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => onTranscriptChange(e.target.value)}
        className="min-h-[50vh]"
        placeholder="Transcription de l'audio..."
      />
      
      <div className="flex flex-wrap gap-2">
        <Button onClick={onSave} disabled={isSaving || !transcript.trim()}>
          {isSaving ? (
            <span className="inline-flex items-center gap-2">
              <LoaderCircle className="h-4 w-4 animate-spin" /> Enregistrement...
            </span>
          ) : (
            'Enregistrer'
          )}
        </Button>
        
        <Button 
          variant="outline" 
          onClick={handleDownloadWord} 
          disabled={isDownloading}
        >
          {isDownloading ? (
            <span className="inline-flex items-center gap-2">
              <LoaderCircle className="h-4 w-4 animate-spin" /> Téléchargement...
            </span>
          ) : (
            'Télécharger en Word'
          )}
        </Button>
        
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="outline">Relancer la transcription</Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Relancer la transcription ?</AlertDialogTitle>
              <AlertDialogDescription>
                Êtes-vous sûr de vouloir relancer la transcription ? Cette opération peut prendre plusieurs minutes selon la durée de l'enregistrement.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Annuler</AlertDialogCancel>
              <AlertDialogAction 
                onClick={handleRelaunchTranscription}
                disabled={isRelaunching}
              >
                {isRelaunching ? (
                  <span className="inline-flex items-center gap-2">
                    <LoaderCircle className="h-4 w-4 animate-spin" /> Relance...
                  </span>
                ) : (
                  'Confirmer'
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  )
}

export default TranscriptionTab