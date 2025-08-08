import React, { useState, useMemo } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Download } from 'lucide-react'
import MarkdownDisplay from '@/components/MarkdownDisplay'
import type { AnalysisStepResult } from '@/types'
import * as api from '@/services/api'

interface AssemblyTabProps {
  steps: AnalysisStepResult[]
  analysisId?: string
}

const AssemblyTab: React.FC<AssemblyTabProps> = ({ steps, analysisId }) => {
  const [isEditing, setIsEditing] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  
  // Concaténer le contenu de toutes les étapes en un seul texte Markdown
  const assembledContent = useMemo(() => {
    return steps
      .filter(step => step.content)
      .map(step => `## ${step.step_name}

${step.content}`)
      .join(`

`)
  }, [steps])

  // Vérifier s'il y a du contenu à afficher
  const hasContent = useMemo(() => {
    return steps.some(step => step.content)
  }, [steps])

  const [editedContent, setEditedContent] = useState(assembledContent)

  // Mettre à jour le contenu édité lorsque l'assemblage change
  React.useEffect(() => {
    setEditedContent(assembledContent)
  }, [assembledContent])

  const handleSave = () => {
    // Dans une vraie application, vous voudriez sauvegarder le contenu modifié
    // Pour l'instant, on se contente de sortir du mode édition
    setIsEditing(false)
    // Afficher un message de succès serait utile ici
    console.log('Contenu enregistré avec succès')
  }

  const handleDownloadWord = async () => {
    if (!analysisId) {
      console.error('ID d\'analyse manquant')
      return
    }
    
    try {
      setIsDownloading(true)
      const blob = await api.downloadWordDocument(analysisId, 'assembly')
      
      // Créer une URL pour le blob et déclencher le téléchargement
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `analyse-${analysisId}.docx`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('Erreur lors du téléchargement du document Word:', error)
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div className="flex gap-2">
          {isEditing ? (
            <>
              <Button variant="outline" onClick={() => setIsEditing(false)}>
                Annuler
              </Button>
              <Button onClick={handleSave}>Enregistrer</Button>
            </>
          ) : (
            <Button onClick={() => setIsEditing(true)} disabled={!hasContent}>
              Modifier
            </Button>
          )}
        </div>
        <Button onClick={handleDownloadWord} disabled={isDownloading || !hasContent || !analysisId}>
          <Download className="mr-2 h-4 w-4" />
          Télécharger en Word
        </Button>
      </div>

      {hasContent ? (
        isEditing ? (
          <Textarea
            value={editedContent}
            onChange={(e) => setEditedContent(e.target.value)}
            rows={20}
            className="font-mono text-sm"
          />
        ) : (
          <MarkdownDisplay content={editedContent} />
        )
      ) : (
        <div className="text-sm text-muted-foreground p-4 border border-dashed rounded-md">
          Aucun contenu disponible pour l'assemblage. Les résultats des étapes apparaîtront ici une fois l'analyse terminée.
        </div>
      )}
    </div>
  )
}

export default AssemblyTab