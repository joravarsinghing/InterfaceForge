import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { hasValidCurrentModel } from '../services/workflow';
import { GeometryPreview } from '../components/GeometryPreview';
import {
  Project,
  ConnectionValidationResult,
  GenerationJob,
  MockScenario,
  KCLCompileResult,
} from '../types/schema';
import {
  fetchKclReadiness,
  fetchActiveGeneration,
  compileKcl,
  startGeneration,
  cancelGeneration,
  retryGeneration,
  fetchProject,
} from '../services/api';

const ZOO_LOADING_DIALOGUES = [
  'Zoo Design Studio is an AI-native CAD platform.',
  'Zookeeper is a conversational agent that designs parts from natural language.',
  'Zoo generates true B-rep geometry that is fully editable and parametric.',
  'Designs can be created by clicking, coding, or prompting.',
  'Zoo gives manufacturing-aware feedback as you model.',
  'Zoo runs on Windows, Mac, Linux, and even in the browser.',
  'Zoo supports ITAR-compliant workflows in a US-regulated region.',
  'Zoo is SOC 2 Type II audited for security and reliability.',
  'Zoo is headquartered at 8701 Aviation Blvd, Inglewood, California.',
] as const;
interface ModelGenerationPageProps {
  project: Project | null;
  onProjectUpdate?: (updated: Project) => void;
}

export const ModelGenerationPage: React.FC<ModelGenerationPageProps> = ({
  project,
  onProjectUpdate,
}) => {
  const navigate = useNavigate();
  const canProceedToReview = Boolean(project && hasValidCurrentModel(project));

  const [readiness, setReadiness] = useState<ConnectionValidationResult | null>(null);
  const [readinessLoading, setReadinessLoading] = useState<boolean>(true);
  const [compileState, setCompileState] = useState<{
    loading: boolean;
    result: KCLCompileResult | null;
    error: string | null;
  }>({
    loading: false,
    result: null,
    error: null,
  });

  const [selectedScenario] = useState<MockScenario>('success');
  const [activeJob, setActiveJob] = useState<GenerationJob | null>(null);
  const [loadingDialogueIndex, setLoadingDialogueIndex] = useState(0);
  const [jobState, setJobState] = useState<{
    loading: boolean;
    error: string | null;
  }>({
    loading: false,
    error: null,
  });

  useEffect(() => {
    const isGenerating = activeJob?.status === 'queued' || activeJob?.status === 'running';
    if (!isGenerating) {
      setLoadingDialogueIndex(0);
      return;
    }

    const timer = window.setInterval(() => {
      setLoadingDialogueIndex((current) => (current + 1) % ZOO_LOADING_DIALOGUES.length);
    }, 4500);
    return () => window.clearInterval(timer);
  }, [activeJob?.status]);

  const checkReadiness = useCallback(async () => {
    if (!project) return;
    setReadinessLoading(true);
    try {
      const res = await fetchKclReadiness(project.project_id, project.project_token);
      setReadiness(res);
      setReadinessLoading(false);
    } catch {
      setReadinessLoading(false);
    }
  }, [project]);

  useEffect(() => {
    if (project) {
      checkReadiness();
    }
  }, [project, checkReadiness]);

  useEffect(() => {
    if (!project) return;
    fetchActiveGeneration(project.project_id, project.project_token)
      .then((job) => { if (job) setActiveJob(job); })
      .catch(() => { /* the readiness card remains usable */ });
  }, [project]);

  const refreshProjectData = useCallback(async () => {
    if (!project) return;
    try {
      const updated = await fetchProject(project.project_id, project.project_token);
      if (onProjectUpdate) {
        onProjectUpdate(updated);
      }
    } catch {
      // Ignore background refresh errors
    }
  }, [project, onProjectUpdate]);

  const handleCompileKcl = async () => {
    if (!project) return;
    setCompileState({ loading: true, result: null, error: null });
    try {
      const res = await compileKcl(project.project_id, project.project_token);
      if (res.success) {
        setCompileState({ loading: false, result: res, error: null });
      } else {
        const errMsg = res.errors.length > 0 ? res.errors[0].message : 'KCL Compilation failed.';
        setCompileState({ loading: false, result: res, error: errMsg });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Compilation request failed.';
      setCompileState({ loading: false, result: null, error: msg });
    }
  };

  const handleStartGeneration = async () => {
    if (!project) return;
    setJobState({ loading: true, error: null });
    try {
      const job = await startGeneration(project.project_id, project.project_token, selectedScenario);
      setActiveJob(job);
      setJobState({ loading: false, error: null });
      await refreshProjectData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start generation job.';
      if (msg.includes('[IF-JOB-409]')) {
        try {
          const existing = await fetchActiveGeneration(project.project_id, project.project_token);
          if (existing) {
            setActiveJob(existing);
            setJobState({ loading: false, error: null });
            return;
          }
        } catch {
          // Preserve the original server error when the recovery lookup fails.
        }
      }
      setJobState({ loading: false, error: msg });
    }
  };

  const handleCancelGeneration = async () => {
    if (!project || !activeJob) return;
    setJobState({ loading: true, error: null });
    try {
      const cancelled = await cancelGeneration(
        project.project_id,
        activeJob.job_id,
        project.project_token
      );
      setActiveJob(cancelled);
      setJobState({ loading: false, error: null });
      await refreshProjectData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to cancel generation job.';
      setJobState({ loading: false, error: msg });
    }
  };

  const handleRetryGeneration = async () => {
    if (!project || !activeJob) return;
    setJobState({ loading: true, error: null });
    try {
      const retried = await retryGeneration(
        project.project_id,
        activeJob.job_id,
        project.project_token,
        selectedScenario
      );
      setActiveJob(retried);
      setJobState({ loading: false, error: null });
      await refreshProjectData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retry generation job.';
      setJobState({ loading: false, error: msg });
    }
  };

  if (!project) {
    return (
      <div className="placeholder-page" role="region" aria-label="Step 4 Model Generation">
        <div className="placeholder-card">
          <span className="step-tag">Step 4 of 5</span>
          <h1>No Active Project</h1>
          <p className="placeholder-description">
            Please start a project and approve both interfaces before generating 3D models.
          </p>
          <button className="btn btn-primary" onClick={() => navigate('/step1')}>
            Go to Step 1
          </button>
        </div>
      </div>
    );
  }

  const isReadyToCompile = readiness?.is_valid ?? false;
  const isJobActive = activeJob?.status === 'queued' || activeJob?.status === 'running';
  const isJobSucceeded = activeJob?.status === 'succeeded';
  const isJobFailed = activeJob?.status === 'failed';
  const isJobCancelled = activeJob?.status === 'cancelled';

  const stagesList = [
    { key: 'validating', label: 'Validating' },
    { key: 'compiling', label: 'Compiling' },
    { key: 'executing', label: 'Executing' },
    { key: 'rendering', label: 'Rendering' },
    { key: 'finalizing', label: 'Finalizing' },
  ];

  return (
    <div className="model-generation-page" role="region" aria-labelledby="step4-heading">
      {/* Header Banner */}
      <div className="page-header-banner">
        <div>
          <span className="step-tag">Step 4 of 5</span>
          <h1 id="step4-heading">3D Model Generation &amp; Staged Pipeline</h1>
          <p className="subtitle">
            Compile deterministic KCL and execute staged 3D geometry generation using the Zoo Engine provider abstraction.
          </p>
        </div>
        <div className="header-status-badge">
          {project.state === 'model_current' ? (
            <span className="badge badge-success" aria-live="polite">
                [MODEL CURRENT REV {project.current_model_revision}]
            </span>
          ) : isJobSucceeded ? (
            <span className="badge badge-success" aria-live="polite">
                [GENERATION SUCCEEDED]
            </span>
          ) : isJobActive ? (
            <span className="badge badge-info" aria-live="polite">
                [JOB RUNNING STAGE: {activeJob?.current_stage.toUpperCase()}]
            </span>
          ) : isJobFailed ? (
            <span className="badge badge-error" aria-live="polite">
                [GENERATION FAILED]
            </span>
          ) : isReadyToCompile ? (
            <span className="badge badge-info" aria-live="polite">
                [READY TO GENERATE]
            </span>
          ) : (
            <span className="badge badge-error" aria-live="polite">
                [CONFIGURATION INCOMPLETE]
            </span>
          )}
        </div>
      </div>

      {/* Pre-flight Readiness Summary & KCL Compilation */}
      <section className="readiness-card" aria-labelledby="readiness-heading">
        <h2 id="readiness-heading" className="card-title">Pre-Flight Readiness &amp; KCL Emitter</h2>
        {readinessLoading ? (
          <div className="loading-state" aria-live="polite">
            <span className="spinner"></span> Validating schema compile readiness...
          </div>
        ) : readiness?.is_valid ? (
          <div className="readiness-success-panel">
            <p className="status-text">
                Both Interface A and Interface B are approved, and connection parameters satisfy geometric validation rules.
            </p>
            <div className="readiness-details-grid">
              <div className="readiness-detail-item">
                <span className="label">Interface A:</span>
                <span className="val">{project?.interface_a?.profile_type ?? 'N/A'} ({project?.interface_a?.approved ? 'Approved' : 'Pending'})</span>
              </div>
              <div className="readiness-detail-item">
                <span className="label">Interface B:</span>
                <span className="val">{project?.interface_b?.profile_type ?? 'N/A'} ({project?.interface_b?.approved ? 'Approved' : 'Pending'})</span>
              </div>
              <div className="readiness-detail-item">
                <span className="label">Connection Mode:</span>
                <span className="val">{project?.connection ? `${project.connection.mode} (${project.connection.length_mm} mm)` : 'N/A'}</span>
              </div>
              <div className="readiness-detail-item">
                <span className="label">Schema Revision:</span>
                <span className="val">Rev {project?.current_schema_revision ?? 1}</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="readiness-error-panel" aria-live="assertive">
            <p className="error-text"> Pre-flight readiness check failed:</p>
            <ul className="error-list">
              {readiness?.blocking_errors.map((err) => (
                <li key={err.id}>
                  <strong>[{err.id}]</strong> {err.message}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="compile-action-row" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginTop: '1rem' }}>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={!isReadyToCompile || compileState.loading}
            onClick={handleCompileKcl}
          >
            {compileState.loading ? 'Compiling KCL...' : 'Compile KCL Code'}
          </button>
          <button
            type="button"
            className="btn btn-primary btn-large"
            disabled={!isReadyToCompile || isJobActive || jobState.loading}
            onClick={handleStartGeneration}
          >
            {jobState.loading ? 'Launching Generation...' : ' Start 3D Generation'}
          </button>
        </div>
      </section>

      {/* Compiler Artifact Output Panel */}
      {compileState.result && compileState.result.success && (
        <section className="kcl-output-card" aria-labelledby="kcl-output-heading">
          <div className="card-header-row">
            <h2 id="kcl-output-heading" className="card-title">Generated KCL Artifact Metadata</h2>
            <span className="hash-badge" title="SHA-256 Hash">
              SHA256: {compileState.result.kcl_hash?.substring(0, 16)}...
            </span>
          </div>

          <div className="meta-grid">
            <div className="meta-item">
              <span className="meta-label">Compiler Version</span>
              <span className="meta-val">{compileState.result.compiler_version}</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Schema Revision</span>
              <span className="meta-val">Rev {compileState.result.schema_revision}</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Artifact Reference</span>
              <span className="meta-val code-path">{compileState.result.artifact_ref}</span>
            </div>
          </div>

          {/* Source Code Preview */}
          <div className="code-preview-container">
            <div className="code-header">
              <span>Source Preview ({compileState.result.artifact_ref})</span>
              <span className="units-tag">Units: mm</span>
            </div>
            <pre className="kcl-code-block" tabIndex={0} aria-label="KCL Source Code Preview">
              <code>{compileState.result.preview_snippet || compileState.result.kcl_code}</code>
            </pre>
          </div>

          <div className="kcl-card-footer">
            <a
              href="https://zoo.dev/design-studio/download"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-primary"
            >
              Download Zoo Design Studio | Zoo
            </a>
          </div>
        </section>
      )}

      {/* Staged Generation Progress Panel */}
      {activeJob && (
        <section className="generation-progress-card" aria-labelledby="job-progress-heading">
          <div className="card-header-row">
            <h2 id="job-progress-heading" className="card-title">
              Generation Job [{activeJob.job_id}]
            </h2>
            <span className={`status-badge-inline status-${activeJob.status}`}>
              {activeJob.status.toUpperCase()}
            </span>
          </div>

          {/* Staged Progress Bar */}
          <div className="staged-progress-container">
            {isJobActive && (
              <div className="generation-loading-header" aria-live="polite">
                <div>
                  <span className="generation-loading-label">Zoo Engine generation progress</span>
                  <strong className="generation-loading-percent">{Math.round(activeJob.progress_percent)}%</strong>
                </div>
                <div className="generation-loading-dialogue" role="status">
                  <strong>While Zoo is thinking:</strong> {ZOO_LOADING_DIALOGUES[loadingDialogueIndex]}
                </div>
              </div>
            )}
            <div className="progress-bar-track">
              <div
                className={`progress-bar-fill ${activeJob.status}`}
                style={{ width: `${activeJob.progress_percent}%` }}
              ></div>
            </div>

            <div className="stage-steps-row">
              {stagesList.map((stg) => {
                const isActive = activeJob.current_stage === stg.key;
                const isPassed =
                  activeJob.status === 'succeeded' ||
                  (activeJob.progress_percent > 0 &&
                    stagesList.findIndex((s) => s.key === stg.key) <
                      stagesList.findIndex((s) => s.key === activeJob.current_stage));
                return (
                  <div
                    key={stg.key}
                    className={`stage-step-item ${
                      isActive ? 'active' : isPassed ? 'passed' : ''
                    }`}
                  >
                    <span className="stage-dot"></span>
                    <span className="stage-name">{stg.label}</span>
                  </div>
                );
              })}
            </div>

            <div className="current-stage-callout">
              <strong>Current Stage:</strong> <span className="stage-highlight">{activeJob.current_stage.toUpperCase()}</span> ({activeJob.progress_percent}%)
            </div>
          </div>

          {/* Action Row: Cancel & Retry */}
          <div className="job-actions-row">
            {isJobActive && (
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleCancelGeneration}
                disabled={jobState.loading}
              >
                  Cancel Generation
              </button>
            )}

            {(isJobFailed || isJobCancelled) && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleRetryGeneration}
                disabled={jobState.loading}
              >
                  Retry Generation
              </button>
            )}
          </div>

          {/* Service Failure State & Recovery Steps */}
          {(isJobFailed || isJobCancelled) && (
            <div className="failure-details-panel" role="alert">
              <h3> Generation Failure Notice [{activeJob.error_id || 'IF-ENG-ERR'}]</h3>
              <p className="failure-message">{activeJob.error_message}</p>
              {activeJob.recovery_steps.length > 0 && (
                <div className="recovery-steps-box">
                  <strong>Recommended Recovery Steps:</strong>
                  <ul>
                    {activeJob.recovery_steps.map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ul>
                </div>
              )}
              {/* Last Known Good Model Status Callout (ADR-005) */}
              <div className="last-known-good-banner">
                {project.last_known_good_model_revision ? (
                  <p className="lkg-text">
                      <strong>Last-Known-Good Model Preserved:</strong> Revision {project.last_known_good_model_revision} remains active as current model.
                  </p>
                ) : (
                  <p className="lkg-text">
                      <strong>No Last-Known-Good Model:</strong> Project does not currently have an active valid model.
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Preview Artifact & Model Summary */}
          {isJobSucceeded && activeJob.preview_metadata && (
            <div className="preview-container-card">
              <h3> Generated 3D Adapter Preview</h3>
              <GeometryPreview
                project={project}
                boundingBox={activeJob.preview_metadata.bounding_box}
                volumeCm3={activeJob.preview_metadata.volume_cm3}
                className="preview-svg-wrapper"
                featured
                summary={
                  <div className="model-summary-panel">
                    <h4>Model Summary Specs</h4>
                    <div className="summary-grid">
                      <div className="summary-item">
                        <span className="s-label">Model Revision:</span>
                        <span className="s-val">Rev {activeJob.model_revision}</span>
                      </div>
                      <div className="summary-item">
                        <span className="s-label">Estimated Volume:</span>
                        <span className="s-val">{activeJob.preview_metadata.volume_cm3} cm3</span>
                      </div>
                      <div className="summary-item">
                        <span className="s-label">Bounding Box:</span>
                        <span className="s-val">
                          {activeJob.preview_metadata.bounding_box.x_mm} - {activeJob.preview_metadata.bounding_box.y_mm} - {activeJob.preview_metadata.bounding_box.z_mm} mm
                        </span>
                      </div>
                      <div className="summary-item">
                        <span className="s-label">Facet Count:</span>
                        <span className="s-val">{activeJob.preview_metadata.facet_count} facets</span>
                      </div>
                      <div className="summary-item">
                        <span className="s-label">Rendered At:</span>
                        <span className="s-val">{new Date(activeJob.preview_metadata.render_timestamp).toLocaleString()}</span>
                      </div>
                      <div className="summary-item">
                        <span className="s-label">Status:</span>
                        <span className="s-val badge badge-success"> CURRENT</span>
                      </div>
                    </div>
                  </div>
                }
              />
            </div>
          )}
        </section>
      )}

      {/* Global Error Alert */}
      {jobState.error && (
        <div className="compile-error-banner" role="alert">
          <h3> Request Error</h3>
          <p>{jobState.error}</p>
        </div>
      )}

      {/* Footer Navigation */}
      <div className="navigation-footer">
        <button type="button" className="btn btn-secondary" onClick={() => navigate('/step3')}>
            Back to Connection Config
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => navigate('/step5')}
          disabled={!isJobSucceeded && !canProceedToReview}
        >
          Proceed to Review &amp; Export (Step 5)
        </button>
      </div>
    </div>
  );
};
