import { useState } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { PredefinedPrompts } from '@/services/api';

interface UploadFormProps {
  prompts: PredefinedPrompts;
  onSubmit: (file: File, prompt: string) => void;
  isLoading: boolean;
}

export function UploadForm({ prompts, onSubmit, isLoading }: UploadFormProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedPrompt, setSelectedPrompt] = useState<string>('');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handlePromptChange = (value: string) => {
    setSelectedPrompt(value);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedFile && selectedPrompt) {
      onSubmit(selectedFile, selectedPrompt);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Télécharger un fichier audio</CardTitle>
        <CardDescription>
          Sélectionnez un fichier audio et choisissez le type d'analyse à effectuer
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="audio-file">Fichier audio</Label>
            <Input
              id="audio-file"
              type="file"
              accept="audio/*"
              onChange={handleFileChange}
              disabled={isLoading}
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="prompt-select">Type d'analyse</Label>
            <Select value={selectedPrompt} onValueChange={handlePromptChange} disabled={isLoading}>
              <SelectTrigger id="prompt-select">
                <SelectValue placeholder="Sélectionnez un type d'analyse" />
              </SelectTrigger>
              <SelectContent>
                {Object.keys(prompts).map((promptKey) => (
                  <SelectItem key={promptKey} value={promptKey}>
                    {promptKey}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          
          <Button 
            type="submit" 
            disabled={isLoading || !selectedFile || !selectedPrompt}
            className="w-full"
          >
            {isLoading ? (
              <>
                <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
                Analyse en cours...
              </>
            ) : (
              'Analyser'
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}