// Handle file selection and display filename
document.getElementById('audio-file').addEventListener('change', function(e) {
    const fileName = e.target.files[0] ? e.target.files[0].name : 'Aucun fichier sélectionné';
    document.getElementById('file-name').textContent = fileName;
});

// Handle form submission
document.getElementById('upload-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const form = e.target;
    const formData = new FormData(form);
    
    // Show status section and hide result section
    document.getElementById('status-section').style.display = 'block';
    document.getElementById('result-section').style.display = 'none';
    
    // Update status message
    document.getElementById('status-message').textContent = 'Envoi du fichier...';
    
    try {
        // Send file to backend
        const response = await fetch('/process-audio/', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        const taskId = data.task_id;
        
        // Start polling for status updates
        pollStatus(taskId);
    } catch (error) {
        document.getElementById('status-message').textContent = `Erreur: ${error.message}`;
        console.error('Error:', error);
    }
});

// Poll for task status
async function pollStatus(taskId) {
    const statusMessage = document.getElementById('status-message');
    const progressBar = document.getElementById('progress');
    
    // Define known statuses and their progress percentages
    const statusProgress = {
        'Démarré': 10,
        'Découpage du fichier audio...': 20,
        'Analyse de la transcription par l\'IA...': 80,
        'Terminé': 100
    };
    
    const poll = async () => {
        try {
            const response = await fetch(`/status/${taskId}`);
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const statusData = await response.json();
            const status = statusData.status;
            
            // Update status message
            statusMessage.textContent = status;
            
            // Update progress bar
            const progress = statusProgress[status] || 0;
            progressBar.style.width = `${progress}%`;
            
            if (status === 'Terminé') {
                // Task completed, fetch result
                try {
                    const resultResponse = await fetch(`/result/${taskId}`);
                    
                    if (!resultResponse.ok) {
                        throw new Error(`Erreur HTTP: ${resultResponse.status}`);
                    }
                    
                    const resultText = await resultResponse.text();
                    
                    // Display result
                    document.getElementById('analysis-result').textContent = resultText;
                    document.getElementById('result-section').style.display = 'block';
                    document.getElementById('status-section').style.display = 'none';
                    
                    // Set up download button
                    const downloadBtn = document.getElementById('download-btn');
                    downloadBtn.style.display = 'block';
                    downloadBtn.onclick = () => {
                        const a = document.createElement('a');
                        a.href = `/result/${taskId}`;
                        a.download = 'report.txt';
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                    };
                } catch (error) {
                    statusMessage.textContent = `Erreur lors de la récupération du résultat: ${error.message}`;
                    console.error('Error fetching result:', error);
                }
                
                return true; // Stop polling
            }
            
            return false; // Continue polling
        } catch (error) {
            statusMessage.textContent = `Erreur: ${error.message}`;
            console.error('Error polling status:', error);
            return true; // Stop polling on error
        }
    };
    
    // Poll every 3 seconds
    const interval = setInterval(async () => {
        const shouldStop = await poll();
        if (shouldStop) {
            clearInterval(interval);
        }
    }, 3000);
}