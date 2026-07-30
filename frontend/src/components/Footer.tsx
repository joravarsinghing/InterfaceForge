import React from 'react';
import { HealthResponse } from '../services/api';
import { Wordmark } from './Wordmark';

interface FooterProps {
  healthState: {
    data: HealthResponse | null;
    loading: boolean;
    error: string | null;
  };
}

export const Footer: React.FC<FooterProps> = ({ healthState }) => {
  const getStatusText = () => {
    if (healthState.loading) return 'API Status: Checking...';
    if (healthState.error || !healthState.data) return 'API Status: Offline';
    return `API Status: Online (${healthState.data.service_name} v${healthState.data.version})`;
  };

  return (
    <footer className="app-footer">
      <div className="footer-container">
        <div className="footer-info">
          <p className="privacy-note">
            <strong>Privacy &amp; Data Storage:</strong> Project state is stored locally by the development backend. Uploaded images are stored temporarily for profile extraction. No user accounts or tracking systems exist, and external AI/Zoo services are inactive in mock mode.
          </p>
        </div>

        <div className="footer-links">
          <span className="footer-link-item">{getStatusText()}</span>
          <span className="footer-separator" aria-hidden="true">|</span>
          <a
            href="https://github.com/joravarsinghing/InterfaceForge"
            target="_blank"
            rel="noopener noreferrer"
            className="footer-link"
          >
            GitHub Repository
          </a>
          <span className="footer-separator" aria-hidden="true">|</span>
          <span className="footer-link-item"><Wordmark /> - <img src="/Zoo.dev.logo.svg" alt="Zoo" className="footer-zoo-logo" /> API Makeathon 2026 Submission</span>
        </div>
      </div>
    </footer>
  );
};
