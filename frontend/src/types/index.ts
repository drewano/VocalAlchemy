// Central API/Application types

export interface PredefinedPrompts {
  [key: string]: string
}

export interface UserPrompt {
  id: number
  name: string
  content: string
}

export type AnalysisSummary = {
  id: string
  status: string
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

export interface AnalysisDetail {
  id: string
  status: string
  created_at: string
  filename: string
  prompt: string | null
  transcript: string
  latest_analysis: string | null
  versions: AnalysisVersion[]
  people_involved: string | null
}

export interface AnalysisListResponse {
  items: AnalysisSummary[]
  total: number
}
