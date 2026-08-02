import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Project, ModelRevision, AgentProposalResult } from '../types/schema';
import { GeometryPreview } from '../components/GeometryPreview';
import {
  fetchCurrentKcl,
  fetchExportStatus,
  generateExports,
  getExportDownloadUrl,
  proposeRevision,
  confirmRevision,
  fetchGenerationStatus,
  fetchProject,
  validateConnectionConfig,
  startGeneration,
  retryFormatExport,
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
interface ResultPageProps {
  project: Project | null;
  onProjectUpdate?: (updated: Project) => void;
  onRestartProject?: () => void;
}

export const ResultPage: React.FC<ResultPageProps> = ({
  project,
  onProjectUpdate,
  onRestartProject,
}) => {
  const navigate = useNavigate();
  const [showKclCode, setShowKclCode] = useState(false);
  const [copiedKcl, setCopiedKcl] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);
  const [kclArtifact, setKclArtifact] = useState<{ text: string; kcl_hash: string } | null>(null);
  const [exportStatus, setExportStatus] = useState<import('../types/schema').ExportStatusResponse | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [generatingFormats, setGeneratingFormats] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    if (!project) return () => { cancelled = true; };
    Promise.all([
      fetchExportStatus(project.project_id, project.project_token),
      fetchCurrentKcl(project.project_id, project.project_token),
    ]).then(([status, kcl]) => {
      if (!cancelled) {
        setExportStatus(status);
        setKclArtifact({ text: kcl.text, kcl_hash: kcl.kcl_hash });
      }
    }).catch((err: unknown) => {
      if (!cancelled) setExportError(err instanceof Error ? err.message : 'Failed to load export status.');
    });
    return () => { cancelled = true; };
  }, [project]);



  // Model Revision Panel State (Stage S9 Bounded Zoo Agent Revisions)
  const [revisionPrompt, setRevisionPrompt] = useState('');
  const [isProposing, setIsProposing] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [proposal, setProposal] = useState<AgentProposalResult | null>(null);
  const [proposalError, setProposalError] = useState<string | null>(null);
  const [regenerationError, setRegenerationError] = useState<string | null>(null);
  const [regenerationJob, setRegenerationJob] = useState<import('../types/schema').GenerationJob | null>(null);
  const [previewProject, setPreviewProject] = useState<Project | null>(null);
  const [previewMetadata, setPreviewMetadata] = useState<import('../types/schema').PreviewMetadata | null>(null);
  const [loadingDialogueIndex, setLoadingDialogueIndex] = useState(0);
  const isPipelineBusy = isConfirming || regenerationJob?.status === 'queued' || regenerationJob?.status === 'running' || regenerationJob?.status === 'cancel_requested';

  useEffect(() => {
    const isGenerating = regenerationJob?.status === 'queued' || regenerationJob?.status === 'running';
    if (!isGenerating) {
      setLoadingDialogueIndex(0);
      return;
    }
    const timer = window.setInterval(() => {
      setLoadingDialogueIndex((current) => (current + 1) % ZOO_LOADING_DIALOGUES.length);
    }, 4500);
    return () => window.clearInterval(timer);
  }, [regenerationJob?.status]);


  if (!project) {
    return (
      <div className="placeholder-page container" role="region" aria-label="Step 5 Review & Export">
        <div className="placeholder-card">
          <span className="step-tag">Step 5 of 5</span>
          <h1>No Active Project</h1>
          <p className="placeholder-description">
            Please start a project and complete model generation before reviewing export options.
          </p>
          <button className="btn btn-primary" onClick={() => navigate('/step1')}>
            Go to Step 1
          </button>
        </div>
      </div>
    );
  }

  // Find active or last known good model revision
  const currentRevNumber = project?.current_model_revision || project?.last_known_good_model_revision;
  const revisions = project?.model_revisions || [];
  const activeRev: ModelRevision | undefined = revisions.find(
    (r) => r.model_revision === currentRevNumber
  ) || revisions[revisions.length - 1];

  const isStale = project?.state === 'model_stale' || activeRev?.status === 'stale';
  const isFailedPreserved =
    (project?.state === 'generation_failed' || activeRev?.status === 'failed') &&
    project?.last_known_good_model_revision !== null && project?.last_known_good_model_revision !== undefined;

  const interfaceA = project?.interface_a;
  const interfaceB = project?.interface_b;
  const conn = project?.connection;
  const mfg = project?.manufacturing;



  const handleCopyKcl = async () => {
    if (!kclArtifact?.text) return;
    await navigator.clipboard.writeText(kclArtifact.text);
    setCopiedKcl(true);
    setTimeout(() => setCopiedKcl(false), 2000);
  };

  const handleDownloadKcl = () => {
    if (isPipelineBusy || exportStatus?.formats.kcl?.status !== 'ready') return;
    window.open(getExportDownloadUrl(project.project_id, 'kcl', project.project_token), '_blank', 'noopener,noreferrer');
  };

  const refreshExportStatus = async () => {
    const status = await fetchExportStatus(project.project_id, project.project_token);
    setExportStatus(status);
    return status;
  };

  const handleExport = async (format: string) => {
    const detail = exportStatus?.formats[format];
    if (isPipelineBusy) return;
    if (detail?.status === 'ready') {
      window.open(getExportDownloadUrl(project.project_id, format, project.project_token), '_blank', 'noopener,noreferrer');
      return;
    }
    setExportError(null);
    setGeneratingFormats((current) => new Set(current).add(format));
    try {
      if (detail?.status === 'failed') {
        await retryFormatExport(project.project_id, format, project.project_token);
      } else {
        await generateExports(project.project_id, [format], project.project_token);
      }
      await refreshExportStatus();
    } catch (err: unknown) {
      setExportError(err instanceof Error ? err.message : `Failed to generate ${format.toUpperCase()}.`);
      try { await refreshExportStatus(); } catch { /* preserve the backend error */ }
    } finally {
      setGeneratingFormats((current) => {
        const next = new Set(current);
        next.delete(format);
        return next;
      });
    }
  };

  const renderExportAction = (format: string, label: string) => {
    const detail = exportStatus?.formats[format];

    const isGenerating = generatingFormats.has(format) || detail?.status === 'preparing';
    const statusLabel = isGenerating ? 'Generating' : detail?.status === 'unavailable' ? 'Unavailable in offline mode' : detail?.status === 'failed' ? 'Failed' : detail?.status === 'ready' ? 'Ready' : 'Not generated';
    const statusColor = detail?.status === 'failed' ? '#f85149' : detail?.status === 'unavailable' ? '#d29922' : detail?.status === 'ready' ? '#3fb950' : '#8b949e';
    if (detail?.status === 'ready') {
      return <div><div style={{ color: statusColor, fontSize: '0.75rem', marginBottom: '0.35rem' }}>{statusLabel}</div><button type="button" className={`btn btn-primary btn-sm export-action-button export-action-button-ready${isPipelineBusy ? ' export-action-button-pipeline-busy' : ''}`} disabled={isPipelineBusy} onClick={() => handleExport(format)} style={{ width: '100%', opacity: isPipelineBusy ? 0.5 : 1 }}>Download {label}</button></div>;
    }
    if (detail?.status === 'unavailable') {
      return <div><div style={{ color: statusColor, fontSize: '0.75rem', marginBottom: '0.35rem' }}>{statusLabel}</div></div>;
    }
    const actionLabel = isGenerating ? `Generating ${label}` : detail?.status === 'failed' ? `Retry ${label}` : `Generate ${label}`;
    return <div><div style={{ color: statusColor, fontSize: '0.75rem', marginBottom: '0.35rem' }}>{statusLabel}</div><button type="button" className={`btn btn-sm export-action-button export-action-button-pending${isPipelineBusy ? ' export-action-button-pipeline-busy' : ''}`} disabled={isPipelineBusy || isGenerating || isStale} onClick={() => handleExport(format)} style={{ width: '100%', opacity: isPipelineBusy || isStale ? 0.5 : 1 }}>{actionLabel}</button></div>;
  };
  // Stage S9 Revision Handlers
  const handleProposeRevision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!revisionPrompt.trim()) return;

    setIsProposing(true);
    setProposalError(null);
    setRegenerationError(null);
    setProposal(null);

    try {
      const res = await proposeRevision(project.project_id, revisionPrompt, project.project_token);
      setProposal(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to generate revision proposal';
      setProposalError(msg);
    } finally {
      setIsProposing(false);
    }
  };

  const handleConfirmRevision = async () => {
    if (!proposal || !proposal.changes || proposal.changes.length === 0) return;

    setIsConfirming(true);
    setRegenerationError(null);

    try {
      const res = await confirmRevision(project.project_id, proposal.changes, project.project_token);
      if (onProjectUpdate) onProjectUpdate(res.project);
      setProposal(null);
      setRevisionPrompt('');

      setRegenerationJob({
        job_id: 'pending_revision_' + Date.now(),
        project_id: project.project_id,
        model_revision: (project.current_model_revision || 0) + 1,
        status: 'queued',
        current_stage: 'validating',
        progress_percent: 0,
        mock_scenario: 'success',
        recovery_steps: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
      const queuedJob = await startGeneration(project.project_id, project.project_token);
      setRegenerationJob(queuedJob);
      let latestJob = queuedJob;
      while (latestJob.status === 'queued' || latestJob.status === 'running' || latestJob.status === 'cancel_requested') {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        latestJob = await fetchGenerationStatus(project.project_id, latestJob.job_id, project.project_token);
        setRegenerationJob(latestJob);
      }

      if (latestJob.status !== 'succeeded') {
        throw new Error(latestJob.error_message || 'The updated model could not be generated.');
      }
      setPreviewMetadata(latestJob.preview_metadata || null);
      let updatedProject = await fetchProject(project.project_id, project.project_token);
      if (!updatedProject.loft_plan?.sections?.length) {
        const refreshedGeometry = await validateConnectionConfig(
          updatedProject.project_id,
          updatedProject.connection,
          updatedProject.manufacturing,
          updatedProject.project_token,
        );
        if (refreshedGeometry.loft_plan?.sections?.length) {
          updatedProject = { ...updatedProject, loft_plan: refreshedGeometry.loft_plan };
        }
      }
      setPreviewProject(updatedProject);
      if (onProjectUpdate) onProjectUpdate(updatedProject);
      const [status, kcl] = await Promise.all([
        fetchExportStatus(project.project_id, project.project_token),
        fetchCurrentKcl(project.project_id, project.project_token),
      ]);
      setExportStatus(status);
      setKclArtifact({ text: kcl.text, kcl_hash: kcl.kcl_hash });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Regeneration failed during revision confirmation.';
      setRegenerationError(msg);
    } finally {
      setIsConfirming(false);
    }
  };

  const handleCancelRevision = () => {
    setProposal(null);
    setProposalError(null);
  };

  const getStatusBadgeClass = (status?: string) => {
    switch (status) {
      case 'current':
        return 'badge-success';
      case 'stale':
        return 'badge-warning';
      case 'failed':
        return 'badge-danger';
      default:
        return 'badge-info';
    }
  };

  return (
    <div className="result-page container" role="region" aria-label="Step 5 Review and Export">
      {/* Top Banner & Header */}
      <div className="page-header" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <span className="step-tag" style={{ background: '#1f6feb', color: '#fff', padding: '0.2rem 0.6rem', borderRadius: '4px', fontSize: '0.8rem', fontWeight: 'bold' }}>
              Step 5 of 5
            </span>
            <h1 className="page-title" style={{ marginTop: '0.5rem', marginBottom: '0.25rem' }}>
              Review &amp; Export Adapter Design
            </h1>
            <p className="page-subtitle" style={{ color: '#8b949e', margin: 0 }}>
              Verify the adapter candidate, inspection values, deterministic KCL, and export readiness.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <span className={`badge ${getStatusBadgeClass(activeRev?.status)}`} style={{ padding: '0.4rem 0.8rem', borderRadius: '4px', fontWeight: 'bold', fontSize: '0.85rem' }}>
              MODEL STATUS: {(activeRev?.status || project.state).toUpperCase()}
            </span>
            <span className="badge badge-info" style={{ padding: '0.4rem 0.8rem', borderRadius: '4px', background: '#21262d', color: '#c9d1d9', border: '1px solid #30363d' }}>
              Model Rev: #{currentRevNumber || 1}
            </span>
            <span className="badge badge-info" style={{ padding: '0.4rem 0.8rem', borderRadius: '4px', background: '#21262d', color: '#c9d1d9', border: '1px solid #30363d' }}>
              Schema Rev: #{project.current_schema_revision}
            </span>
          </div>
        </div>
      </div>

      {/* Warning Banners */}
      {regenerationJob && (regenerationJob.status === 'queued' || regenerationJob.status === 'running' || regenerationJob.status === 'cancel_requested') && (
        <section className="generation-progress-card" aria-labelledby="step5-job-progress-heading">
          <div className="card-header-row">
            <h2 id="step5-job-progress-heading" className="card-title">Updating model - please wait</h2>
            <span className={`status-badge-inline status-${regenerationJob.status}`}>
              {regenerationJob.status.toUpperCase()}
            </span>
          </div>
          <div className="staged-progress-container">
            <div className="generation-loading-header" aria-live="polite">
              <div>
                <span className="generation-loading-label">Zoo Engine generation progress</span>
                <strong className="generation-loading-percent">{Math.round(regenerationJob.progress_percent)}%</strong>
              </div>
              <div className="generation-loading-dialogue" role="status">
                <strong>While Zoo is thinking:</strong> {ZOO_LOADING_DIALOGUES[loadingDialogueIndex]}
              </div>
            </div>
            <div className="progress-bar-track">
              <div className={`progress-bar-fill ${regenerationJob.status}`} style={{ width: `${regenerationJob.progress_percent}%` }} />
            </div>
            <div className="current-stage-callout">
              <strong>Current Stage:</strong> <span className="stage-highlight">{regenerationJob.current_stage.toUpperCase()}</span> ({Math.round(regenerationJob.progress_percent)}%)
            </div>
          </div>
        </section>
      )}

      {isStale && (
        <div className="warning-banner" role="alert" style={{ background: 'rgba(210, 153, 34, 0.15)', borderLeft: '4px solid #d29922', padding: '1rem', borderRadius: '6px', marginBottom: '1.5rem', color: '#f0f6fc' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <strong style={{ color: '#d29922', fontSize: '1.05rem' }}> Model Parameters Modified (STALE)</strong>
              <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.9rem', color: '#c9d1d9' }}>
                Upstream profile dimensions or connection settings were modified after model generation. The model displayed below may not reflect the latest schema revision.
              </p>
            </div>
            <button type="button" className="btn btn-primary btn-sm" onClick={() => navigate('/step4')}>
                Re-generate Model in Step 4
            </button>
          </div>
        </div>
      )}

      {isFailedPreserved && (
        <div className="info-banner" role="alert" style={{ background: 'rgba(56, 139, 253, 0.15)', borderLeft: '4px solid #388bfd', padding: '1rem', borderRadius: '6px', marginBottom: '1.5rem', color: '#f0f6fc' }}>
          <strong style={{ color: '#58a6ff', fontSize: '1.05rem' }}> Preserved Last-Known-Good Model (Revision {project.last_known_good_model_revision})</strong>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.9rem', color: '#c9d1d9' }}>
            Per <strong>ADR-005</strong>, the latest generation attempt encountered an error, so the previous successful model (Revision {project.last_known_good_model_revision}) is preserved as current.
          </p>
        </div>
      )}

      {/* Stage S9 Bounded Natural Language Model Revisions Panel */}
      <div className="card revision-panel" style={{ background: '#161b22', border: '1px solid #00e676', borderRadius: '8px', padding: '1.5rem', marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.2rem', marginTop: 0, marginBottom: '0.5rem', color: '#00e676', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>-</span> Safe Model Revisions (Zoo Agent API)
        </h2>
        <p style={{ fontSize: '0.88rem', color: '#c9d1d9', marginTop: 0, marginBottom: '1rem' }}>
          Request natural-language adjustments to transition length, lateral offsets, angle inclination, wall thickness, or clearances.
          The AI proposes validated changes, which are only applied to the model after your explicit confirmation.
        </p>

        <form onSubmit={handleProposeRevision} style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <input
            type="text"
            className="input-field"
            value={revisionPrompt}
            onChange={(e) => setRevisionPrompt(e.target.value)}
            placeholder="e.g. 'Make it 20 mm longer', 'Move outlet 10 mm right and 5 mm up', 'Increase wall thickness to 3 mm'"
            disabled={isProposing || isConfirming || regenerationJob?.status === 'queued' || regenerationJob?.status === 'running'}
            style={{ flex: 1, minWidth: '280px', padding: '0.6rem 0.9rem', background: '#0d1117', border: '1px solid #30363d', color: '#f0f6fc', borderRadius: '6px' }}
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={isProposing || isConfirming || regenerationJob?.status === 'queued' || regenerationJob?.status === 'running' || !revisionPrompt.trim()}
            style={{ background: '#00e676', color: '#0d1117', border: 'none', fontWeight: 'bold', minWidth: '160px' }}
          >
            {isProposing ? 'Analyzing Prompt...' : 'Propose Revision'}
          </button>
        </form>

        {isProposing && (
          <div className="agent-thinking-progress" role="status" aria-live="polite">
            <div className="agent-thinking-progress-track" aria-hidden="true">
              <div className="agent-thinking-progress-fill" />
            </div>
            <span>Zoo Agent is thinking...</span>
          </div>
        )}

        {proposalError && (
          <div role="alert" style={{ background: 'rgba(248, 81, 73, 0.15)', borderLeft: '4px solid #f85149', padding: '0.75rem 1rem', borderRadius: '6px', marginBottom: '1rem', color: '#f0f6fc', fontSize: '0.9rem' }}>
            <strong style={{ color: '#f85149' }}>[IF-AGENT-400] Proposal Error:</strong> {proposalError}
          </div>
        )}

        {regenerationError && (
          <div role="alert" style={{ background: 'rgba(248, 81, 73, 0.15)', borderLeft: '4px solid #f85149', padding: '0.75rem 1rem', borderRadius: '6px', marginBottom: '1rem', color: '#f0f6fc', fontSize: '0.9rem' }}>
            <strong style={{ color: '#f85149' }}>[IF-ENG-001] Model Regeneration Failed:</strong> {regenerationError}
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: '#c9d1d9' }}>
              Per <strong>ADR-005</strong>, your previous model revision remains available and active.
            </p>
          </div>
        )}

        {/* Structured Proposal Review Box */}
        {proposal && (
          <div className="proposal-review-box" style={{ background: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', padding: '1.25rem', marginTop: '1rem' }}>
            <h3 style={{ margin: '0 0 0.5rem 0', color: '#58a6ff', fontSize: '1.05rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span></span> Proposed Parameter Revision Review
            </h3>
            <p style={{ color: '#f0f6fc', fontSize: '0.92rem', marginBottom: '1rem' }}>
              <strong>Summary:</strong> {proposal.summary}
            </p>

            {proposal.is_valid && proposal.changes.length > 0 && (
              <>
                <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '1rem', fontSize: '0.88rem', color: '#c9d1d9' }}>
                  <thead>
                    <tr style={{ background: '#161b22', borderBottom: '1px solid #30363d', textAlign: 'left' }}>
                      <th style={{ padding: '0.6rem' }}>Target Parameter Field</th>
                      <th style={{ padding: '0.6rem' }}>Current Trusted Value</th>
                      <th style={{ padding: '0.6rem' }}>Proposed New Value</th>
                      <th style={{ padding: '0.6rem' }}>Unit</th>
                      <th style={{ padding: '0.6rem' }}>Agent Rationale</th>
                    </tr>
                  </thead>
                  <tbody>
                    {proposal.changes.map((ch, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid #21262d' }}>
                        <td style={{ padding: '0.6rem', color: '#79c0ff', fontWeight: 'bold' }}>{ch.field}</td>
                        <td style={{ padding: '0.6rem' }}>{ch.current_value}</td>
                        <td style={{ padding: '0.6rem', color: '#00e676', fontWeight: 'bold' }}>{ch.proposed_value}</td>
                        <td style={{ padding: '0.6rem' }}>{ch.unit}</td>
                        <td style={{ padding: '0.6rem', color: '#8b949e' }}>{ch.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {proposal.validation_warnings.length > 0 && (
                  <div style={{ background: 'rgba(210, 153, 34, 0.15)', borderLeft: '4px solid #d29922', padding: '0.5rem 0.75rem', borderRadius: '4px', marginBottom: '1rem', fontSize: '0.85rem' }}>
                    <strong style={{ color: '#d29922' }}>Engineering Warnings:</strong>
                    <ul style={{ margin: '0.25rem 0 0 0', paddingLeft: '1.2rem', color: '#c9d1d9' }}>
                      {proposal.validation_warnings.map((w, idx) => (
                        <li key={idx}>[{w.id}] {w.message}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                  <button type="button" className="btn btn-secondary" onClick={handleCancelRevision} disabled={isConfirming || regenerationJob?.status === 'queued' || regenerationJob?.status === 'running'}>
                    Cancel Revision
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleConfirmRevision}
                    disabled={isConfirming || regenerationJob?.status === 'queued' || regenerationJob?.status === 'running'}
                    style={{ background: '#00e676', color: '#0d1117', border: 'none', fontWeight: 'bold' }}
                  >
                    {isConfirming ? 'Compiling & Generating 3D Model...' : ' Confirm & Regenerate 3D Model'}
                  </button>
                </div>
              </>
            )}

            {!proposal.is_valid && (
              <div style={{ background: 'rgba(248, 81, 73, 0.15)', borderLeft: '4px solid #f85149', padding: '0.75rem 1rem', borderRadius: '6px', marginTop: '0.5rem' }}>
                <strong style={{ color: '#f85149', display: 'block', marginBottom: '0.25rem' }}> Revision Request Rejected by Safety &amp; Boundary Controls:</strong>
                <ul style={{ margin: 0, paddingLeft: '1.2rem', color: '#c9d1d9', fontSize: '0.88rem' }}>
                  {proposal.validation_errors.map((err, idx) => (
                    <li key={idx} style={{ marginBottom: '0.25rem' }}>
                      <strong>[{err.id}]</strong> {err.message}
                      {err.recovery_steps && err.recovery_steps.length > 0 && (
                        <span style={{ display: 'block', color: '#8b949e', fontSize: '0.82rem' }}>
                          Recovery: {err.recovery_steps.join(' ')}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
                <div style={{ marginTop: '0.75rem', display: 'flex', justifyContent: 'flex-end' }}>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={handleCancelRevision}>
                    Dismiss
                  </button>
                </div>
              </div>
            )}

            {proposal.is_valid && proposal.changes.length === 0 && (
              <div style={{ background: 'rgba(56, 139, 253, 0.15)', borderLeft: '4px solid #388bfd', padding: '0.75rem 1rem', borderRadius: '6px', marginTop: '0.5rem' }}>
                <strong style={{ color: '#58a6ff' }}>Clarification Needed:</strong> {proposal.summary}
                <div style={{ marginTop: '0.75rem', display: 'flex', justifyContent: 'flex-end' }}>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={handleCancelRevision}>
                    Dismiss
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Main Grid: Preview & Specifications */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        {/* Left Column: 3D Model Preview Card */}
        <div className="card" style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '1.25rem' }}>
          <h2 style={{ fontSize: '1.1rem', marginTop: 0, marginBottom: '1rem', color: '#f0f6fc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span></span> 3D Geometry Preview
          </h2>

          <div className="preview-canvas-wrapper" style={{ background: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', height: '280px', display: 'flex', flexDirection: 'column', alignItems: 'stretch', justifyContent: 'center', position: 'relative', overflow: 'hidden' }}>
            <GeometryPreview
              key={(previewProject || project).current_model_revision || 'preview'}
              project={previewProject || project}
              boundingBox={previewMetadata?.bounding_box}
              volumeCm3={previewMetadata?.volume_cm3 ?? activeRev?.volume_cm3}
              className="step5-geometry-preview"
            />

            <div style={{ position: 'absolute', bottom: '10px', right: '10px', background: 'rgba(22, 27, 34, 0.85)', padding: '0.25rem 0.5rem', borderRadius: '4px', border: '1px solid #30363d', fontSize: '0.75rem', color: '#8b949e' }}>
              Mock Render Canvas
            </div>
          </div>

          <div className="preview-metadata-grid" style={{ marginTop: '1rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.85rem' }}>
            <div style={{ background: '#0d1117', padding: '0.5rem', borderRadius: '4px', border: '1px solid #21262d' }}>
              <span style={{ color: '#8b949e', display: 'block' }}>Estimated Volume:</span>
              <strong style={{ color: '#3fb950' }}>{exportStatus?.volume_cm3 ?? activeRev?.volume_cm3 ?? 'Not generated'} cm3</strong>
            </div>
            <div style={{ background: '#0d1117', padding: '0.5rem', borderRadius: '4px', border: '1px solid #21262d' }}>
              <span style={{ color: '#8b949e', display: 'block' }}>Bounding Box:</span>
              <strong style={{ color: '#c9d1d9' }}>Generated mesh bounds shown in the shared preview</strong>
            </div>
          </div>
        </div>

        {/* Right Column: Physical & Fabrication Specifications */}
        <div className="card" style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '1.25rem' }}>
          <h2 style={{ fontSize: '1.1rem', marginTop: 0, marginBottom: '1rem', color: '#f0f6fc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span></span> Adapter Candidate Specifications
          </h2>

          <div className="spec-table" style={{ fontSize: '0.88rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {/* Interface A */}
            <div style={{ background: '#0d1117', padding: '0.75rem', borderRadius: '6px', border: '1px solid #21262d' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                <strong style={{ color: '#58a6ff' }}>Interface A (Source Mating Face):</strong>
                <span style={{ color: '#3fb950', fontSize: '0.8rem', fontWeight: 'bold' }}> Approved</span>
              </div>
              <div style={{ color: '#c9d1d9' }}>
                Profile: <strong>{interfaceA.profile_type}</strong> | Dimensions:{' '}
                {interfaceA.dimensions.map((d) => `${d.label}: ${d.value}${d.unit}`).join(', ')}
              </div>
            </div>

            {/* Interface B */}
            <div style={{ background: '#0d1117', padding: '0.75rem', borderRadius: '6px', border: '1px solid #21262d' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                <strong style={{ color: '#58a6ff' }}>Interface B (Target Mating Face):</strong>
                <span style={{ color: '#3fb950', fontSize: '0.8rem', fontWeight: 'bold' }}> Approved</span>
              </div>
              <div style={{ color: '#c9d1d9' }}>
                Profile: <strong>{interfaceB.profile_type}</strong> | Dimensions:{' '}
                {interfaceB.dimensions.map((d) => `${d.label}: ${d.value}${d.unit}`).join(', ')}
              </div>
            </div>

            {/* Connection Spec */}
            <div style={{ background: '#0d1117', padding: '0.75rem', borderRadius: '6px', border: '1px solid #21262d' }}>
              <strong style={{ color: '#d29922', display: 'block', marginBottom: '0.25rem' }}>Connection Parameters:</strong>
              <div style={{ color: '#c9d1d9' }}>
                Mode: <strong>{conn.mode}</strong> | Length: <strong>{conn.length_mm} mm</strong> | Offsets: X={conn.offset_x_mm}mm, Y={conn.offset_y_mm}mm | Angle: {conn.angle_deg} deg
              </div>
            </div>

            {/* Fabrication Settings */}
            <div style={{ background: '#0d1117', padding: '0.75rem', borderRadius: '6px', border: '1px solid #21262d' }}>
              <strong style={{ color: '#a371f7', display: 'block', marginBottom: '0.25rem' }}>Fabrication Settings:</strong>
              <div style={{ color: '#c9d1d9' }}>
                Process: <strong>{mfg.process.toUpperCase()}</strong> | Material: <strong>{mfg.material}</strong> | Wall: {mfg.wall_thickness_mm} mm | Clearances: A={mfg.clearance_a_mm}mm, B={mfg.clearance_b_mm}mm
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Warnings & Inspection Panel */}
      {activeRev?.warnings && activeRev.warnings.length > 0 && (
        <div className="card" style={{ background: '#161b22', border: '1px solid #d29922', borderRadius: '8px', padding: '1rem', marginBottom: '1.5rem' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#d29922', fontSize: '1rem' }}>
              Model Warnings ({activeRev.warnings.length})
          </h3>
          <ul style={{ margin: 0, paddingLeft: '1.25rem', color: '#c9d1d9', fontSize: '0.9rem' }}>
            {activeRev.warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* KCL Code Viewer & Zoo Design Studio Integration Card */}
      <div className="card" style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '1.25rem', marginBottom: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2 style={{ fontSize: '1.1rem', margin: 0, color: '#f0f6fc' }}>
                Deterministic KCL Code Artifact
            </h2>
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: '#8b949e' }}>
              Deterministic KCL script compiled from the approved canonical project schema per ADR-001 &amp; ADR-002.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShowKclCode(!showKclCode)}>
              {showKclCode ? 'Hide KCL Code' : 'View KCL Code'}
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={handleCopyKcl}>
              {copiedKcl ? ' Copied!' : 'Copy KCL'}
            </button>
            <button type="button" className={`btn btn-secondary btn-sm${isPipelineBusy ? ' export-action-button-pipeline-busy' : ''}`} disabled={isPipelineBusy} onClick={handleDownloadKcl} style={{ opacity: isPipelineBusy ? 0.5 : 1 }}>
              Download .kcl
            </button>
            <a
              href="https://zoo.dev/design-studio/download"
              target="_blank"
              rel="noopener noreferrer"
              aria-disabled={isPipelineBusy}
              className={`btn btn-primary btn-sm${isPipelineBusy ? ' export-action-button-pipeline-busy' : ''}`}
              onClick={(event) => { if (isPipelineBusy) event.preventDefault(); }}
              style={{ opacity: isPipelineBusy ? 0.5 : 1, pointerEvents: isPipelineBusy ? 'none' : 'auto' }}
            >
              Download Zoo Design Studio | Zoo
            </a>
          </div>
        </div>

        {showKclCode && (
          <div style={{ marginTop: '1rem' }}>
            <pre style={{ background: '#0d1117', border: '1px solid #30363d', padding: '1rem', borderRadius: '6px', color: '#79c0ff', fontSize: '0.85rem', overflowX: 'auto', maxHeight: '300px' }}>
              <code>{kclArtifact?.text || "KCL artifact is not available."}</code>
            </pre>
          </div>
        )}
      </div>

      {/* Export Section & Actions */}
      <div className="card" style={{ background: '#161b22', border: '1px solid #1f6feb', borderRadius: '8px', padding: '1.5rem', marginBottom: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
          <div>
            <h2 style={{ fontSize: '1.2rem', margin: 0, color: '#f0f6fc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span></span> CAD File Export
            </h2>
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: '#8b949e' }}>
              Download STL and KCL artifacts from model revision #{currentRevNumber || 1}. Inspect exported files before manufacturing.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <span className="badge badge-info" style={{ background: '#21262d', color: '#c9d1d9', border: '1px solid #30363d', fontSize: '0.8rem' }}>
              Units: mm
            </span>
            <span className="badge badge-info" style={{ background: '#21262d', color: '#c9d1d9', border: '1px solid #30363d', fontSize: '0.8rem' }}>
              Model Rev: #{currentRevNumber || 1}
            </span>
          </div>
        </div>

        {exportError && (
          <div role="alert" style={{ background: "rgba(248, 81, 73, 0.15)", borderLeft: "4px solid #f85149", padding: "0.75rem 1rem", borderRadius: "6px", marginBottom: "1rem", color: "#f0f6fc" }}>
            {exportError}
          </div>
        )}


        {isStale && (
          <div className="export-notice-banner" style={{ background: 'rgba(210, 153, 34, 0.15)', borderLeft: '4px solid #d29922', padding: '1rem', borderRadius: '6px', marginBottom: '1.25rem' }}>
            <strong style={{ color: '#d29922', fontSize: '0.95rem' }}>
                Model is Stale Export Blocked
            </strong>
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: '#c9d1d9' }}>
              Upstream parameters have changed since last generation. Re-generate the 3D model in Step 4 before exporting.
            </p>
          </div>
        )}

        <div className="export-formats-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem', marginBottom: '1.5rem' }}>
          {/* STL Format Card */}
          <div style={{ background: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', padding: '1.25rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <strong style={{ color: '#f0f6fc', fontSize: '1rem' }}>STL Mesh (.stl)</strong>
                <span className="badge badge-success" style={{ fontSize: '0.7rem' }}>SLICER REVIEW</span>
              </div>
              <p style={{ fontSize: '0.8rem', color: '#8b949e', margin: '0 0 0.75rem 0' }}>
                Binary 3D mesh for slicer inspection and 3D-print preparation.
              </p>
            </div>
            <div>
              {renderExportAction('stl', 'STL (.stl)')}
            </div>
          </div>

          {/* STEP Format Card */}
          <div style={{ background: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', padding: '1.25rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <strong style={{ color: '#f0f6fc', fontSize: '1rem' }}>STEP Export (.step)</strong>
                <span className="badge badge-info" style={{ fontSize: '0.7rem' }}>PLANNED</span>
              </div>
              <p style={{ fontSize: '0.8rem', color: '#8b949e', margin: '0 0 0.75rem 0' }}>
                Editable STEP solid export will be added in a future iteration using the Zoo geometry pipeline.
              </p>
            </div>
            <div>
              <div style={{ color: '#8b949e', fontSize: '0.75rem', marginBottom: '0.35rem' }}>Future Feature</div>
              <button type="button" className="btn btn-sm export-action-button" disabled style={{ width: '100%', opacity: 0.5, cursor: 'not-allowed' }}>
                Planned
              </button>
            </div>
          </div>


          {/* KCL Code Format Card */}
          <div style={{ background: '#0d1117', border: '1px solid #238636', borderRadius: '6px', padding: '1.25rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <strong style={{ color: '#3fb950', fontSize: '1rem' }}>KCL Script (.kcl)</strong>
                <span className="badge badge-success" style={{ fontSize: '0.7rem' }}>PARAMETRIC</span>
              </div>
              <p style={{ fontSize: '0.8rem', color: '#8b949e', margin: '0 0 0.75rem 0' }}>
                Deterministic KittyCAD KCL artifact compiled from the approved canonical schema.
              </p>
            </div>
            <div>
              {renderExportAction('kcl', 'KCL (.kcl)')}
            </div>
          </div>
        </div>

        {/* Global Footer Actions */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', paddingTop: '1rem', borderTop: '1px solid #30363d' }}>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button type="button" className="btn btn-secondary" onClick={() => navigate('/step3')}>
                Revise Parameters (Step 3)
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => navigate('/step4')}>
                Re-generate Model (Step 4)
            </button>
          </div>

          {onRestartProject && (
            <button type="button" className="btn btn-tertiary" onClick={() => setShowExportModal(true)} style={{ color: '#f85149', borderColor: '#f85149' }}>
              Start New Project
            </button>
          )}
        </div>
      </div>

      {/* Exit / Restart Confirmation Modal */}
      {showExportModal && (
        <div className="modal-overlay" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0, 0, 0, 0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="modal-card" style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '1.5rem', maxWidth: '480px', width: '90%', color: '#f0f6fc' }}>
            <h3 style={{ marginTop: 0, color: '#f85149', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span></span> Restart Workflow?
            </h3>
            <p style={{ fontSize: '0.9rem', color: '#c9d1d9' }}>
              Are you sure you want to start a new project? Your current active project state will be reset in this browser session.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.25rem' }}>
              <button type="button" className="btn btn-secondary" onClick={() => setShowExportModal(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                style={{ background: '#da3633', borderColor: '#f85149' }}
                onClick={() => {
                  setShowExportModal(false);
                  if (onRestartProject) onRestartProject();
                }}
              >
                Confirm &amp; Restart
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ResultPage;
