import axios from 'axios'
import type { PredefinedPrompts, AnalysisDetail, AnalysisListResponse } from '@/types'

// Types locaux alignés avec AuthContext
interface User {
  id: number;
  email: string;
}

type LoginResponse = { access_token: string; token_type: string; user: User }

// Créer une instance axios de base
const api = axios.create({
  baseURL: '/api',
  withCredentials: true, // Si nécessaire pour les cookies
})

// Intercepteur pour ajouter automatiquement le token d'authentification à chaque requête
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers = config.headers || {}
    ;(config.headers as any).Authorization = `Bearer ${token}`
  }
  return config
})

// Intercepteur de réponse pour centraliser les erreurs
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status ?? 0
    const detail = error?.response?.data?.detail
    const message =
      (typeof detail === 'string' && detail) ||
      (Array.isArray(detail) && detail[0]?.msg) ||
      error?.message ||
      'Une erreur réseau est survenue.'

    const standardized = { message, status }
    return Promise.reject(standardized)
  }
)

export { api }

/**
 * Récupère les prompts prédéfinis depuis le backend
 * @returns Un objet contenant les prompts prédéfinis
 */
export async function getPrompts(): Promise<PredefinedPrompts> {
  const response = await api.get('/prompts')
  return response.data
}

/**
 * Envoie un fichier audio pour traitement avec un prompt spécifique
 * @param file Le fichier audio à traiter
 * @param prompt Le prompt à utiliser pour l'analyse
 * @returns Un objet contenant l'ID de la tâche
 */
export async function processAudio(file: File, prompt: string): Promise<{ analysis_id: string }> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('prompt', prompt)

  const response = await api.post('/analysis/process-audio/', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })

  return response.data
}

/**
 * Récupère le statut d'une tâche de traitement
 * @param taskId L'ID de la tâche à vérifier
 * @returns Un objet contenant le statut de la tâche
 */
export async function getTaskStatus(analysisId: string): Promise<{ status: string; has_result: boolean; has_transcript: boolean }> {
  const response = await api.get(`/analysis/status/${analysisId}`)
  return response.data
}

/**
 * Récupère le fichier résultat ou transcription d'une tâche terminée
 * @param taskId L'ID de la tâche
 * @param type Le type de fichier à récupérer ('result' ou 'transcript')
 * @returns Le contenu du fichier texte
 */
export async function getResultFile(analysisId: string, type: 'result' | 'transcript'): Promise<string> {
  const response = await api.get(`/analysis/${type}/${analysisId}`, { responseType: 'text' })
  return response.data
}

export async function listAnalyses({ page, pageSize }: { page: number; pageSize: number }): Promise<AnalysisListResponse> {
  const skip = Math.max(0, (page - 1) * pageSize)
  const limit = Math.max(1, pageSize)
  const res = await api.get('/analysis/list', { params: { skip, limit } })
  return res.data
}

export async function getAnalysisDetail(taskId: string): Promise<AnalysisDetail> {
  const res = await api.get(`/analysis/${taskId}`)
  return res.data
}

export async function rerunAnalysis(analysisId: string, prompt: string): Promise<any> {
  const formData = new FormData()
  formData.append('prompt', prompt)
  const res = await api.post(`/analysis/rerun/${analysisId}`, formData)
  return res.data
}

export async function getVersionResult(versionId: string): Promise<string> {
  const res = await api.get(`/result/version/${versionId}`, { responseType: 'text' })
  return res.data
}

export async function deleteAnalysis(analysisId: string): Promise<void> {
  await api.delete(`/analysis/${analysisId}`)
}

export async function renameAnalysis(analysisId: string, newName: string): Promise<void> {
  await api.patch(`/analysis/${analysisId}/rename`, { filename: newName })
}

// Fonction utilitaire pour construire l'URL du fichier audio (aucun appel axios)
export function getAudioFileUrl(analysisId: string): string {
  return `/api/analysis/audio/${analysisId}`
}

// Récupère le fichier audio (authentifié) en tant que Blob
export async function getAudioFileBlob(analysisId: string): Promise<Blob> {
  const res = await api.get(`/analysis/audio/${analysisId}`, { responseType: 'blob' })
  return res.data
}

// User prompts CRUD moved to prompts.api.ts

// Récupère l'utilisateur courant
export async function getMe(): Promise<User> {
  const res = await api.get('/users/me')
  return res.data
}

/**
 * Connecte un utilisateur
 * @param email L'email de l'utilisateur
 * @param password Le mot de passe de l'utilisateur
 * @returns Objet contenant token, type et user
 */
export async function login(email: string, password: string): Promise<LoginResponse> {
  const formData = new FormData()
  formData.append('username', email) // Le backend attend 'username' pour l'email
  formData.append('password', password)

  const response = await api.post('/users/token', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })

  return response.data
}

/**
 * Inscrit un nouvel utilisateur
 * @param email L'email de l'utilisateur
 * @param password Le mot de passe de l'utilisateur
 * @returns Un objet contenant le token d'accès
 */
export async function signup(email: string, password: string): Promise<{ access_token: string }> {
  const response = await api.post('/users/register', { email, password })
  return response.data
}