import React, { useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useAnalysisDetail } from '@/hooks/useAnalysisDetail'

import AudioPlayer from '@/components/AudioPlayer'
import { Spinner } from '@/components/ui/spinner'
import { usePromptFlows } from '@/hooks/usePromptFlows'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import TranscriptionTab from '@/components/analysis/TranscriptionTab'
import ResultsTab from '@/components/analysis/ResultsTab'
import AssemblyTab from '@/components/analysis/AssemblyTab'

const AnalysisDetailPage: React.FC = () => {
  const { analysisId } = useParams<{ analysisId: string }>()
  usePromptFlows()

  const {
    analysisData,
    currentPeople,
    isLoading,
    isRerunning,
    rerunAnalysis,
    editedTranscript,
    setEditedTranscript,
    saveTranscript,
    isSaving,
  } = useAnalysisDetail(analysisId)

  const scrollToRerunSection = useCallback(() => {
    document.getElementById('rerun-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  if (isLoading) {
    return (
      <div className="container mx-auto py-8 space-y-6">
        <Skeleton className="h-24 w-full" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <Skeleton className="h-[60vh] w-full" />
          <div className="space-y-6">
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-[30vh] w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        </div>
      </div>
    )
  }

  if (!analysisData) {
    return (
      <div className="container mx-auto py-8">
        <Card>
          <CardHeader>
            <CardTitle>Analyse introuvable</CardTitle>
          </CardHeader>
          <CardContent>Impossible de charger les détails de l'analyse.</CardContent>
        </Card>
      </div>
    )
  }

  

  // Simplified flags for spinners
  const isTranscribing = analysisData.status === 'PENDING' || analysisData.status === 'TRANSCRIPTION_IN_PROGRESS'
  const isAnalyzing = analysisData.status === 'ANALYSIS_PENDING' || analysisData.status === 'ANALYSIS_IN_PROGRESS'

  return (
    <div className="container mx-auto py-8 space-y-8">
      {/* Barre d'actions sticky */}
      <div className="sticky top-0 z-20 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8 py-4 mb-2 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-b">
        <div className="flex items-center justify-between gap-2">
          <div className="text-lg font-semibold">Détails de la réunion</div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={scrollToRerunSection}>Relancer</Button>
          </div>
        </div>
      </div>

      {/* Panneau du haut */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Détails de l'analyse</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <div className="text-sm text-muted-foreground">Fichier</div>
              <div className="font-medium break-all">{analysisData.filename}</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Créée le</div>
              <div className="font-medium">
                {new Date(analysisData.created_at).toLocaleString()}
              </div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Personnes concernées</div>
              {analysisData.status === 'COMPLETED' ? (
                <div className="font-medium whitespace-pre-wrap">{currentPeople || '—'}</div>
              ) : (
                <div className="text-sm text-muted-foreground">Disponible après l'analyse.</div>
              )}
            </div>
            <div className="sm:col-span-3">
              <AudioPlayer analysisId={analysisData.id} />
            </div>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="transcription" className="w-full">
        <TabsList>
          <TabsTrigger value="transcription">Transcription</TabsTrigger>
          <TabsTrigger value="results">Résultats par étapes</TabsTrigger>
          <TabsTrigger value="assembly">Assemblage</TabsTrigger>
        </TabsList>
        <TabsContent value="transcription">
          <Card>
            <CardHeader>
              <CardTitle>Transcription</CardTitle>
            </CardHeader>
            <CardContent>
              {isTranscribing ? (
                <Spinner text="Transcription en cours avec Azure AI Speech..." />
              ) : (
                <TranscriptionTab
                  analysisId={analysisData.id}
                  transcript={editedTranscript}
                  onTranscriptChange={setEditedTranscript}
                  onSave={saveTranscript}
                  isSaving={isSaving}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="results">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Résultats par étapes</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {analysisData.versions && analysisData.versions.length > 0 && (
                <ResultsTab
                  steps={analysisData.versions[0].steps || []}
                  isAnalyzing={isAnalyzing}
                  onRerunWorkflow={rerunAnalysis}
                  isRerunning={isRerunning}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="assembly">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Assemblage</CardTitle>
            </CardHeader>
            <CardContent>
              {analysisData.versions && analysisData.versions.length > 0 ? (
                <AssemblyTab steps={analysisData.versions[0].steps || []} />
              ) : (
                <div className="text-sm text-muted-foreground p-4">
                  Aucune donnée d'assemblage disponible.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default AnalysisDetailPage
