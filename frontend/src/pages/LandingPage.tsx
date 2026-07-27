import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { HealthResponse } from '../services/api';
import { Project } from '../types/schema';

interface LandingPageProps {
  healthState: {
    data: HealthResponse | null;
    loading: boolean;
    error: string | null;
  };
  onRetryHealth: () => void;
  onStartProject?: () => Promise<Project>;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  healthState,
  onRetryHealth,
  onStartProject,
}) => {
  const navigate = useNavigate();
  const [starting, setStarting] = useState(false);

  const handleStart = async () => {
    if (onStartProject) {
      setStarting(true);
      try {
        await onStartProject();
        setStarting(false);
        navigate('/step1');
      } catch (err: unknown) {
        setStarting(false);
        // Navigate anyway to step1 as fallback
        navigate('/step1');
      }
    } else {
      navigate('/step1');
    }
  };

  return (
    <div className="landing-page">
      {/* Hero Section */}
      <section className="hero-section" aria-labelledby="hero-heading">
        <div className="hero-container">
          <h1 id="hero-heading" className="hero-title">
            Two interfaces in. One adapter out.
          </h1>
          <p className="hero-subtitle">
            Upload or sketch two physical interfaces, confirm dimensions, choose how they connect, and generate a parametric CAD adapter powered by Zoo Engine API.
          </p>

          <div className="hero-actions">
            <button
              type="button"
              className="btn btn-primary btn-large"
              disabled={starting}
              onClick={handleStart}
            >
              {starting ? 'Initializing Project...' : 'Start New Project'}
            </button>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="workflow-preview-section" aria-labelledby="workflow-heading">
        <h2 id="workflow-heading" className="section-title">How It Works</h2>
        <div className="workflow-steps-grid">
          <div className="workflow-card">
            <div className="workflow-step-num">1</div>
            <h3>Capture Interface A</h3>
            <p>Upload a photograph or sketch facing the opening directly.</p>
          </div>
          <div className="workflow-card">
            <div className="workflow-step-num">2</div>
            <h3>Capture Interface B</h3>
            <p>Upload photograph or sketch for the second mating product.</p>
          </div>
          <div className="workflow-card">
            <div className="workflow-step-num">3</div>
            <h3>Choose Connection</h3>
            <p>Select coaxial, offset, or limited-angle parametric relationship.</p>
          </div>
          <div className="workflow-card">
            <div className="workflow-step-num">4</div>
            <h3>Generate Model</h3>
            <p>Execute deterministic KCL generation via Zoo Engine API.</p>
          </div>
          <div className="workflow-card">
            <div className="workflow-step-num">5</div>
            <h3>Review & Export</h3>
            <p>Inspect 3D render and download manufacturing-ready STL/STEP files.</p>
          </div>
        </div>
      </section>

      {/* Sample Examples Preview */}
      <section className="examples-section" aria-labelledby="examples-heading">
        <h2 id="examples-heading" className="section-title">Example Applications</h2>
        <div className="examples-grid">
          <div className="example-card">
            <h3>Vacuum Hose Adapter</h3>
            <p>Connect shop dust extractors to CNC router dust ports with tight slip fit.</p>
            <span className="card-badge">Coaxial Mode</span>
          </div>
          <div className="example-card">
            <h3>Camera Mount Adapter</h3>
            <p>Transition between non-standard tripod plates and camera rigs.</p>
            <span className="card-badge">Offset Mode</span>
          </div>
        </div>
      </section>

      {/* Low-Emphasis Collapsible Backend & Developer Status */}
      <details className="dev-status-details">
        <summary className="dev-status-summary">
          <span>⚙️ System Architecture &amp; Backend Status</span>
          <span className="dev-status-indicator">
            {healthState.data ? '● Service Connected' : healthState.loading ? '○ Checking...' : '⚠️ Service Offline'}
          </span>
        </summary>
        <div className="status-card" style={{ marginTop: '16px' }}>
          {healthState.loading && (
            <div className="status-state loading" aria-live="polite">
              <div className="spinner"></div>
              <p>Connecting to FastAPI backend endpoint at <code>/health</code>...</p>
            </div>
          )}

          {healthState.error && (
            <div className="status-state offline" aria-live="polite">
              <div className="status-icon">⚠️</div>
              <div className="status-details">
                <h3>Backend Service Unavailable</h3>
                <p>Could not reach local FastAPI server at <code>http://localhost:8000/health</code>.</p>
                <p className="error-message">Error details: {healthState.error}</p>
                <div className="status-actions">
                  <button type="button" className="btn btn-secondary" onClick={onRetryHealth}>
                    Retry Connection
                  </button>
                </div>
              </div>
            </div>
          )}

          {healthState.data && (
            <div className="status-state online" aria-live="polite">
              <div className="status-icon">✅</div>
              <div className="status-details">
                <h3>Backend Service Connected &amp; Healthy</h3>
                <div className="health-grid">
                  <div className="health-item">
                    <span className="health-label">Service Name</span>
                    <span className="health-value">{healthState.data.service_name}</span>
                  </div>
                  <div className="health-item">
                    <span className="health-label">Status</span>
                    <span className="health-value status-ok">{healthState.data.status}</span>
                  </div>
                  <div className="health-item">
                    <span className="health-label">Environment</span>
                    <span className="health-value">{healthState.data.environment}</span>
                  </div>
                  <div className="health-item">
                    <span className="health-label">API Version</span>
                    <span className="health-value">{healthState.data.version}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </details>
    </div>
  );
};
