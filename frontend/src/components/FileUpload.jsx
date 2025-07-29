import React from 'react';

const FileUpload = ({ onFileSelect, onSubmit, isLoading, file }) => {
  const handleFileChange = (e) => {
    onFileSelect(e.target.files[0]);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit();
  };

  return (
    <section className="upload-section">
      <h2>Upload Audio File</h2>
      <form onSubmit={handleSubmit}>
        <div className="file-input-wrapper">
          <input 
            id="audio-file"
            type="file" 
            accept="audio/*" 
            onChange={handleFileChange} 
            disabled={isLoading}
          />
          <label htmlFor="audio-file" className="file-input-label">
            Choose File
          </label>
          <span className="file-name">
            {file ? file.name : 'Aucun fichier sélectionné'}
          </span>
        </div>
        <button 
          type="submit" 
          disabled={isLoading || !file}
        >
          {isLoading ? 'Processing...' : 'Upload and Process'}
        </button>
      </form>
    </section>
  );
};

export default FileUpload;