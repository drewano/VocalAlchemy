import { api } from '@/services/api'
import type { PromptFlow, PromptFlowCreate, PromptFlowUpdate } from '@/types'

export async function getPromptFlows(): Promise<PromptFlow[]> {
  const res = await api.get('/prompt-flows')
  return res.data
}

export async function getPromptFlow(id: string): Promise<PromptFlow> {
  const res = await api.get(`/prompt-flows/${id}`)
  return res.data
}

export async function createPromptFlow(data: PromptFlowCreate): Promise<PromptFlow> {
  const res = await api.post('/prompt-flows', data)
  return res.data
}

export async function updatePromptFlow(id: string, data: PromptFlowUpdate): Promise<PromptFlow> {
  const res = await api.put(`/prompt-flows/${id}`, data)
  return res.data
}

export async function deletePromptFlow(id: string): Promise<void> {
  await api.delete(`/prompt-flows/${id}`)
}


