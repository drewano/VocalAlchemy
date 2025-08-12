# VocalAlchemy Project Context for Qwen Code

This document provides essential context for Qwen Code to understand and assist with the VocalAlchemy project, an audio analysis pipeline using Azure Speech and AI services.

## Project Overview

VocalAlchemy is a full-stack web application designed to analyze audio files. Users can upload audio, which is then transcribed using Azure Speech Services. The transcript is subsequently processed by an AI (Azure AI Studio via LiteLLM) according to predefined or custom prompts to generate various types of analysis (e.g., summaries, action items, sentiment analysis). The application features a React/Vite frontend and a Python/FastAPI backend. It uses PostgreSQL for data persistence, Redis for task queuing, and Azure Blob Storage for file storage. Docker and Docker Compose are used for containerization and orchestration.

## Key Technologies & Architecture

*   **Frontend:** React (v19), Vite, TypeScript, Tailwind CSS.
*   **Backend:** Python (v3.11), FastAPI, SQLAlchemy (asyncpg for PostgreSQL), ARQ (with Redis) for background tasks.
*   **External Services:**
    *   Azure Speech Services (for transcription).
    *   Azure AI Studio / LiteLLM (for AI analysis).
    *   Azure Blob Storage (for storing original audio, transcripts, and analysis results).
*   **Databases:**
    *   PostgreSQL (main relational data: users, analyses, prompts, results).
    *   Redis (task queue and caching).
*   **Containerization:** Docker, Docker Compose.

## Development & Running Instructions

### Prerequisites

*   Docker and Docker Compose installed.
*   An `.env` file configured with necessary API keys and connection strings (see `.env.example`).

### Building and Running

1.  **Environment Setup:** Ensure your `.env` file is correctly populated with Azure credentials, database details, and secret keys.
2.  **Start Services:** Run the entire application stack using Docker Compose:
    ```bash
    docker-compose up --build
    ```
    This command builds the frontend, creates the necessary Docker images, and starts the `db`, `redis`, `app`, and `worker` services as defined in `docker-compose.yml`.
3.  **Accessing the Application:**
    *   The frontend should be accessible at `http://localhost:8000`.
    *   The backend API is also served from `http://localhost:8000/api`.

### Development Workflow

#### Backend (Python/FastAPI)
*   **Entry Point:** `backend/src/main.py`
*   **Dependencies:** Managed via `requirements.txt`.
*   **Configuration:** `backend/src/config.py` loads settings from environment variables.
*   **Structure:**
    *   `backend/src/api/endpoints/`: API route definitions (e.g., `analysis.py` for core analysis logic).
    *   `backend/src/services/`: Core business logic (e.g., `analysis_service.py`, `external_apis/`).
    *   `backend/src/infrastructure/`: Database models (`sql_models.py`), database connection (`database.py`), and repositories (`repositories/`).
    *   `backend/src/worker/`: ARQ worker definitions for background tasks (`main.py`, `tasks.py`).
*   **Testing:** (If tests exist) Run using the project's test framework (details would be in test files/scripts).

#### Frontend (React/Vite)
*   **Entry Point:** `frontend/index.html`, `frontend/src/main.tsx`
*   **Dependencies:** Managed via `frontend/package.json` (`npm install` or `pnpm install`).
*   **Development Server:** Run locally (outside Docker) using `npm run dev` or `pnpm dev` within the `frontend/` directory.
*   **Building:** The production build is handled by the Dockerfile's first stage (`FROM node:20-alpine AS frontend-builder`) and the command `npm run build`.

### Key Dockerfile Stages

1.  **Frontend Builder:** Uses Node.js to build the React/Vite application into static files.
2.  **Main Application:** Uses Python to create the final image.
    *   Installs system dependencies (like `ffmpeg`).
    *   Installs Python requirements.
    *   Copies backend source code.
    *   **Crucially**, it copies the static files built in the first stage into the `/app/static` directory.
    *   The FastAPI app (`src.main:app`) is configured to serve these static files.

## Data Flow

1.  User uploads an audio file via the frontend.
2.  Backend (`/api/analysis/initiate-upload/`) generates a SAS URL for Azure Blob Storage and creates an analysis record.
3.  Frontend uploads the file directly to Azure Blob Storage using the SAS URL.
4.  Frontend calls backend (`/api/analysis/finalize-upload/`) to signal upload completion.
5.  Backend enqueues a transcription task (`start_transcription_task`) via ARQ/Redis.
6.  ARQ Worker picks up the task, uses Azure Speech SDK to transcribe the audio (stored back in Blob Storage), and updates the database.
7.  Upon successful transcription, the worker enqueues an AI analysis task (`run_ai_analysis_task`).
8.  ARQ Worker picks up the analysis task, retrieves the transcript, sends it to Azure AI via LiteLLM for processing, and stores the results in Blob Storage/database.
9.  Frontend polls `/api/analysis/status/{analysis_id}` or fetches the full result from `/api/analysis/{analysis_id}`.

## Service Details

### Audio Transcription (`AzureSpeechClient`)
Located in `backend/src/services/external_apis/azure_speech_client.py`.
*   Uses Azure Cognitive Services Speech SDK via REST API for batch transcription.
*   Optimized for French (`fr-FR`) with diarization enabled.
*   Submits audio files stored in Azure Blob Storage (via SAS URL) for transcription.
*   Provides methods to check job status and retrieve the final transcript.

### AI Analysis (`LiteLLMAIProcessor`)
Located in `backend/src/services/external_apis/litellm_ai_processor.py`.
*   Uses the `litellm` library as a unified interface to LLMs.
*   Specifically configured to connect to Azure AI Studio endpoints.
*   Executes prompts defined in `PromptFlows` against the transcribed text.

### Blob Storage (`BlobStorageService`)
Located in `backend/src/services/blob_storage_service.py`.
*   Wrapper around Azure Blob Storage SDK.
*   Handles uploading/downloading files (audio, transcripts, analysis results).
*   Generates SAS URLs for secure, time-limited access to blobs, including for direct browser uploads.

### Analysis Core Logic (`AnalysisService`)
Located in `backend/src/services/analysis_service.py`.
*   Orchestrates the entire analysis pipeline.
*   Manages audio normalization using `pydub`/`ffmpeg`.
*   Coordinates with `AzureSpeechClient` for transcription.
*   Coordinates with `LiteLLMAIProcessor` for AI analysis.
*   Interacts with `BlobStorageService` for file I/O.
*   Updates analysis status and progress in the database.
*   Handles deletion of analysis data (including associated blobs).

### Background Tasks (`ARQ Worker`)
Defined in `backend/src/worker/tasks.py` and `backend/src/worker/main.py`.
*   Uses ARQ with Redis to process long-running tasks asynchronously.
*   Tasks include: starting transcription, checking transcription status, running AI analysis, deleting analysis data.
*   Prevents the main API from blocking while waiting for external services.