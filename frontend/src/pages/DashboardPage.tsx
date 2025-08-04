import React, { useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import * as api from '@/services/api';
import AuthContext from '@/contexts/AuthContext';
import { UploadForm } from '@/components/UploadForm';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table';

interface AnalysisHistoryItem {
  id: string;
  filename: string;
  date: string;
  status: 'completed' | 'processing' | 'failed';
}

const DashboardPage: React.FC = () => {
  const [prompts, setPrompts] = useState<api.PredefinedPrompts>({});
  const [history, setHistory] = useState<AnalysisHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const authContext = useContext(AuthContext);
  const navigate = useNavigate();

  if (!authContext) {
    throw new Error('DashboardPage must be used within an AuthProvider');
  }

  const { user, logout } = authContext;

  // Récupérer les prompts prédéfinis au chargement
  useEffect(() => {
    const fetchPrompts = async () => {
      try {
        const data = await api.getPrompts();
        setPrompts(data);
      } catch (err) {
        console.error('Erreur lors de la récupération des prompts:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPrompts();
  }, []);

  // Charger l'historique réel depuis le backend
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const items = await api.listAnalyses();
        const mapped: AnalysisHistoryItem[] = items.map(it => ({
          id: it.id,
          filename: it.filename || 'fichier',
          date: new Date(it.created_at).toLocaleString(),
          status: it.status === 'Terminé' ? 'completed' : it.status?.toLowerCase().includes('écou') || it.status?.toLowerCase().includes('transcription') || it.status?.toLowerCase().includes('analyse') ? 'processing' : it.status?.toLowerCase().includes('échoué') ? 'failed' : 'processing',
        }));
        setHistory(mapped);
      } catch (e) {
        console.error('Erreur chargement historique', e);
      }
    };
    loadHistory();
  }, []);

  const handleUploadSubmit = async (file: File, prompt: string) => {
    setIsSubmitting(true);
    try {
      const { task_id } = await api.processAudio(file, prompt);
      // Ajouter une entrée "en cours" immédiatement
      const newItem: AnalysisHistoryItem = {
        id: task_id,
        filename: file.name,
        date: new Date().toLocaleString(),
        status: 'processing'
      };
      setHistory(prev => [newItem, ...prev]);

      // Polling jusqu'à Terminé
      const poll = async () => {
        try {
          const st = await api.getTaskStatus(task_id);
          setHistory(prev => prev.map(h => h.id === task_id ? {
            ...h,
            status: st.status === 'Terminé' ? 'completed' : (st.status?.toLowerCase().includes('échoué') ? 'failed' : 'processing'),
          } : h));
          if (st.status !== 'Terminé' && !st.status?.toLowerCase().includes('échoué')) {
            setTimeout(poll, 1500);
          }
        } catch (e) {
          console.error('Polling status error', e);
          setTimeout(poll, 2000);
        }
      };
      poll();
    } catch (err) {
      console.error('Erreur lors de l\'analyse:', err);
      alert('Erreur lors de l\'analyse du fichier');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="container mx-auto py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Tableau de bord</h1>
        <div className="flex items-center gap-4">
          {user && <span className="text-sm">Connecté en tant que: {user.email}</span>}
          <Button variant="outline" onClick={handleLogout}>
            Déconnexion
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Formulaire d'upload */}
        <div>
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Nouvelle analyse</CardTitle>
              <CardDescription>
                Téléchargez un fichier audio pour lancer une nouvelle analyse
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-4">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : (
                <UploadForm 
                  prompts={prompts} 
                  onSubmit={handleUploadSubmit} 
                  isLoading={isSubmitting} 
                />
              )}
            </CardContent>
          </Card>
        </div>

        {/* Historique des analyses */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle>Historique des analyses</CardTitle>
              <CardDescription>
                Liste de vos analyses récentes
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Fichier</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Statut</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((item) => (
                    <TableRow key={item.id} className="cursor-pointer hover:bg-muted/40" onClick={() => window.open(`/api/result/${item.id}`, '_blank')}>
                      <TableCell className="font-medium">{item.filename}</TableCell>
                      <TableCell>{item.date}</TableCell>
                      <TableCell>
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          item.status === 'completed' 
                            ? 'bg-green-100 text-green-800' 
                            : item.status === 'failed' 
                              ? 'bg-red-100 text-red-800' 
                              : 'bg-yellow-100 text-yellow-800'
                        }`}>
                          {item.status === 'completed' 
                            ? 'Terminé' 
                            : item.status === 'failed' 
                              ? 'Échoué' 
                              : 'En cours'}
                        </span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;