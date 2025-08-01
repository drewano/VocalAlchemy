import React from 'react';

const FileUpload = ({ onFileSelect, file }) => {
  const handleFileChange = (e) => {
    onFileSelect(e.target.files[0]);
  };

  return (
    <section className="upload-section">
      <h2>Upload Audio File</h2>
      <div className="file-input-wrapper">
        <input 
          id="audio-file"
          type="file" 
          accept="audio/*" 
          onChange={handleFileChange} 
        />
        <label htmlFor="audio-file" className="file-input-label">
          Choose File
        </label>
        <span className="file-name">
          {file ? file.name : 'Aucun fichier sélectionné'}
        </span>
      </div>
    </section>
  );
};

export default FileUpload;