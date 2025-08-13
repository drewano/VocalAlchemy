// Central API/Application types

export interface User {
  id: number
  email: string
  is_admin: boolean
  status: string
}

export interface AdminUserView extends User {
  meeting_count: number
}

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

export interface AnalysisStepResult {
  id: string
  step_name: string
  step_order?: number
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED'
  content?: string | null
}

export interface AnalysisVersion {
  id: string
  prompt_used: string
  created_at: string
  people_involved: string | null
  steps: AnalysisStepResult[]
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
  error_message?: string | null
}

export interface AnalysisListResponse {
  items: AnalysisSummary[]
  total: number
}

export interface AnalysisStatusResponse {
  id: string;
  status: AnalysisStatus;
}

// Prompt Flows
export interface PromptStep {
  id: string
  name: string
  content: string
  step_order: number
}

export interface PromptFlow {
  id: string
  name: string
  description: string | null
  steps: PromptStep[]
}

export interface PromptStepCreate {
  name: string
  content: string
  step_order: number
}

export interface PromptFlowCreate {
  name: string
  description?: string | null
  steps: PromptStepCreate[]
}

export interface PromptFlowUpdate {
  name?: string
  description?: string | null
  steps?: PromptStepCreate[]
}