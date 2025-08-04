// Types pour l'API
export interface PredefinedPrompts {
  [key: string]: string;
}

// URL de base pour l'API
const API_BASE_URL = '/api';

/**
 * Récupère les prompts prédéfinis depuis le backend
 * @returns Un objet contenant les prompts prédéfinis
 */
export async function getPrompts(): Promise<PredefinedPrompts> {
  const response = await fetch(`${API_BASE_URL}/prompts`);
  if (!response.ok) {
    throw new Error(`Erreur HTTP: ${response.status}`);
  }
  return response.json();
}

/**
 * Envoie un fichier audio pour traitement avec un prompt spécifique
 * @param file Le fichier audio à traiter
 * @param prompt Le prompt à utiliser pour l'analyse
 * @returns Un objet contenant l'ID de la tâche
 */
export async function processAudio(file: File, prompt: string): Promise<{ task_id: string }> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('prompt', prompt);
  
  const response = await fetch(`${API_BASE_URL}/process-audio/`, {
    method: 'POST',
    body: formData,
  });
  
  if (!response.ok) {
    throw new Error(`Erreur HTTP: ${response.status}`);
  }
  
  return response.json();
}

/**
 * Récupère le statut d'une tâche de traitement
 * @param taskId L'ID de la tâche à vérifier
 * @returns Un objet contenant le statut de la tâche
 */
export async function getTaskStatus(taskId: string): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE_URL}/status/${taskId}`);
  if (!response.ok) {
    throw new Error(`Erreur HTTP: ${response.status}`);
  }
  return response.json();
}

/**
 * Récupère le fichier résultat ou transcription d'une tâche terminée
 * @param taskId L'ID de la tâche
 * @param type Le type de fichier à récupérer ('result' ou 'transcript')
 * @returns Le contenu du fichier texte
 */
export async function getResultFile(taskId: string, type: 'result' | 'transcript'): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/${type}/${taskId}`);
  if (!response.ok) {
    throw new Error(`Erreur HTTP: ${response.status}`);
  }
  return response.text();
}