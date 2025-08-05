import { api } from './api'
import type { UserPrompt } from '@/types'

// User prompts CRUD isolated in this module for maintainability
export async function getUserPrompts(): Promise<UserPrompt[]> {
  const res = await api.get('/user-prompts')
  return res.data
}

export async function createUserPrompt(data: { name: string; content: string }): Promise<UserPrompt> {
  const res = await api.post('/user-prompts', data)
  return res.data
}

export async function updateUserPrompt(id: number, data: { name: string; content: string }): Promise<UserPrompt> {
  const res = await api.put(`/user-prompts/${id}`, data)
  return res.data
}

export async function deleteUserPrompt(id: number): Promise<void> {
  await api.delete(`/user-prompts/${id}`)
}
