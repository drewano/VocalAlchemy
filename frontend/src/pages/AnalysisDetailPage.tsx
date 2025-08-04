import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import * as api from '@/services/api';
import type { AnalysisDetail, AnalysisVersion } from '@/services/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { LoaderCircle } from 'lucide-react';

const AnalysisDetailPage: React.FC = () => {
  const { analysisId } = useParams<{ analysisId: string }>();

  const [analysisData, setAnalysisData] = useState<AnalysisDetail | null>(null);
  const [currentPrompt, setCurrentPrompt] = useState<string>('');
  const [currentAnalysis, setCurrentAnalysis] = useState<string>('');
  const [currentPeople, setCurrentPeople] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRerunning, setIsRerunning] = useState<boolean>(false);

  useEffect(() => {
    const load = async () => {
      if (!analysisId) return;
      setIsLoading(true);
      try {
        const data = await api.getAnalysisDetail(analysisId);
        setAnalysisData(data);
        setCurrentPrompt(data.prompt || '');
        setCurrentAnalysis(data.latest_analysis || 'Aucune analyse disponible.');
        setCurrentPeople(data.people_involved || 'Non spécifié');
      } catch (e) {
        console.error('Failed to load analysis detail', e);
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [analysisId]);

  const handleRerun = async () => {
    if (!analysisId || !currentPrompt.trim()) return;
    setIsRerunning(true);
    try {
      await api.rerunAnalysis(analysisId, currentPrompt);
      // success toast could be added here with sonner
      const data = await api.getAnalysisDetail(analysisId);
      setAnalysisData(data);
      setCurrentAnalysis(data.latest_analysis || 'Aucune analyse disponible.');
      setCurrentPeople(data.people_involved || 'Non spécifié');
    } catch (e) {
      console.error('Failed to rerun analysis', e);
    } finally {
      setIsRerunning(false);
    }
  };

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
    );
  }

  if (!analysisData) {
    return (
      <div className="container mx-auto py-8">
        <Card>
          <CardHeader>
            <CardTitle>Analyse introuvable</CardTitle>
          </CardHeader>
          <CardContent>
            Impossible de charger les détails de l'analyse.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 space-y-8">
      {/* Panneau du haut */}
      <Card>
        <CardHeader>
          <CardTitle>Détails de l'analyse</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <div className="text-sm text-muted-foreground">Fichier</div>
              <div className="font-medium break-all">{analysisData.filename}</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Créée le</div>
              <div className="font-medium">{new Date(analysisData.created_at).toLocaleString()}</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Personnes concernées</div>
              <div className="font-medium whitespace-pre-wrap">{currentPeople || '—'}</div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Panneau de gauche: Transcription */}
        <Card>
          <CardHeader>
            <CardTitle>Transcription</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="bg-muted/50 p-4 rounded-lg max-h-[70vh] overflow-y-auto">
              <code className="whitespace-pre-wrap">{analysisData.transcript}</code>
            </pre>
          </CardContent>
        </Card>

        {/* Panneau de droite */}
        <div className="space-y-6">
          {/* Rerun */}
          <Card>
            <CardHeader>
              <CardTitle>Relancer l'analyse</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                value={currentPrompt}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setCurrentPrompt(e.target.value)}
                placeholder="Saisissez un nouveau prompt..."
                className="min-h-24"
              />
              <Button onClick={handleRerun} disabled={isRerunning || !currentPrompt.trim()}>
                {isRerunning ? (
                  <span className="inline-flex items-center gap-2"><LoaderCircle className="h-4 w-4 animate-spin" /> Relance...</span>
                ) : (
                  "Relancer l'analyse"
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Résultat courant */}
          <Card>
            <CardHeader>
              <CardTitle>Résultat de l'analyse</CardTitle>
            </CardHeader>
            <CardContent>
              {currentAnalysis ? (
                <pre className="bg-muted/50 p-4 rounded-lg max-h-[40vh] overflow-y-auto">
                  <code className="whitespace-pre-wrap">{currentAnalysis}</code>
                </pre>
              ) : (
                <div className="text-sm text-muted-foreground">Aucun résultat pour l'instant.</div>
              )}
            </CardContent>
          </Card>

          {/* Historique des versions */}
          <Card>
            <CardHeader>
              <CardTitle>Historique des versions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {(analysisData.versions || []).map((v: AnalysisVersion) => (
                  <button
                    key={v.id}
                    className="w-full text-left p-3 rounded-lg border hover:bg-muted/50"
                    onClick={async () => {
                      setCurrentPeople(v.people_involved || 'Non spécifié');
                      setCurrentPrompt(v.prompt_used || '');
                      try {
                        const content = await api.getVersionResult(v.id);
                        setCurrentAnalysis(content || 'Aucune analyse disponible.');
                      } catch (e) {
                        console.error('Failed to load version result', e);
                      }
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <div className="font-medium">{new Date(v.created_at).toLocaleString()}</div>
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
  );
};

export default AnalysisDetailPage;
