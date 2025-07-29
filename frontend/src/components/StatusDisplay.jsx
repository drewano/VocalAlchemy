import React from 'react';

const StatusDisplay = ({ status }) => {
  return (
    <div className="status-section">
      <div className="status-indicator">
        <div className="spinner"></div>
        <div id="status-message">{status}</div>
      </div>
    </div>
  );
};

export default StatusDisplay;