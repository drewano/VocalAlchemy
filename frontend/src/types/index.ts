// Central API/Application types

export interface PredefinedPrompts {
  [key: string]: string
}

export interface UserPrompt {
  id: number
  name: string
  content: string
}

export type AnalysisStatus =
  | 'PENDING'
  | 'TRANSCRIPTION_IN_PROGRESS'
  | 'ANALYSIS_PENDING'
  | 'ANALYSIS_IN_PROGRESS'
  | 'COMPLETED'
  | 'TRANSCRIPTION_FAILED'
  | 'ANALYSIS_FAILED'

export type AnalysisSummary = {
  id: string
  status: AnalysisStatus
  created_at: string
  filename: string
  transcript_snippet?: string
  analysis_snippet?: string
}

export interface AnalysisVersion {
  id: string
  prompt_used: string
  created_at: string
  people_involved: string | null
}

export interface ActionPlanItemAttributes {
  topic?: string
  responsible?: string
  assigned_by?: string
  participants?: string[]
  deadline?: string
}

export interface ActionPlanItem {
  extraction_class: string
  extraction_text: string
  attributes: ActionPlanItemAttributes
  char_interval?: { start: number; end: number } | null
}

export interface AnalysisDetail {
  id: string
  status: AnalysisStatus
  created_at: string
  filename: string
  prompt: string | null
  transcript: string
  latest_analysis: string | null
  versions: AnalysisVersion[]
  people_involved: string | null
  action_plan?: ActionPlanItem[] | null
}

export interface AnalysisListResponse {
  items: AnalysisSummary[]
  total: number
}

export interface AnalysisStatusResponse {
  id: string;
  status: AnalysisStatus;
}