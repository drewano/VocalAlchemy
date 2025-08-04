import { useState, useEffect } from 'react';
import './App.css';
import * as api from './services/api';
import { UploadForm } from './components/UploadForm';
import { StatusDisplay } from './components/StatusDisplay';
import { ResultsDisplay } from './components/ResultsDisplay';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { ModeToggle } from '@/components/mode-toggle';

type TaskStatus = 'idle' | 'processing' | 'complete' | string;

function App() {
  const [prompts, setPrompts] = useState<api.PredefinedPrompts | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<TaskStatus>('idle');
  const [analysisResult, setAnalysisResult] = useState<string | null>(null);
  const [transcription, setTranscription] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPrompts = async () => {
      try {
        const promptsData = await api.getPrompts();
        setPrompts(promptsData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Erreur inconnue lors du chargement des prompts');
      }
    };

    fetchPrompts();
  }, []);

  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null;

    const pollTaskStatus = async () => {
      if (taskId && (status === 'processing' || (typeof status === 'string' && !status.startsWith('Terminé')))) {
        try {
          const taskStatus = await api.getTaskStatus(taskId);
          setStatus(taskStatus.status);

          if (taskStatus.status === 'Terminé') {
            if (intervalId) {
              clearInterval(intervalId);
            }

            // Récupérer les résultats
            try {
              const [resultData, transcriptData] = await Promise.all([
                api.getResultFile(taskId, 'result'),
                api.getResultFile(taskId, 'transcript')
              ]);
              
              setAnalysisResult(resultData);
              setTranscription(transcriptData);
              setStatus('complete');
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Erreur lors de la récupération des résultats');
              setStatus('idle');
            }
          }
        } catch (err) {
          if (intervalId) {
            clearInterval(intervalId);
          }
          setError(err instanceof Error ? err.message : 'Erreur lors de la vérification du statut');
          setStatus('idle');
        }
      }
    };

    if (taskId && status !== 'idle' && status !== 'complete') {
      // Appel immédiat
      pollTaskStatus();
      // Polling toutes les 3 secondes
      intervalId = setInterval(pollTaskStatus, 3000);
    }

    // Nettoyage de l'intervalle lors du démontage ou changement de dépendances
    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [taskId, status]);

  const handleSubmit = async (file: File, prompt: string) => {
    try {
      setStatus('processing');
      const response = await api.processAudio(file, prompt);
      setTaskId(response.task_id);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inconnue lors du traitement du fichier');
      setStatus('idle');
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <header className="w-full">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <div className="text-2xl font-bold">Audio Analyzer AI</div>
          <ModeToggle />
        </div>
      </header>
      <main className="flex-1 flex flex-col items-center p-4 sm:p-8">
        <div className="w-full max-w-3xl">
          <h1 className="text-2xl font-bold mb-4">Analyseur Audio IA</h1>
          <p className="text-lg mb-8">
            Téléversez un fichier audio pour obtenir une synthèse, une analyse de sentiment ou une extraction d'entités.
          </p>
          
          {error && (
            <Card className="mb-6 border-destructive">
              <CardHeader>
                <CardTitle className="text-destructive">Erreur</CardTitle>
              </CardHeader>
              <CardContent>
                <p>{error}</p>
              </CardContent>
            </Card>
          )}
          
          {status === 'idle' && prompts && (
            <UploadForm 
              prompts={prompts} 
              onSubmit={handleSubmit} 
              isLoading={status !== 'idle' && status !== 'complete'} 
            />
          )}
          
          {(status !== 'idle' && status !== 'complete') && (
            <StatusDisplay status={status} />
          )}
          
          {status === 'complete' && analysisResult && transcription && taskId && (
            <ResultsDisplay 
              analysis={analysisResult} 
              transcription={transcription} 
              taskId={taskId}
            />
          )}
        </div>
      </main>
    </div>
  )
}

export default App