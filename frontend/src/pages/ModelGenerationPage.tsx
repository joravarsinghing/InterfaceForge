import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Project, ConnectionValidationResult } from '../types/schema';
import { fetchKclReadiness, compileKcl, KCLCompileResult } from '../services/api';

interface ModelGenerationPageProps {
  project: Project | null;
  onProjectUpdate?: (updated: Project) => void;
}

export const ModelGenerationPage: React.FC<ModelGenerationPageProps> = ({
  project,
}) => {
  const navigate = useNavigate();

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

  const checkReadiness = useCallback(async () => {
    if (!project) return;
    setReadinessLoading(true);
    try {
      const res = await fetchKclReadiness(project.project_id, project.project_token);
      setReadiness(res);
      setReadinessLoading(false);
    } catch (err: unknown) {
      setReadinessLoading(false);
    }
  }, [project]);

  useEffect(() => {
    if (project) {
      checkReadiness();
    }
  }, [project, checkReadiness]);

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

  if (!project) {
    return (
      <div className="placeholder-page" role="region" aria-label="Step 4 Model Generation">
        <div className="placeholder-card">
          <span className="step-tag">Step 4 of 5</span>
          <h1>No Active Project</h1>
          <p className="placeholder-description">
            Please start a project and approve both interfaces before compiling KCL.
          </p>
          <button className="btn btn-primary" onClick={() => navigate('/step1')}>
            Go to Step 1
          </button>
        </div>
      </div>
    );
  }

  const isReadyToCompile = readiness?.is_valid ?? false;

  return (
    <div className="model-generation-page" role="region" aria-labelledby="step4-heading">
      {/* Header Banner */}
      <div className="page-header-banner">
        <div>
          <span className="step-tag">Step 4 of 5</span>
          <h1 id="step4-heading">Deterministic KCL Compiler</h1>
          <p className="subtitle">
            Convert validated canonical design schema into explicit, deterministic KCL code without invoking external APIs.
          </p>
        </div>
        <div className="header-status-badge">
          {compileState.result?.success ? (
            <span className="badge badge-success" aria-live="polite">
              ✓ [KCL COMPILED — AWAITING ZOO ENGINE EXECUTION]
            </span>
          ) : isReadyToCompile ? (
            <span className="badge badge-info" aria-live="polite">
              ✓ [COMPILE READINESS VERIFIED]
            </span>
          ) : (
            <span className="badge badge-error" aria-live="polite">
              ⛔ [CONFIGURATION INCOMPLETE]
            </span>
          )}
        </div>
      </div>

      {/* Pre-flight Readiness Summary */}
      <section className="readiness-card" aria-labelledby="readiness-heading">
        <h2 id="readiness-heading" className="card-title">Pre-Flight Readiness Check</h2>
        {readinessLoading ? (
          <div className="loading-state" aria-live="polite">
            <span className="spinner"></span> Validating schema compile readiness...
          </div>
        ) : readiness?.is_valid ? (
          <div className="readiness-success-panel">
            <p className="status-text">
              ✓ Both Interface A and Interface B are approved, and connection parameters satisfy geometric validation rules.
            </p>
            <div className="readiness-details-grid">
              <div className="readiness-detail-item">
                <span className="label">Interface A:</span>
                <span className="val">{project.interface_a.profile_type} ({project.interface_a.approved ? 'Approved' : 'Pending'})</span>
              </div>
              <div className="readiness-detail-item">
                <span className="label">Interface B:</span>
                <span className="val">{project.interface_b.profile_type} ({project.interface_b.approved ? 'Approved' : 'Pending'})</span>
              </div>
              <div className="readiness-detail-item">
                <span className="label">Connection Mode:</span>
                <span className="val">{project.connection.mode} ({project.connection.length_mm} mm)</span>
              </div>
              <div className="readiness-detail-item">
                <span className="label">Schema Revision:</span>
                <span className="val">Rev {project.current_schema_revision}</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="readiness-error-panel" aria-live="assertive">
            <p className="error-text">⛔ Pre-flight readiness check failed:</p>
            <ul className="error-list">
              {readiness?.blocking_errors.map((err) => (
                <li key={err.id}>
                  <strong>[{err.id}]</strong> {err.message}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="compile-action-row">
          <button
            type="button"
            className="btn btn-primary btn-large"
            disabled={!isReadyToCompile || compileState.loading}
            onClick={handleCompileKcl}
          >
            {compileState.loading ? 'Compiling KCL...' : 'Compile Deterministic KCL'}
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
            <div className="meta-item">
              <span className="meta-label">Execution Status</span>
              <span className="meta-val status-draft">Draft (Pending Zoo Execution)</span>
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
        </section>
      )}

      {/* Error Alert */}
      {compileState.error && (
        <div className="compile-error-banner" role="alert">
          <h3>⛔ Compilation Error</h3>
          <p>{compileState.error}</p>
        </div>
      )}

      {/* Footer Navigation */}
      <div className="navigation-footer">
        <button type="button" className="btn btn-secondary" onClick={() => navigate('/step3')}>
          ← Back to Connection Config
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => navigate('/step5')}
        >
          Proceed to Review &amp; Export (Step 5) →
        </button>
      </div>
    </div>
  );
};
