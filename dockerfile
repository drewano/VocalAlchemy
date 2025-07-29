# Dockerfile

# --- Étape 1: Image de base ---
# Utilisation d'une image Python 3.11 légère (slim)
FROM python:3.11-slim

# --- Variables d'environnement ---
# Empêche Python de générer des fichiers .pyc
ENV PYTHONDONTWRITEBYTECODE 1
# Assure que les sorties (logs) sont envoyées directement au terminal sans buffer
ENV PYTHONUNBUFFERED 1

# --- Dépendances Système ---
# Met à jour les paquets et installe ffmpeg, qui est requis par pydub pour traiter divers formats audio.
# Nettoie ensuite le cache pour garder l'image légère.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# --- Répertoire de travail ---
# Définit le répertoire de travail dans le conteneur
WORKDIR /app

# --- Installation des dépendances Python ---
# Copie uniquement le fichier des dépendances pour profiter du cache Docker.
# Si requirements.txt ne change pas, cette étape ne sera pas ré-exécutée.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copie du code de l'application ---
# Copie les répertoires contenant le code source et les assets
COPY src ./src
COPY static ./static
COPY templates ./templates

# --- Création des répertoires d'exécution ---
# Crée le répertoire 'uploads' que l'application utilise pour stocker les fichiers temporaires
RUN mkdir uploads

# --- Exposition du port ---
# Informe Docker que le conteneur écoutera sur le port 8000
EXPOSE 8000

# --- Commande de démarrage ---
# Lance l'application avec Uvicorn.
# --host 0.0.0.0 est crucial pour que l'application soit accessible depuis l'extérieur du conteneur.
# Note : Les clés API (GLADIA_API_KEY, GOOGLE_API_KEY) doivent être fournies en tant que
# variables d'environnement lors de l'exécution du conteneur.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]