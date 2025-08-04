import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { LoaderCircle } from 'lucide-react';

interface StatusDisplayProps {
  status: string;
}

export function StatusDisplay({ status }: StatusDisplayProps) {
  // Normalise et supporte les statuts backend (PENDING, PROCESSING, COMPLETED, FAILED) + fallback legacy
  const normalized = (status || '').toUpperCase()

  const statusMessages: Record<string, string> = {
    PENDING: 'Mise en file et préparation... ',
    PROCESSING: 'Traitement en cours...',
    COMPLETED: 'Traitement terminé !',
    FAILED: 'Échec du traitement',
    // Fallbacks anciens libellés
    'DÉMARRÉ': 'Le traitement a démarré...',
    'TRANSCRIPTION EN COURS': "Transcription de l'audio...",
    'ANALYSE EN COURS': 'Analyse du contenu...',
    "GÉNÉRATION DU RAPPORT": 'Génération du rapport...',
  }

  const statusProgress: Record<string, number> = {
    PENDING: 15,
    PROCESSING: 60,
    COMPLETED: 100,
    FAILED: 100,
    'DÉMARRÉ': 10,
    'TRANSCRIPTION EN COURS': 40,
    'ANALYSE EN COURS': 70,
    "GÉNÉRATION DU RAPPORT": 90,
  }

  const displayMessage = statusMessages[normalized] || status
  const progressValue = statusProgress[normalized] ?? 75

  return (
    <Card>
      <CardHeader>
        <CardTitle>État du traitement</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col items-center justify-center space-y-4">
        <p className="text-center text-lg">{displayMessage}</p>
        <LoaderCircle className="h-16 w-16 animate-spin text-primary" />
        <Progress value={progressValue} className="w-full" />
      </CardContent>
    </Card>
  )
}
