import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { LoaderCircle } from 'lucide-react';

interface StatusDisplayProps {
  status: string;
}

export function StatusDisplay({ status }: StatusDisplayProps) {
  // Messages d'état traduits
  const statusMessages: Record<string, string> = {
    'processing': 'Traitement en cours...',
    'Démarré': 'Le traitement a démarré...',
    'Transcription en cours': 'Transcription de l\'audio...',
    'Analyse en cours': 'Analyse du contenu...',
    'Génération du rapport': 'Génération du rapport...',
    'Terminé': 'Traitement terminé !',
  };

  // Progression approximative pour chaque statut
  const statusProgress: Record<string, number> = {
    'Démarré': 10,
    'Transcription en cours': 40,
    'Analyse en cours': 70,
    'Génération du rapport': 90,
    'Terminé': 100,
  };

  // Obtenir le message approprié ou utiliser le statut tel quel
  const displayMessage = statusMessages[status] || status;
  
  // Obtenir la progression appropriée ou 75 par défaut
  const progressValue = statusProgress[status] || 75;

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
  );
}