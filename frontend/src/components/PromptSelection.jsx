import { useState, useEffect } from 'react';
import axios from 'axios';

const PromptSelection = ({ prompt, setPrompt }) => {
  const [predefinedPrompts, setPredefinedPrompts] = useState([]);

  useEffect(() => {
    const fetchPrompts = async () => {
      try {
        const response = await axios.get('/api/prompts');
        setPredefinedPrompts(response.data);
      } catch (error) {
        console.error('Error fetching prompts:', error);
      }
    };

    fetchPrompts();
  }, []);

  const handlePromptChange = (e) => {
    setPrompt(e.target.value);
  };

  const handleSelectChange = (e) => {
    const selectedPrompt = e.target.value;
    if (selectedPrompt) {
      setPrompt(selectedPrompt);
    }
  };

  return (
    <div className="prompt-selection">
      <h2>Personnalisez votre analyse</h2>
      
      <div className="prompt-controls">
        <select 
          onChange={handleSelectChange}
          value=""
          className="prompt-select"
        >
          <option value="">Choisissez un prompt prédéfini</option>
          {Object.entries(predefinedPrompts).map(([name, content]) => (
            <option key={name} value={content}>
              {name}
            </option>
          ))}
        </select>
        
        <textarea
          value={prompt}
          onChange={handlePromptChange}
          placeholder="Saisissez ou modifiez votre prompt personnalisé ici..."
          className="prompt-textarea"
          rows={6}
        />
      </div>
    </div>
  );
};

export default PromptSelection;