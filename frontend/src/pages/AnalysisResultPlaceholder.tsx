import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { approveInterface } from '../services/api';
import { AnalysisResult, Project } from '../types/schema';

interface AnalysisResultPlaceholderProps {
  interfaceId: 'interface_a' | 'interface_b';
  project: Project | null;
  analysisResult?: AnalysisResult | null;
  onProjectUpdate?: (project: Project) => void;
}

export const AnalysisResultPlaceholder: React.FC<AnalysisResultPlaceholderProps> = ({
  interfaceId,
  project,
  analysisResult,
  onProjectUpdate,
}) => {
  const navigate = useNavigate();
  const isInterfaceB = interfaceId === 'interface_b';
  const interfaceName = isInterfaceB ? 'Interface B' : 'Interface A';
  const interfaceData = isInterfaceB ? project?.interface_b : project?.interface_a;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const profileType =
    analysisResult?.profile_type || interfaceData?.profile_type || 'circle';
  const dimensions =
    analysisResult?.candidate_dimensions || interfaceData?.dimensions || [];
  const confidence = analysisResult?.confidence ?? 0.95;

  const handleApprove = async () => {
    if (!project) return;
    setLoading(true);
    setError(null);
    try {
      const updatedProject = await approveInterface(
        project.project_id,
        interfaceId,
        project.project_token
      );
      setLoading(false);
      if (onProjectUpdate) {
        onProjectUpdate(updatedProject);
      }
      navigate(isInterfaceB ? '/step3' : '/step2');
    } catch (err: unknown) {
      setLoading(false);
      setError(err instanceof Error ? err.message : 'Failed to approve interface');
    }
  };

  return (
    <div className="analysis-result-placeholder container">
      <h1 className="page-title">{interfaceName} Profile Analysis Result</h1>
      <p className="page-subtitle">
        Review profile candidate extracted by the analysis provider.
      </p>

      {error && (
        <div className="error-banner" role="alert">
          <p>{error}</p>
        </div>
      )}

      <div className="analysis-card">
        <header className="analysis-header">
          <div className="profile-badge">
            <span className="label">Detected Profile:</span>
            <strong className="value">{profileType}</strong>
          </div>
          <div className="confidence-badge">
            <span className="label">Confidence:</span>
            <strong className="value">{(confidence * 100).toFixed(0)}%</strong>
          </div>
        </header>

        <section className="dimensions-section">
          <h2>Extracted Candidate Dimensions</h2>
          {dimensions.length > 0 ? (
            <table className="dimensions-table">
              <thead>
                <tr>
                  <th>Parameter</th>
                  <th>Value</th>
                  <th>Unit</th>
                  <th>Provenance</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {dimensions.map((dim) => (
                  <tr key={dim.id}>
                    <td>{dim.label}</td>
                    <td><strong>{dim.value}</strong></td>
                    <td>{dim.unit}</td>
                    <td><code>{dim.provenance}</code></td>
                    <td>{(dim.confidence * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="empty-notice">No specific dimensions extracted.</p>
          )}
        </section>

        <div className="placeholder-notice">
          <p>
            <strong>Stage S4A Status:</strong> Mock profile analysis complete. SVG contour
            editing and vector parameter adjustment will be integrated in Stage S4B.
          </p>
        </div>

        <footer className="analysis-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate(isInterfaceB ? '/step2' : '/step1')}
          >
            Re-upload Image
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={loading}
            onClick={handleApprove}
          >
            {loading ? 'Approving...' : `Approve ${interfaceName}`}
          </button>
        </footer>
      </div>
    </div>
  );
};

export default AnalysisResultPlaceholder;
