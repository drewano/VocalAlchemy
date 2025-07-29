import { useState, useEffect } from 'react';
import axios from 'axios';
import FileUpload from './components/FileUpload';
import StatusDisplay from './components/StatusDisplay';
import ResultDisplay from './components/ResultDisplay';
import './App.css';

function App() {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState('');
  const [result, setResult] = useState(null);
  const [taskId, setTaskId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleFileSelect = (selectedFile) => {
    setFile(selectedFile);
  };

  const handleSubmit = async () => {
    if (!file) return;

    setIsLoading(true);
    setError(null);
    setStatus('Envoi du fichier...');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('/api/process-audio/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const newTaskId = response.data.task_id;
      setTaskId(newTaskId);
      setStatus('Démarré');
    } catch (err) {
      setError(err.message);
      setIsLoading(false);
    }
  };

  const fetchResult = async (id) => {
    try {
      const response = await axios.get(`/api/result/${id}`);
      setResult(response.data);
      setIsLoading(false);
    } catch (err) {
      setError(err.message);
      setIsLoading(false);
    }
  };

  const pollStatus = async () => {
    if (!taskId) return;

    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`/api/status/${taskId}`);
        const statusData = response.data;
        const currentStatus = statusData.status;

        setStatus(currentStatus);

        if (currentStatus === 'Terminé') {
          clearInterval(interval);
          fetchResult(taskId);
        }
      } catch (err) {
        setError(err.message);
        clearInterval(interval);
        setIsLoading(false);
      }
    }, 3000);

    return () => clearInterval(interval);
  };

  useEffect(() => {
    if (taskId) {
      pollStatus();
    }
  }, [taskId]);

  return (
    <div className="container">
      <header>
        <h1>Audio Analysis Pipeline</h1>
        <p>Upload an audio file for AI-powered transcription and analysis</p>
      </header>
      
      <main>
        {error && <div className="error">Erreur: {error}</div>}
        
        {result ? (
          <ResultDisplay resultText={result} taskId={taskId} />
        ) : isLoading ? (
          <StatusDisplay status={status} />
        ) : (
          <FileUpload 
            onFileSelect={handleFileSelect} 
            onSubmit={handleSubmit} 
            isLoading={isLoading} 
            file={file} 
          />
        )}
      </main>
      
      <footer>
        <p>Audio Analysis Pipeline © 2025</p>
      </footer>
    </div>
  );
}

export default App;
