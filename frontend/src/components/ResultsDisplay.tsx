import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Download } from 'lucide-react';
import { downloadTextAsFile } from '@/lib/utils';

interface ResultsDisplayProps {
  analysis: string;
  transcription: string;
  taskId: string;
}

export function ResultsDisplay({ analysis, transcription, taskId }: ResultsDisplayProps) {
  const handleDownloadReport = () => {
    downloadTextAsFile(analysis, `rapport-${taskId}.md`);
  };

  const handleDownloadTranscription = () => {
    downloadTextAsFile(transcription, `transcription-${taskId}.txt`);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Résultats de l'analyse</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="analysis" className="w-full">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6 flex-wrap">
            <TabsList>
              <TabsTrigger value="analysis">Analyse IA</TabsTrigger>
              <TabsTrigger value="transcription">Transcription brute</TabsTrigger>
            </TabsList>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleDownloadReport}>
                <Download className="mr-2 h-4 w-4" />
                Télécharger rapport
              </Button>
              <Button variant="outline" size="sm" onClick={handleDownloadTranscription}>
                <Download className="mr-2 h-4 w-4" />
                Télécharger transcription
              </Button>
            </div>
          </div>
          <TabsContent value="analysis" className="mt-0">
            <pre className="bg-muted/50 p-4 rounded-lg max-h-96 overflow-y-auto">
              <code className="whitespace-pre-wrap">{analysis}</code>
            </pre>
          </TabsContent>
          <TabsContent value="transcription" className="mt-0">
            <pre className="bg-muted/50 p-4 rounded-lg max-h-96 overflow-y-auto">
              <code className="whitespace-pre-wrap">{transcription}</code>
            </pre>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}