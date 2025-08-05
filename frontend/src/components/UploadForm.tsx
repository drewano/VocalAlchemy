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
import { Plus, CloudUpload } from 'lucide-react'
import type { PredefinedPrompts } from '@/types';

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
    <div className="bg-white rounded-xl shadow-sm p-8">
      {/* Header */}
      <div className="flex items-center mb-6">
        <div className="bg-blue-100 text-blue-600 p-3 rounded-full mr-4">
          <Plus className="w-5 h-5" />
        </div>
        <div>
          <h3 className="text-lg font-semibold">Lancez une nouvelle analyse</h3>
          <p className="text-sm text-gray-600">Téléchargez un fichier audio pour commencer.</p>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Drag & drop area */}
        <div>
          <Label htmlFor="audio-file" className="mb-2 block">Fichier audio</Label>
          <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-gray-300 border-dashed rounded-md">
            <div className="space-y-1 text-center">
              <CloudUpload className="mx-auto h-8 w-8 text-gray-400" />
              <div className="flex text-sm text-gray-600">
                <label
                  htmlFor="audio-file"
                  className="relative cursor-pointer rounded-md bg-white font-semibold text-blue-600 hover:text-blue-500 focus-within:outline-none focus-within:ring-2 focus-within:ring-blue-600 focus-within:ring-offset-2"
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
              <p className="text-xs text-gray-500">MP3, WAV, M4A jusqu'à 100MB</p>
            </div>
          </div>
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
          className="w-full bg-blue-600 hover:bg-blue-700 text-white"
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
    </div>
  );
}