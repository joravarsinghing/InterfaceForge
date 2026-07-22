import React from 'react';
import { HealthResponse } from '../services/api';

interface HeaderProps {
  healthState: {
    data: HealthResponse | null;
    loading: boolean;
    error: string | null;
  };
  onRetryHealth: () => void;
}

export const Header: React.FC<HeaderProps> = ({ healthState, onRetryHealth }) => {
  const [showHelp, setShowHelp] = React.useState(false);

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
            <span className="logo-text">InterfaceForge</span>
          </a>
          <span className="project-status-tag" aria-label="Current Project Status">
            S5A KCL &amp; Brand
          </span>
        </div>

        <div className="header-right">
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
            <h3>InterfaceForge Help & Documentation</h3>
            <p>
              InterfaceForge connects two physical products by converting 2D interface images into parametric CAD models via Zoo Engine API.
            </p>
            <p className="status-note">
              <strong>Stage S5A Note:</strong> KCL Compiler &amp; Brand Integration active. Canonical design schemas compile into deterministic KCL without external API execution.
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
