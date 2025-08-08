import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Pencil, Download, Settings } from 'lucide-react'
import MarkdownDisplay from '@/components/MarkdownDisplay'
import type { AnalysisStepResult } from '@/types'
import { updateStepResult, relaunchAnalysisStep } from '@/services/api'
import { downloadTextAsFile } from '@/lib/utils'
import { useToast } from '@/hooks/use-toast'

interface StepResultItemProps {
  step: AnalysisStepResult
}

const StepResultItem: React.FC<StepResultItemProps> = ({ step }) => {
  const { toast } = useToast()
  const [isEditing, setIsEditing] = useState(false)
  const [editedContent, setEditedContent] = useState(step.content || '')
  const [isPromptDialogOpen, setIsPromptDialogOpen] = useState(false)
  const [editedPrompt, setEditedPrompt] = useState('')
  const [isRelaunching, setIsRelaunching] = useState(false)

  // Mettre à jour le contenu édité lorsque les props changent
  useEffect(() => {
    setEditedContent(step.content || '')
  }, [step.content])

  const handleSave = async () => {
    try {
      await updateStepResult(step.id, editedContent)
      setIsEditing(false)
      toast.success("Le résultat a été mis à jour avec succès.")
    } catch (error) {
      console.error('Erreur lors de la mise à jour du résultat:', error)
      toast.error("Impossible de mettre à jour le résultat.")
    }
  }

  const handleCancel = () => {
    setEditedContent(step.content || '')
    setIsEditing(false)
  }

  const handleDownload = () => {
    downloadTextAsFile(editedContent, `resultat-${step.id}.txt`)
  }

  const handleRelaunch = async () => {
    try {
      setIsRelaunching(true)
      await relaunchAnalysisStep(step.id, editedPrompt)
      toast.success("L'étape a été relancée avec succès.")
    } catch (error) {
      console.error("Erreur lors du relancement de l'analyse:", error)
      toast.error("Impossible de relancer l'analyse.")
    } finally {
      setIsRelaunching(false)
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-lg">{step.step_name}</CardTitle>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={handleDownload}
            title="Télécharger en .txt"
          >
            <Download className="h-4 w-4" />
          </Button>
          <Dialog open={isPromptDialogOpen} onOpenChange={setIsPromptDialogOpen}>
            <DialogTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                title="Modifier le prompt"
              >
                <Settings className="h-4 w-4" />
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Modifier le prompt</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <Textarea
                  value={editedPrompt}
                  onChange={(e) => setEditedPrompt(e.target.value)}
                  placeholder="Entrez un nouveau prompt pour relancer cette étape..."
                  rows={10}
                />
                <div className="flex justify-end gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setIsPromptDialogOpen(false)}
                  >
                    Annuler
                  </Button>
                  <Button onClick={handleRelaunch} disabled={isRelaunching}>
                    {isRelaunching ? (
                      <span className="inline-flex items-center gap-2">
                        <span className="h-4 w-4 animate-spin">↻</span>
                        Relance...
                      </span>
                    ) : (
                      'Relancer'
                    )}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsEditing(!isEditing)}
            title={isEditing ? "Annuler l'édition" : "Modifier le résultat"}
          >
            <Pencil className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isEditing ? (
          <div className="space-y-4">
            <Textarea
              value={editedContent}
              onChange={(e) => setEditedContent(e.target.value)}
              rows={15}
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={handleCancel}>
                Annuler
              </Button>
              <Button onClick={handleSave}>
                Enregistrer
              </Button>
            </div>
          </div>
        ) : (
          <MarkdownDisplay content={editedContent} />
        )}
      </CardContent>
    </Card>
  )
}

export default StepResultItem