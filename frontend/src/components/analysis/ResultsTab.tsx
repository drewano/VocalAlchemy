import { Button } from '@/components/ui/button'
import { LoaderCircle } from 'lucide-react'
import type { AnalysisStepResult } from '@/types'
import StepResultItem from './StepResultItem'

interface ResultsTabProps {
  steps: AnalysisStepResult[]
  isAnalyzing: boolean
  onRerunWorkflow: () => void
  isRerunning: boolean
}

export function ResultsTab({ steps, isAnalyzing, onRerunWorkflow, isRerunning }: ResultsTabProps) {
  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Button 
          onClick={onRerunWorkflow} 
          disabled={isRerunning}
          variant="outline"
        >
          {isRerunning ? (
            <span className="inline-flex items-center gap-2">
              <LoaderCircle className="h-4 w-4 animate-spin" /> Relance...
            </span>
          ) : (
            'Relancer tout le workflow d\'analyse'
          )}
        </Button>
      </div>
      
      {isAnalyzing && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <LoaderCircle className="h-4 w-4 animate-spin" /> 
          L'IA analyse la transcription...
        </div>
      )}
      
      <div className="space-y-6">
        {steps && steps.length > 0 ? (
          steps.map((step) => (
            <StepResultItem key={step.id} step={step} />
          ))
        ) : (
          <div className="text-sm text-muted-foreground p-4 border border-dashed rounded-md">
            Aucune étape disponible. Les résultats des étapes apparaîtront ici une fois l'analyse terminée.
          </div>
        )}
      </div>
    </div>
  )
}

export default ResultsTab