import React, { useState } from 'react';
import { HealthResponse } from '../services/api';
import { Project } from '../types/schema';
import { Wordmark } from './Wordmark';

interface HeaderProps {
  healthState: {
    data: HealthResponse | null;
    loading: boolean;
    error: string | null;
  };
  project?: Project | null;
  onRetryHealth: () => void;
  onRestartProject?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  healthState,
  project,
  onRetryHealth,
  onRestartProject,
}) => {
  const [showHelp, setShowHelp] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);

  const getStatusBadge = () => {
    if (healthState.loading) {
      return (
        <span className="status-badge status-loading" aria-live="polite">
          <img src="/InterfaceForge_logo_in.svg" alt="" className="logo-badge-icon" />
          <span className="status-dot"></span> Checking backend...
        </span>
      );
    }
    if (healthState.error || !healthState.data) {
      return (
        <button
          className="status-badge status-offline"
          onClick={onRetryHealth}
          title={`Backend Unavailable: ${healthState.error || 'Unknown error'}. Click to retry.`}
          aria-live="polite"
        >
          <img src="/InterfaceForge_logo_in.svg" alt="" className="logo-badge-icon" />
          <span className="status-dot"></span> Service: Offline (Retry)
        </button>
      );
    }
    return (
      <span
        className="status-badge status-online"
        title={`Connected to ${healthState.data.service_name} v${healthState.data.version} (${healthState.data.environment})`}
        aria-live="polite"
      >
        <span className="status-dot"></span> Service: Online
      </span>
    );
  };

  return (
    <header className="app-header">
      <div className="header-container">
        <div className="header-left">
          <a href="/" className="logo-link" aria-label="InterfaceForge Home">
            <img src="/InterfaceForge_logo.svg" alt="InterfaceForge Logo" className="logo-full-desktop" />
            <img src="/InterfaceForge_logo_in.svg" alt="InterfaceForge Mark" className="logo-compact-mobile" />
            <Wordmark className="logo-text" />
          </a>
          <span className="mock-mode-badge" title="Mock mode active for Zoo Engine API">
            Mock Mode
          </span>
        </div>

        <div className="header-right">
          {project && (
            <span className="project-id-badge" style={{ fontSize: '0.78rem', color: '#8b949e', background: '#161b22', padding: '0.25rem 0.5rem', borderRadius: '4px', border: '1px solid #30363d' }}>
              Project: <code style={{ color: '#79c0ff' }}>{project.project_id.substring(0, 8)}...</code>
            </span>
          )}

          {project && onRestartProject && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setShowConfirmModal(true)}
              style={{ fontSize: '0.8rem', padding: '0.3rem 0.6rem' }}
            >
              🔄 Start Over
            </button>
          )}

          <button
            className="help-button"
            onClick={() => setShowHelp(!showHelp)}
            aria-expanded={showHelp}
            aria-label="Toggle help dialog"
          >
            Help
          </button>
          {getStatusBadge()}
        </div>
      </div>

      {showHelp && (
        <div className="help-panel" role="region" aria-label="Help and documentation">
          <div className="help-panel-content">
            <h3><Wordmark /> Help &amp; Documentation</h3>
            <p>
              <Wordmark /> connects two physical products by converting 2D interface images into parametric CAD models via Zoo Engine API.
            </p>
            <p className="status-note">
              <strong>Stage S6A Note:</strong> Full guided web app workflow is active in Mock Mode. Complete all steps to generate deterministic KCL code and view 3D adapter specifications.
            </p>
            <button className="btn btn-secondary" onClick={() => setShowHelp(false)}>
              Close Help
            </button>
          </div>
        </div>
      )}

      {showConfirmModal && (
        <div className="modal-overlay" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0, 0, 0, 0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="modal-card" style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '1.5rem', maxWidth: '440px', width: '90%', color: '#f0f6fc' }}>
            <h3 style={{ marginTop: 0, color: '#f85149', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>⚠️</span> Restart Project?
            </h3>
            <p style={{ fontSize: '0.9rem', color: '#c9d1d9' }}>
              Are you sure you want to exit or restart? All active session data for this project will be reset.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.25rem' }}>
              <button type="button" className="btn btn-secondary" onClick={() => setShowConfirmModal(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                style={{ background: '#da3633', borderColor: '#f85149' }}
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
