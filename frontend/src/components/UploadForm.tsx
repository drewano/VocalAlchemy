import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Plus, CloudUpload, X } from 'lucide-react'
import type { PredefinedPrompts } from '@/types';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'

interface UploadFormProps {
  prompts: PredefinedPrompts;
  onSubmit: (file: File, prompt: string) => void;
  isLoading: boolean;
}

export function UploadForm({ prompts, onSubmit, isLoading }: UploadFormProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedPromptText, setSelectedPromptText] = useState<string>('');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handlePromptChange = (value: string) => {
    // value is now the textual prompt
    setSelectedPromptText(value);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedFile && selectedPromptText) {
      onSubmit(selectedFile, selectedPromptText);
    }
  };

  return (
    <Card>
      <CardHeader className="border-b">
        <div className="flex items-center gap-3">
          <div className="bg-blue-100 text-blue-600 p-3 rounded-full">
            <Plus className="w-5 h-5" />
          </div>
          <div>
            <CardTitle>Lancez une nouvelle analyse</CardTitle>
            <CardDescription>Téléchargez un fichier audio pour commencer.</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Drag & drop area or selected file info */}
          <div>
            <Label htmlFor="audio-file" className="mb-2 block">Fichier audio</Label>
            {selectedFile ? (
              <div className="flex items-center justify-between rounded-md border px-4 py-3 bg-muted/30">
                <div className="min-w-0">
                  <div className="font-medium truncate" title={selectedFile.name}>{selectedFile.name}</div>
                  <div className="text-xs text-muted-foreground">{(selectedFile.size / 1024 / 1024).toFixed(2)} Mo</div>
                </div>
                <Button type="button" variant="ghost" size="icon" onClick={() => setSelectedFile(null)} aria-label="Retirer le fichier">
                  <X className="size-4" />
                </Button>
              </div>
            ) : (
              <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-dashed rounded-md">
                <div className="space-y-1 text-center">
                  <CloudUpload className="mx-auto h-8 w-8 text-muted-foreground" />
                  <div className="flex text-sm text-muted-foreground">
                    <label
                      htmlFor="audio-file"
                      className="relative cursor-pointer rounded-md font-semibold text-primary focus-within:outline-none focus-within:ring-2 focus-within:ring-primary focus-within:ring-offset-2"
                    >
                      <span>Téléchargez un fichier</span>
                      <input
                        id="audio-file"
                        name="audio-file"
                        type="file"
                        accept="audio/*"
                        className="sr-only"
                        onChange={handleFileChange}
                        disabled={isLoading}
                      />
                    </label>
                    <p className="pl-1">ou glissez-déposez</p>
                  </div>
                  <p className="text-xs text-muted-foreground">MP3, WAV, M4A jusqu'à 100MB</p>
                </div>
              </div>
            )}
          </div>

          {/* Select full width */}
          <div>
            <Label htmlFor="prompt-select" className="mb-2 block">Type d'analyse</Label>
            <Select value={selectedPromptText} onValueChange={handlePromptChange} disabled={isLoading}>
              <SelectTrigger id="prompt-select" className="w-full">
                <SelectValue placeholder="Sélectionnez un type d'analyse" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(prompts).map(([name, content]) => (
                  <SelectItem key={name} value={content}>
                    {name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Submit button */}
          <Button
            type="submit"
            disabled={isLoading || !selectedFile || !selectedPromptText}
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
