import axios from 'axios'
import type { PredefinedPrompts, AnalysisDetail, AnalysisListResponse, AnalysisStatusResponse } from '@/types'

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
 * Initie un upload de fichier audio en deux étapes
 * @param filename Le nom du fichier à uploader
 * @returns Un objet contenant l'URL SAS, le nom du blob et l'ID de l'analyse
 */
export async function initiateUpload(filename: string): Promise<{ sasUrl: string, blobName: string, analysisId: string }> {
  const response = await api.post('/analysis/initiate-upload/', { filename })
  return {
    sasUrl: response.data.sas_url,
    blobName: response.data.blob_name,
    analysisId: response.data.analysis_id
  }
}

/**
 * Upload un fichier directement vers Azure Blob Storage via URL SAS
 * @param sasUrl L'URL SAS pour l'upload
 * @param file Le fichier à uploader
 */
export async function uploadFileToSasUrl(sasUrl: string, file: File): Promise<void> {
  await axios.put(sasUrl, file, {
    headers: {
      'x-ms-blob-type': 'BlockBlob',
      'Content-Type': file.type || 'application/octet-stream',
    },
  })
}

/**
 * Finalise l'upload et démarre le traitement
 * @param analysisId L'ID de l'analyse créée lors de l'initiation
 * @param prompt Le prompt à utiliser pour l'analyse
 */
export async function finalizeUpload(analysisId: string, promptFlowId: string): Promise<void> {
  await api.post('/analysis/finalize-upload/', {
    analysis_id: analysisId,
    prompt_flow_id: promptFlowId,
  })
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

export async function updateTranscript(analysisId: string, content: string): Promise<void> {
  await api.put(`/analysis/${analysisId}/transcript`, { content })
}

export async function updateStepResult(stepResultId: string, content: string): Promise<void> {
  await api.put(`/analysis/step-result/${stepResultId}`, { content })
}

export async function rerunAnalysis(analysisId: string, promptFlowId: string): Promise<any> {
  const res = await api.post(`/analysis/rerun/${analysisId}`, {
    analysis_id: analysisId,
    prompt_flow_id: promptFlowId,
  })
  return res.data
}

export async function getVersionResult(versionId: string): Promise<string> {
  const res = await api.get(`/result/version/${versionId}`, { responseType: 'text' })
  return res.data
}

export async function deleteAnalysis(analysisId: string): Promise<void> {
  await api.delete(`/analysis/${analysisId}`)
}

export async function checkAnalysisStatus(analysisId: string): Promise<AnalysisStatusResponse> {
  const res = await api.get(`/analysis/status/${analysisId}`)
  return res.data
}

export async function renameAnalysis(analysisId: string, newName: string): Promise<void> {
  await api.patch(`/analysis/${analysisId}/rename`, { filename: newName })
}

/**
 * Relance uniquement la transcription d'une analyse
 * @param analysisId L'ID de l'analyse à retranscrire
 */
export async function relaunchTranscription(analysisId: string): Promise<void> {
  await api.post(`/analysis/${analysisId}/retranscribe`)
}

/**
 * Relance une seule étape de l'analyse IA
 * @param stepResultId L'ID du résultat d'étape à relancer
 * @param newPromptContent Le nouveau contenu du prompt (optionnel)
 */
export async function relaunchAnalysisStep(stepResultId: string, newPromptContent?: string): Promise<void> {
  await api.post(`/analysis/step-result/${stepResultId}/rerun`, {
    new_prompt_content: newPromptContent
  })
}

/**
 * Télécharge un document Word contenant la transcription ou l'assemblage des résultats
 * @param analysisId L'ID de l'analyse
 * @param type Le type de document à télécharger ('transcription' ou 'assembly')
 * @returns Un Blob contenant le document Word
 */
export async function downloadWordDocument(analysisId: string, type: 'transcription' | 'assembly'): Promise<Blob> {
  const response = await api.get(`/analysis/${analysisId}/download-word`, {
    params: { type },
    responseType: 'blob'
  })
  return response.data
}

// Récupère une URL SAS pour le fichier audio original
export async function getAudioFileSasUrl(analysisId: string): Promise<string> {
  const res = await api.get(`/analysis/audio/${analysisId}`)
  return res.data.url
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
  const params = new URLSearchParams()
  params.append('username', email) // Le backend attend 'username' pour l'email
  params.append('password', password)

  const response = await api.post('/users/token', params)

  return response.data
}

/**
 * Inscrit un nouvel utilisateur
 * @param email L'email de l'utilisateur
 * @param password Le mot de passe de l'utilisateur
 * @returns Un objet contenant les informations de l'utilisateur créé
 */
export async function signup(email: string, password: string): Promise<User> {
  const response = await api.post('/users/register', { email, password })
  return response.data
}