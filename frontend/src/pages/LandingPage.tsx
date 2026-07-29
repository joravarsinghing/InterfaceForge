import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { HealthResponse, ServiceStatusRow } from '../services/api';
import { getEarliestIncompleteStep } from '../services/workflow';
import { Project } from '../types/schema';

interface LandingPageProps {
  healthState: {
    data: HealthResponse | null;
    loading: boolean;
    error: string | null;
  };
  project?: Project | null;
  isHydrating?: boolean;
  onRetryHealth: () => void;
  onStartProject?: () => Promise<Project>;
  onContinueProject?: () => Promise<Project | null>;
}

const REQUIRED_SERVICE_IDS = [
  'backend',
  'gemini_vision',
  'openrouter_vision',
  'zoo_engine',
  'persistence',
];

const SERVICE_LABELS: Record<string, string> = {
  backend: 'InterfaceForge backend',
  gemini_vision: 'Gemini Vision',
  openrouter_vision: 'OpenRouter Vision fallback',
  zoo_engine: 'Zoo Authentication',
  persistence: 'Project persistence/storage',
};

function rowsFromHealth(health: HealthResponse | null, loading: boolean, error: string | null): ServiceStatusRow[] {
  const rows = health?.services ?? [];
  const byId = new Map(rows.map((row) => [row.id, row]));
  return REQUIRED_SERVICE_IDS.map((id) => {
    const existing = byId.get(id);
    if (existing) return existing;
    if (id === 'backend') {
      if (loading) {
        return { id, label: SERVICE_LABELS[id], status: 'Checking', message: 'Backend health check is in progress.' };
      }
      if (error || !health) {
        return { id, label: SERVICE_LABELS[id], status: 'Unavailable', message: error || 'Backend health check failed.' };
      }
      return { id, label: SERVICE_LABELS[id], status: 'Available', message: 'Backend API is responding.' };
    }
    return {
      id,
      label: SERVICE_LABELS[id],
      status: loading ? 'Checking' : 'Unavailable',
      message: loading ? 'Service check is in progress.' : 'No status was returned for this service.',
    };
  });
}

export const LandingPage: React.FC<LandingPageProps> = ({
  healthState,
  project,
  isHydrating = false,
  onRetryHealth,
  onStartProject,
  onContinueProject,
}) => {
  const navigate = useNavigate();
  const [starting, setStarting] = useState(false);
  const [continuing, setContinuing] = useState(false);
  const [showNewProjectConfirm, setShowNewProjectConfirm] = useState(false);
  const hasProject = Boolean(project?.project_id);

  const handleStart = async () => {
    if (onStartProject) {
      setStarting(true);
      try {
        await onStartProject();
        setStarting(false);
        navigate('/step1');
      } catch (_err: unknown) {
        setStarting(false);
        navigate('/step1');
      }
    } else {
      navigate('/step1');
    }
  };

  const handleContinue = async () => {
    if (!project) return;
    setContinuing(true);
    try {
      const latest = onContinueProject ? await onContinueProject() : project;
      navigate(getEarliestIncompleteStep(latest || project));
    } finally {
      setContinuing(false);
    }
  };

  const statusRows = rowsFromHealth(healthState.data, healthState.loading, healthState.error);
  const connectedCount = statusRows.filter((row) => row.status === 'Available').length;
  const statusSummary = healthState.loading
    ? 'Checking services'
    : `${connectedCount}/${statusRows.length} services available`;

  return (
    <div className="landing-page">
      <section className="hero-section" aria-labelledby="hero-heading">
        <div className="hero-container">
          <img src="/InterfaceForge_logo.svg" alt="" className="hero-icon" />
          <h1 id="hero-heading" className="hero-title">
            Two interfaces in. One adapter out.
          </h1>
          <p className="hero-subtitle">
            Upload clean cross-section images for A and B, confirm scale, approve each trace, configure the adapter, and generate a parametric CAD candidate with Zoo Engine.
          </p>

          <div className="hero-actions">
            {hasProject ? (
              <>
                <button
                  type="button"
                  className="btn btn-primary btn-large"
                  disabled={continuing || isHydrating}
                  onClick={handleContinue}
                >
                  {continuing || isHydrating ? 'Restoring Project...' : 'Continue Project'}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-large"
                  disabled={starting}
                  onClick={() => setShowNewProjectConfirm(true)}
                >
                  Start New Project
                </button>
              </>
            ) : (
              <button
                type="button"
                className="btn btn-primary btn-large"
                disabled={starting || isHydrating}
                onClick={handleStart}
              >
                {starting ? 'Initializing Project...' : 'Start New Project'}
              </button>
            )}
          </div>
        </div>
      </section>

      <section className="workflow-preview-section" aria-labelledby="workflow-heading">
        <h2 id="workflow-heading" className="section-title">How It Works</h2>
        <div className="workflow-steps-grid">
          <div className="workflow-card">
            <div className="workflow-step-num">1</div>
            <h3>Capture Interface A</h3>
            <p>Upload a clean front-facing cross-section of the first mating face.</p>
          </div>
          <div className="workflow-card">
            <div className="workflow-step-num">2</div>
            <h3>Capture Interface B</h3>
            <p>Approve A, then repeat trace and scale review for the second interface.</p>
          </div>
          <div className="workflow-card">
            <div className="workflow-step-num">3</div>
            <h3>Choose Connection</h3>
            <p>Select coaxial, offset, or limited-angle parametric relationship.</p>
          </div>
          <div className="workflow-card">
            <div className="workflow-step-num">4</div>
            <h3>Generate Model</h3>
            <p>Compile deterministic KCL from approved parameters and execute with Zoo Engine.</p>
          </div>
          <div className="workflow-card">
            <div className="workflow-step-num">5</div>
            <h3>Review &amp; Export</h3>
            <p>Inspect the adapter candidate, optionally revise parameters, and export STL/STEP/KCL.</p>
          </div>
        </div>
      </section>

      <section className="examples-section" aria-labelledby="examples-heading">
        <h2 id="examples-heading" className="section-title">Example Applications</h2>
        <div className="examples-grid">
          <div className="example-card">
            <div className="example-image-placeholder" role="img" aria-label="Placeholder for future Vacuum Hose Adapter example image">
              <span>Vacuum Hose Adapter image placeholder</span>
            </div>
            <h3>Vacuum Hose Adapter</h3>
            <p>Connect shop dust extractors to CNC router dust ports with tight slip fit.</p>
            <span className="card-badge">Coaxial Mode</span>
          </div>
          <div className="example-card">
            <div className="example-image-placeholder" role="img" aria-label="Placeholder for future Camera Mount Adapter example image">
              <span>Camera Mount Adapter image placeholder</span>
            </div>
            <h3>Camera Mount Adapter</h3>
            <p>Transition between non-standard tripod plates and camera rigs.</p>
            <span className="card-badge">Offset Mode</span>
          </div>
        </div>
      </section>

      <details className="dev-status-details">
        <summary className="dev-status-summary">
          <span>System Status</span>
          <span className="dev-status-indicator">{statusSummary}</span>
        </summary>
        <div className="status-card" style={{ marginTop: '16px' }}>
          <div className="status-panel-header">
            <div>
              <h3>Runtime Dependencies</h3>
              <p>Provider checks are independent and do not expose keys or environment values.</p>
            </div>
            <button type="button" className="btn btn-secondary" onClick={onRetryHealth} disabled={healthState.loading}>
              {healthState.loading ? 'Checking...' : 'Refresh Status'}
            </button>
          </div>
          <div className="service-status-list" aria-live="polite">
            {statusRows.map((row) => (
              <div className="service-status-row" key={row.id} data-status={row.status}>
                <div>
                  <strong>{row.label}</strong>
                  {row.model && <span className="service-model">Model: {row.model}</span>}
                  <p>{row.message}</p>
                </div>
                <span className="service-status-badge">{row.status}</span>
              </div>
            ))}
          </div>
        </div>
      </details>

      {showNewProjectConfirm && (
        <div className="modal-overlay" role="presentation">
          <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="new-project-heading">
            <h3 id="new-project-heading">Start New Project?</h3>
            <p>
              A separate new project will be created. Your existing project will remain saved and will not be deleted or overwritten.
            </p>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setShowNewProjectConfirm(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  setShowNewProjectConfirm(false);
                  void handleStart();
                }}
              >
                Start New Project
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
