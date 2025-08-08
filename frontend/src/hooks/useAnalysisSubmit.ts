import { useState, useCallback } from 'react'
import * as api from '@/services/api'

export function useAnalysisSubmit() {
  const [isSubmitting, setIsSubmitting] = useState(false)

  const submitAnalysis = useCallback(async (file: File, promptFlowId: string): Promise<string> => {
    setIsSubmitting(true)
    try {
      // Étape 1 : Initiation - Obtenir l'URL SAS et créer l'enregistrement d'analyse
      const { sasUrl, analysisId } = await api.initiateUpload(file.name)

      // Étape 2 : Upload direct - Envoyer le fichier vers Azure Blob Storage
      await api.uploadFileToSasUrl(sasUrl, file)

      // Étape 3 : Finalisation - Déclencher le traitement en arrière-plan
      await api.finalizeUpload(analysisId, promptFlowId)

      // Étape 4 : Résultat - Retourner l'ID pour la navigation
      return analysisId
    } catch (err) {
      // Propagate error to the caller
      throw err
    } finally {
      setIsSubmitting(false)
    }
  }, [])

  return { submitAnalysis, isSubmitting }
}
