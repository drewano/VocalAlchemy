import React, { useCallback, useRef } from 'react'
import { useParams } from 'react-router-dom'
import type { AnalysisVersion } from '@/types'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { LoaderCircle } from 'lucide-react'
import { useAnalysisDetail } from '@/hooks/useAnalysisDetail'

import AudioPlayer from '@/components/AudioPlayer'
import ActionPlanTable from '@/components/ActionPlanTable'
import { Spinner } from '@/components/ui/spinner'
import MarkdownDisplay from '@/components/MarkdownDisplay'
import { useState } from 'react'
import * as api from '@/services/api'
import type { AnalysisStepResult } from '@/types'
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@/components/ui/select'
import { usePromptFlows } from '@/hooks/usePromptFlows'

const StepItem: React.FC<{ step: AnalysisStepResult }> = ({ step }) => {
  const [isEditing, setIsEditing] = useState(false)
  const [draft, setDraft] = useState(step.content || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onSave = async () => {
    setSaving(true)
    setError(null)
    try {
      await api.updateStepResult(step.id, draft)
      // Update local state post-save
      step.content = draft
      setIsEditing(false)
    } catch (e: any) {
      setError(e?.message || 'Erreur lors de la sauvegarde')
    } finally {
      setSaving(false)
    }
  }

  if (step.status === 'PENDING' || step.status === 'IN_PROGRESS') {
    return (
      <div className="space-y-2">
        <div className="text-sm font-medium">{step.step_name}</div>
        <div className="inline-flex items-center gap-2 text-sm text-muted-foreground">
          <LoaderCircle className="h-4 w-4 animate-spin" /> En cours...
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">{step.step_name}</div>
        <div className="flex gap-2">
          {isEditing ? (
            <>
              <Button size="sm" onClick={onSave} disabled={saving}>
                {saving ? (
                  <span className="inline-flex items-center gap-2"><LoaderCircle className="h-4 w-4 animate-spin" /> Enregistrement...</span>
                ) : (
                  'Enregistrer'
                )}
              </Button>
              <Button size="sm" variant="outline" onClick={() => { setIsEditing(false); setDraft(step.content || '') }}>Annuler</Button>
            </>
          ) : (
            <Button size="sm" variant="outline" onClick={() => setIsEditing(true)}>Modifier</Button>
          )}
        </div>
      </div>
      {error && <div className="text-sm text-destructive">{error}</div>}
      {isEditing ? (
        <Textarea value={draft} onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setDraft(e.target.value)} className="min-h-40" />
      ) : step.status === 'COMPLETED' && step.content ? (
        <MarkdownDisplay content={step.content} />
      ) : (
        <div className="text-sm text-muted-foreground">Aucun contenu.</div>
      )}
    </div>
  )
}

const AnalysisDetailPage: React.FC = () => {
  const { analysisId } = useParams<{ analysisId: string }>()
  const { flows, isLoading: isLoadingFlows } = usePromptFlows()

  const {
    analysisData,
    currentPeople,
    isLoading,
    isRerunning,
    rerunAnalysis,
    selectVersion,
    actionPlan,
    editedTranscript,
    setEditedTranscript,
    saveTranscript,
    selectedFlowForRerun,
    setSelectedFlowForRerun,
  } = useAnalysisDetail(analysisId)

  const transcriptRef = useRef<HTMLElement | null>(null)
  const scrollToRerunSection = useCallback(() => {
    document.getElementById('rerun-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  const handleActionItemClick = useCallback((interval: { start: number; end: number }) => {
    if (!transcriptRef.current || !analysisData?.transcript) return

    // Clear previous highlight by resetting to raw text first
    const codeEl = transcriptRef.current as HTMLElement

    // Always start from the raw transcript to avoid nesting spans
    const rawText = analysisData.transcript

    const start = Math.max(0, Math.min(interval.start, rawText.length))
    const end = Math.max(start, Math.min(interval.end, rawText.length))

    const before = rawText.slice(0, start)
    const middle = rawText.slice(start, end)
    const after = rawText.slice(end)

    const escapeHtml = (s: string) => s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')

    const newHtml = `${escapeHtml(before)}<span class="highlighted-text" id="highlighted-span">${escapeHtml(middle)}</span>${escapeHtml(after)}`

    codeEl.innerHTML = newHtml

    document.getElementById('highlighted-span')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [analysisData?.transcript])

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

      {analysisData.status === 'COMPLETED' ? (
        <ActionPlanTable actionPlan={actionPlan} onItemClick={handleActionItemClick} />
      ) : (
        <Card>
          <CardContent>
            <div className="text-sm text-muted-foreground p-4">Plan d'action disponible après l'analyse.</div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Panneau de gauche: Transcription */}
        <Card>
          <CardHeader>
            <CardTitle>Transcription</CardTitle>
          </CardHeader>
          <CardContent>
            {isTranscribing ? (
              <Spinner text="Transcription en cours avec Azure AI Speech..." />
            ) : (
              <div className="space-y-3">
                <Textarea
                  value={editedTranscript}
                  onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setEditedTranscript(e.target.value)}
                  className="min-h-[40vh]"
                />
                <div className="flex gap-2">
                  <Button onClick={saveTranscript} disabled={!editedTranscript || editedTranscript === analysisData.transcript}>Enregistrer la transcription</Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

      {/* Panneau de droite */}
        <div className="space-y-6">
          {/* Rerun */}
          <Card id="rerun-section">
            <CardHeader>
              <CardTitle className="text-base">Relancer l'analyse</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Select
                value={selectedFlowForRerun}
                onValueChange={setSelectedFlowForRerun}
                disabled={isLoadingFlows}
              >
                <SelectTrigger aria-label="Sélectionner un flux de prompt">
                  <SelectValue placeholder={isLoadingFlows ? 'Chargement…' : 'Sélectionner un flux'} />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectLabel>Flux disponibles</SelectLabel>
                    {flows.length === 0 ? (
                      <SelectItem disabled value="__none__">Aucun flux</SelectItem>
                    ) : (
                      flows.map((flow) => {
                        const isPredefined = flow.id.startsWith('predefined_')
                        const label = isPredefined ? `Prédéfini · ${flow.name}` : flow.name
                        return (
                          <SelectItem key={flow.id} value={flow.id}>{label}</SelectItem>
                        )
                      })
                    )}
                  </SelectGroup>
                </SelectContent>
              </Select>
              <Button onClick={rerunAnalysis} disabled={isRerunning || !selectedFlowForRerun}>
                {isRerunning ? (
                  <span className="inline-flex items-center gap-2">
                    <LoaderCircle className="h-4 w-4 animate-spin" /> Relance...
                  </span>
                ) : (
                  "Relancer l'analyse"
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Résultats par étapes */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Résultats par étapes</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isAnalyzing && (
                <Spinner text="L'IA analyse la transcription..." />
              )}
              {analysisData.versions && analysisData.versions.length > 0 ? (
                (() => {
                  const latestVersion = analysisData.versions[0]
                  return (
                    <div className="space-y-6">
                      {latestVersion.steps && latestVersion.steps.length > 0 ? (
                        latestVersion.steps.map((step) => (
                          <StepItem key={step.id} step={step} />
                        ))
                      ) : (
                        <div className="text-sm text-muted-foreground">Aucune étape pour cette version.</div>
                      )}
                    </div>
                  )
                })()
              ) : (
                <div className="text-sm text-muted-foreground">Aucune version disponible.</div>
              )}
            </CardContent>
          </Card>

          {/* Historique des versions */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Historique des versions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {(analysisData.versions || []).map((v: AnalysisVersion) => (
                  <button
                    key={v.id}
                    className="w-full text-left p-3 rounded-lg border hover:bg-muted/50"
                    onClick={() => selectVersion(v)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="font-medium">
                        {new Date(v.created_at).toLocaleString()}
                      </div>
                      <div className="text-xs text-muted-foreground truncate max-w-[50%]">
                        {v.prompt_used}
                      </div>
                    </div>
                    {v.people_involved && (
                      <div className="text-xs text-muted-foreground mt-1 line-clamp-2 whitespace-pre-wrap">
                        {v.people_involved}
                      </div>
                    )}
                  </button>
                ))}
                {(!analysisData.versions || analysisData.versions.length === 0) && (
                  <div className="text-sm text-muted-foreground">Aucune version enregistrée.</div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

export default AnalysisDetailPage
