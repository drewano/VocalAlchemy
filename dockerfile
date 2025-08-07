# === ÉTAPE 1: Build du Frontend (React/Vite) ===
# On utilise une image Node.js légère (alpine) pour construire les fichiers statiques du frontend.
# On la nomme "frontend-builder" pour pouvoir y faire référence plus tard.
FROM node:20-alpine AS frontend-builder

# On définit le répertoire de travail pour le frontend
WORKDIR /app/frontend

# On copie d'abord les fichiers de dépendances pour profiter du cache Docker.
# Si ces fichiers ne changent pas, `npm install` ne sera pas ré-exécuté.
COPY frontend/package.json ./
# Utilisez `npm ci` pour une installation plus rapide et déterministe en CI/CD
RUN npm install

# On copie le reste du code source du frontend
COPY frontend/ ./

# On exécute la commande de build pour générer les fichiers statiques optimisés.
# Le résultat sera dans le dossier /app/frontend/dist/
RUN npm run build


# === ÉTAPE 2: Image Finale de Production (Python/FastAPI) ===
# On part d'une image Python 3.11 légère (slim).
FROM python:3.11-slim

# Variables d'environnement pour Python pour optimiser l'exécution dans un conteneur.
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Installation des dépendances système.
# ffmpeg est requis par pydub pour traiter les fichiers audio.
# Packages additionnels requis par le SDK Azure Speech (SSL, ALSA, GStreamer pour I/O audio).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libasound2 \
        ca-certificates \
        libssl3 \
        gstreamer1.0-alsa \
        gstreamer1.0-libav \
        gstreamer1.0-plugins-base \
        gstreamer1.0-plugins-good \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Définition du répertoire de travail dans l'image finale
WORKDIR /app

# Copie et installation des dépendances Python
# On copie uniquement requirements.txt d'abord pour le cache Docker.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source du backend
# On copie le dossier `src` du backend vers le dossier `/app/src` de l'image.
COPY backend/src ./src

# CRUCIAL : Copie des fichiers statiques du frontend (buildés à l'étape 1)
# On copie le contenu du dossier /app/frontend/dist de l'étape "frontend-builder"
# vers un dossier /app/static dans notre image finale.
# Votre `main.py` est configuré pour servir les fichiers de ce dossier.
COPY --from=frontend-builder /app/frontend/dist /app/static

# Création du répertoire 'uploads' que l'application utilise pour stocker les fichiers temporaires.
# L'application aura les droits pour écrire dans ce dossier à l'intérieur du conteneur.
RUN mkdir uploads

# Exposition du port sur lequel FastAPI va écouter.
EXPOSE 8000

# Commande pour démarrer l'application avec Uvicorn.
# --host 0.0.0.0 est nécessaire pour que le serveur soit accessible depuis l'extérieur du conteneur.
# Les variables d'environnement (clés API, etc.) seront injectées à l'exécution.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]