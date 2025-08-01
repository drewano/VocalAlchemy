# === Étape 1: Build du Frontend (React/Vite) ===
# On utilise une image Node.js légère (alpine) pour construire les fichiers statiques du frontend.
# On la nomme "frontend-builder" pour pouvoir y faire référence plus tard.
FROM node:20-alpine AS frontend-builder

# On définit le répertoire de travail
WORKDIR /app/frontend

# On copie d'abord package.json pour profiter du cache Docker.
# Si ce fichier ne change pas, `npm install` ne sera pas ré-exécuté.
COPY frontend/package.json .
RUN npm install

# On copie le reste du code source du frontend
COPY frontend/ .

# On exécute la commande de build pour générer les fichiers statiques optimisés.
# Le résultat sera dans le dossier /app/frontend/dist/
RUN npm run build


# === Étape 2: Image Finale de Production (Python/FastAPI) ===
# On part d'une image Python 3.11 légère.
FROM python:3.11-slim

# Variables d'environnement pour Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Installation des dépendances système.
# ffmpeg est requis par pydub pour traiter les fichiers audio.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Définition du répertoire de travail
WORKDIR /app

# Copie et installation des dépendances Python
# On copie uniquement requirements.txt d'abord pour le cache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source du backend
COPY backend/src ./src

# CRUCIAL: Copie des fichiers statiques du frontend (buildés à l'étape 1)
# On copie le contenu du dossier /app/frontend/dist de l'étape "frontend-builder"
# vers un dossier /app/static dans notre image finale.
COPY --from=frontend-builder /app/frontend/dist /app/static

# Création du répertoire 'uploads' que l'application utilise.
RUN mkdir uploads

# Exposition du port sur lequel FastAPI va écouter
EXPOSE 8000

# Commande pour démarrer l'application avec Uvicorn.
# --host 0.0.0.0 est nécessaire pour que le serveur soit accessible depuis l'extérieur du conteneur.
# NOTE: Les clés API (GLADIA_API_KEY, GOOGLE_API_KEY) doivent être fournies comme variables
# d'environnement lors de l'exécution du conteneur (ex: via un fichier .env et docker-compose).
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]