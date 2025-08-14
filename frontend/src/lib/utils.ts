import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import type { AnalysisStatus } from "@/types"
import { 
  CheckCircle, 
  XCircle, 
  Hourglass, 
  LoaderCircle 
} from "lucide-react"



export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function downloadTextAsFile(text: string, filename: string) {
  const blob = new Blob([text], { type: "text/plain" });
  downloadBlobAsFile(blob, filename);
}

export function downloadBlobAsFile(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

export function getStatusProps(status: AnalysisStatus): {
  label: string;
  variant: 'default' | 'secondary' | 'destructive' | 'outline';
  icon: React.ComponentType<{ className?: string }>;
  animated?: boolean;
} {
  switch (status) {
    case 'COMPLETED':
      return {
        label: 'Terminé',
        variant: 'default',
        icon: CheckCircle
      };
    case 'TRANSCRIPTION_IN_PROGRESS':
      return {
        label: 'Transcription...',
        variant: 'secondary',
        icon: LoaderCircle,
        animated: true
      };
    case 'ANALYSIS_IN_PROGRESS':
      return {
        label: 'Analyse IA...',
        variant: 'secondary',
        icon: LoaderCircle,
        animated: true
      };
    case 'PENDING':
      return {
        label: 'En attente',
        variant: 'outline',
        icon: Hourglass
      };
    case 'ANALYSIS_PENDING':
      return {
        label: 'Analyse en attente',
        variant: 'outline',
        icon: Hourglass
      };
    case 'TRANSCRIPTION_FAILED':
      return {
        label: 'Échec Transcription',
        variant: 'destructive',
        icon: XCircle
      };
    case 'ANALYSIS_FAILED':
      return {
        label: 'Échec Analyse',
        variant: 'destructive',
        icon: XCircle
      };
    default:
      return {
        label: status,
        variant: 'outline',
        icon: Hourglass
      };
  }
}
