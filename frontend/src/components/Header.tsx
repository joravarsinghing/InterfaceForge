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
  onRestartProject?: () => void;
  onProviderModeChange?: (mode: ProviderMode) => Promise<void> | void;
}

export const Header: React.FC<HeaderProps> = ({
  healthState,
  project,
  providerStatus,
  providerModeError,
  onRetryHealth,
  onRestartProject,
  onProviderModeChange,
}) => {
  const [showHelp, setShowHelp] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [changingMode, setChangingMode] = useState<ProviderMode | null>(null);

  const effectiveMode: ProviderMode = providerStatus?.effective_mode ?? project?.provider_mode ?? 'mock';
  const selectedMode: ProviderMode = providerStatus?.selected_mode ?? project?.provider_mode ?? 'mock';
  const statusIsLive = Boolean(effectiveMode === 'live' && providerStatus?.live_available);
  const statusLabel = statusIsLive ? 'Live' : 'Mock / Offline';
  const canChangeProviderMode = Boolean(onProviderModeChange);

  const handleModeClick = async (mode: ProviderMode) => {
    if (!onProviderModeChange || changingMode) return;
    setChangingMode(mode);
    try {
      await onProviderModeChange(mode);
    } finally {
      setChangingMode(null);
    }
  };

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

          {project && onRestartProject && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setShowConfirmModal(true)}
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
        <div className="help-panel" role="region" aria-label="Creator and workflow help">
          <div className="help-panel-content">
            <h3>Created by Joravar Singh</h3>
            <p>
              InterfaceForge was created by Joravar Singh for the Zoo API Makeathon 2026.
            </p>
            <p>
              <a
                href="https://joravarsinghing.github.io/portfolio/"
                target="_blank"
                rel="noopener noreferrer"
                className="portfolio-link"
              >
                Open Joravar Singh's portfolio
              </a>
            </p>
            <p className="status-note">
              Workflow: approve both interface profiles, configure the connection, then generate and review the adapter candidate before export.
            </p>
            <button className="btn btn-secondary" onClick={() => setShowHelp(false)}>
              Close Help
            </button>
          </div>
        </div>
      )}

      {showConfirmModal && (
        <div className="modal-overlay">
          <div className="modal-card">
            <h3>Restart Project?</h3>
            <p>
              All active session data for this project will be reset in this browser. Existing backend records are not deleted.
            </p>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setShowConfirmModal(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary btn-danger-confirm"
                onClick={() => {
                  setShowConfirmModal(false);
                  if (onRestartProject) onRestartProject();
                }}
              >
                Yes, Restart Project
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};

export default Header;
