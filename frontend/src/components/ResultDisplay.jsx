import React from 'react';

const ResultDisplay = ({ resultText, taskId }) => {
  const handleDownload = () => {
    // Create a temporary link element
    const link = document.createElement('a');
    link.href = `/api/result/${taskId}`;
    link.download = 'report.txt';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <section className="result-section">
      <h2>Analysis Result</h2>
      <div id="analysis-result">
        <pre>{resultText}</pre>
      </div>
      <button onClick={handleDownload}>
        Télécharger le rapport
      </button>
      <button onClick={() => window.location.reload()}>
        Process Another File
      </button>
    </section>
  );
};

export default ResultDisplay;