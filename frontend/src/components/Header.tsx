import React, { useState } from 'react';
import { HealthResponse } from '../services/api';
import { Project, ProviderMode, ProviderModeStatus } from '../types/schema';
import { Wordmark } from './Wordmark';

interface HeaderProps {
  healthState: {
    data: HealthResponse | null;
    loading: boolean;
    error: string | null;
  };
  project?: Project | null;
  providerStatus?: ProviderModeStatus | null;
  providerModeError?: string | null;
  onRetryHealth: () => void;
  onRequestRestart?: () => void;
  onProviderModeChange?: (mode: ProviderMode) => Promise<void> | void;
}

export const Header: React.FC<HeaderProps> = ({
  healthState,
  project,
  providerStatus: _providerStatus,
  providerModeError,
  onRetryHealth,
  onRequestRestart,
  onProviderModeChange: _onProviderModeChange,
}) => {
  const [showHelp, setShowHelp] = useState(false);




  const getStatusBadge = () => {
    if (healthState.loading) {
      return (
        <span className="status-badge status-loading" aria-live="polite">
          <span className="status-dot" aria-hidden="true"></span> Checking backend
        </span>
      );
    }
    if (healthState.error || !healthState.data) {
      return (
        <button
          className="status-badge status-offline"
          onClick={onRetryHealth}
          title={`Backend unavailable: ${healthState.error || 'Unknown error'}. Click to retry.`}
          aria-live="polite"
        >
          <span className="status-dot" aria-hidden="true"></span> Offline (Retry)
        </button>
      );
    }
    return (
      <span
        className="status-badge status-live"
        title={`${healthState.data.service_name} is connected.`}
        aria-live="polite"
      >
        <span className="status-dot" aria-hidden="true"></span> Connected
      </span>
    );
  };

  return (
    <header className="app-header">
      <div className="header-container">
        <div className="header-left">
          <a href="/" className="logo-link" aria-label="InterfaceForge Home">
            <img src="/InterfaceForge_logo_in.svg" alt="" className="logo-compact-header" />
            <Wordmark className="brand-wordmark" />
          </a>
        </div>


        <div className="header-right">
          {project && (
            <span className="project-name-badge" title={`Project ID: ${project.project_id}`}>
              Project: <strong>{project.display_name || 'Adapter'}</strong>
            </span>
          )}

          {project && onRequestRestart && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={onRequestRestart}
            >
              Start Over
            </button>
          )}

          <button
            className="help-button"
            onClick={() => setShowHelp(!showHelp)}
            aria-expanded={showHelp}
            aria-label="Toggle help panel"
          >
            Help
          </button>
          {getStatusBadge()}
        </div>
      </div>

      {providerModeError && (
        <div className="provider-mode-message" role="status">
          {providerModeError}
        </div>
      )}

      {showHelp && (
        <div className="help-panel" role="region" aria-label="InterfaceForge help">
          <div className="help-panel-content">
            <h3>InterfaceForge Help</h3>
            <p>
              InterfaceForge guides you from two clean 2D interface profiles to a reviewed parametric transition adapter.
            </p>

            <div className="help-columns">
              <section aria-labelledby="help-workflow-heading">
                <h4 id="help-workflow-heading">How to use it</h4>
                <ol>
                  <li>Upload Interface A and confirm one known measurement.</li>
                  <li>Review and approve the detected profile, then repeat for Interface B.</li>
                  <li>Configure the connection and manufacturing settings.</li>
                  <li>Generate through Zoo Engine, review the adapter candidate, and export when ready.</li>
                </ol>
              </section>

              <section aria-labelledby="help-input-heading">
                <h4 id="help-input-heading">For the best results</h4>
                <p>Use front-facing, filled, high-contrast profile images with the full shape visible and proportions preserved.</p>
                <p className="status-note">All detected geometry and scale must be reviewed and confirmed. Outputs are editable design candidates and should be inspected before manufacturing.</p>
              </section>
            </div>

            <p className="help-credit">
              Created by Joravar Singh for the Zoo API Makeathon 2026.{' '}
              <a
                href="https://joravarsinghing.github.io/portfolio/"
                target="_blank"
                rel="noopener noreferrer"
                className="portfolio-link"
              >
                View portfolio
              </a>{' '}
              or <a href="mailto:joravarofficial@outlook.com" className="portfolio-link">email Joravar</a>.
            </p>
            <button className="btn btn-secondary" onClick={() => setShowHelp(false)}>
              Close Help
            </button>
          </div>
        </div>
      )}

    </header>
  );
};

export default Header;
