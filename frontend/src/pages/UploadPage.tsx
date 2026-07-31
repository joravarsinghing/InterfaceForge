import React, { useState, useEffect, ChangeEvent, DragEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ImageGuidance, PreferredInput } from '../components/ImageGuidance';
import { SampleGallery } from '../components/SampleGallery';
import { getSampleFile, SampleAsset } from '../data/sampleManifest';
import { uploadInterfaceImage, analyzeInterfaceImage, fetchProject } from '../services/api';
import { getInterfaceStepPath } from '../services/workflow';
import { AnalysisResult, Project } from '../types/schema';

interface UploadPageProps {
  interfaceId: 'interface_a' | 'interface_b';
  project: Project | null;
  onAnalysisComplete?: (result: AnalysisResult) => void;
  /** Called with the refreshed Project after successful analysis so App state is updated before navigation. */
  onProjectUpdate?: (updated: Project) => void;
}

export const UploadPage: React.FC<UploadPageProps> = ({
  interfaceId,
  project,
  onAnalysisComplete,
  onProjectUpdate,
}) => {
  const location = useLocation();
  const navigate = useNavigate();
  const isReplaceMode = new URLSearchParams(location.search).get('replace') === '1';

  const isInterfaceB = interfaceId === 'interface_b';
  const interfaceName = isInterfaceB ? 'Interface B' : 'Interface A';
  const isPrerequisiteMet = !isInterfaceB || (project?.interface_a?.approved ?? false);

  useEffect(() => {
    if (!project || !isPrerequisiteMet || isReplaceMode) return;

    const resolvedPath = getInterfaceStepPath(project, interfaceId);
    const uploadPath = isInterfaceB ? '/step2' : '/step1';
    if (resolvedPath !== uploadPath) {
      navigate(resolvedPath, { replace: true });
    }
  }, [interfaceId, isInterfaceB, isPrerequisiteMet, isReplaceMode, navigate, project]);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);

  const handleFileSelect = (file: File) => {
    setError(null);
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
  };

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelect(e.target.files[0]);
    }
  };

  const handleKeyDownInputTrigger = (e: React.KeyboardEvent<HTMLLabelElement>, inputId: string) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      document.getElementById(inputId)?.click();
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleClear = () => {
    setSelectedFile(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
    setError(null);
  };

  const handleSelectSample = async (
    sample: SampleAsset,
    targetInterface: 'interface_a' | 'interface_b'
  ) => {
    if (!project) return;

    if (targetInterface === 'interface_b' && !(project?.interface_a?.approved ?? false)) {
      setError('Interface A must be reviewed and approved before uploading an image for Interface B.');
      return;
    }

    setLoading(true);
    setLoadingText('Preparing sample image...');
    setError(null);

    try {
      const file = await getSampleFile(sample);
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));

      setLoadingText('Uploading image file...');
      await uploadInterfaceImage(
        project.project_id,
        targetInterface,
        file,
        project.project_token
      );

      setLoadingText('Analyzing interface contours using AI vision model...');
      const result = await analyzeInterfaceImage(
        project.project_id,
        targetInterface,
        project.project_token
      );

      setAnalysisResult(result);
      setLoadingText('Refreshing project state...');

      let refreshedProject: Project | null = null;
      try {
        refreshedProject = await fetchProject(project.project_id, project.project_token);
      } catch (refreshErr: unknown) {
        if (import.meta.env.DEV) {
          console.error(
            '[UploadPage] Project refresh failed after successful analysis.',
            { project_id: project.project_id, interface_id: targetInterface, refreshErr }
          );
        }
        setLoading(false);
        setError(
          'Analysis succeeded but the project state could not be refreshed. ' +
          'Please retry or reload the page to continue.'
        );
        return;
      }

      if (onAnalysisComplete) {
        onAnalysisComplete(result);
      }
      if (onProjectUpdate && refreshedProject) {
        onProjectUpdate(refreshedProject);
      }

      setLoading(false);
      navigate(targetInterface === 'interface_b' ? '/step2/analysis' : '/step1/analysis');
    } catch (err: unknown) {
      setLoading(false);
      const msg = err instanceof Error ? err.message : 'An unexpected error occurred during sample upload.';
      if (import.meta.env.DEV) {
        console.error('[UploadPage] Sample upload or analysis request failed.', { err });
      }
      setError(msg);
    }
  };

  const handleUploadAndAnalyze = async (providerOverride?: string) => {
    if (!selectedFile || !project) {
      setError('Please select an image file to upload.');
      return;
    }

    setLoading(true);
    setLoadingText('Uploading image file...');
    setError(null);

    try {
      // 1. Upload image
      await uploadInterfaceImage(
        project.project_id,
        interfaceId,
        selectedFile,
        project.project_token,
      );

      // 2. Run analysis
      setLoadingText(
        providerOverride === 'mock'
          ? 'Running mock interface profile analysis...'
          : 'Analyzing interface contours using AI vision model...'
      );
      const result = providerOverride
        ? await analyzeInterfaceImage(
            project.project_id,
            interfaceId,
            project.project_token,
            providerOverride
          )
        : await analyzeInterfaceImage(
            project.project_id,
            interfaceId,
            project.project_token
          );

      setAnalysisResult(result);

      // 3. Refresh project so App-level state reflects updated source_image_ref and
      //  workflow state (interface_a_review_required) before navigation.
      setLoadingText('Refreshing project state...');
      let refreshedProject: Project | null = null;
      try {
        refreshedProject = await fetchProject(project.project_id, project.project_token);
      } catch (refreshErr: unknown) {
        if (import.meta.env.DEV) {
          console.error(
            '[UploadPage] Project refresh failed after successful analysis.',
            { project_id: project.project_id, interface_id: interfaceId, refreshErr }
          );
        }
        setLoading(false);
        setError(
          'Analysis succeeded but the project state could not be refreshed. ' +
          'Please retry or reload the page to continue.'
        );
        return;
      }

      if (onAnalysisComplete) {
        onAnalysisComplete(result);
      }
      if (onProjectUpdate && refreshedProject) {
        onProjectUpdate(refreshedProject);
      }

      setLoading(false);
      navigate(isInterfaceB ? '/step2/analysis' : '/step1/analysis');
    } catch (err: unknown) {
      setLoading(false);
      const msg = err instanceof Error ? err.message : 'An unexpected error occurred during upload.';
      if (import.meta.env.DEV) {
        console.error('[UploadPage] Upload or analysis request failed.', { err });
      }
      setError(msg);
    }
  };

  if (!isPrerequisiteMet) {
    return (
      <div className="upload-page container">
        <h1 className="page-title">{interfaceName} - Prerequisite Required</h1>
        <div className="error-banner" role="alert">
          <h2>Prerequisite Step Incomplete</h2>
          <p>Interface A must be reviewed and approved before you can upload an image for Interface B.</p>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate('/step1')}
          >
            Go to Interface A
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="upload-page container">
      <h1 className="page-title">{interfaceName} - Upload Image or Sketch</h1>
      <p className="page-subtitle">
        Capture the physical mating face that connects to the target product.
      </p>

      {error && (
        <div className="error-banner" role="alert" style={{ marginBottom: '1.5rem' }}>
          <h3>Upload / Analysis Error</h3>
          <p style={{ margin: '0.5rem 0 1rem 0' }}>{error}</p>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => handleUploadAndAnalyze()}
            >
                Retry Analysis
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => handleUploadAndAnalyze('mock')}
            >
                Switch to Demo / Mock Profile
            </button>
            <button
              type="button"
              className="btn btn-tertiary btn-sm"
              onClick={() => setError(null)}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="loading-state" role="status" aria-live="polite">
          <div className="spinner" />
          <p>{loadingText}</p>
        </div>
      ) : (
        <>
        <SampleGallery onSelectSample={handleSelectSample} currentInterface={interfaceId} disabled={loading} />

        <div className="upload-layout">
          <div className="upload-main">
            {!selectedFile ? (
              <div
                className={`dropzone ${isDragOver ? 'drag-over' : ''}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                <div className="dropzone-content">
                  <div className="dropzone-icon" aria-hidden="true"></div>
                  <p className="dropzone-text">Upload your own image or drag &amp; drop here</p>
                  <p className="dropzone-or">or</p>
                  <label
                    htmlFor="file-input"
                    className="btn btn-primary"
                    tabIndex={0}
                    onKeyDown={(e) => handleKeyDownInputTrigger(e, 'file-input')}
                  >
                    Choose Image File
                  </label>
                  <input
                    id="file-input"
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    className="sr-only"
                    onChange={handleInputChange}
                  />
                  <p className="file-info-text">
                    Supported formats: PNG, JPEG, WEBP (Max size: 10MB)
                  </p>
                </div>
              </div>
            ) : (
              <div className="preview-card">
                <h2>Selected Image Preview</h2>
                <div className="preview-container">
                  {previewUrl && (
                    <img
                      src={previewUrl}
                      alt={`Preview for ${selectedFile.name}`}
                      className="image-preview"
                    />
                  )}
                </div>
                <div className="file-meta-panel">
                  <div className="meta-item">
                    <span className="meta-label">Filename</span>
                    <span className="meta-val">{selectedFile.name}</span>
                  </div>
                  <div className="meta-item">
                    <span className="meta-label">Size</span>
                    <span className="meta-val">{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB</span>
                  </div>
                  <div className="meta-item">
                    <span className="meta-label">Format</span>
                    <span className="meta-val">{selectedFile.type || 'image/png'}</span>
                  </div>
                </div>
                <div className="preview-actions">
                  <label
                    htmlFor="replace-file-input"
                    className="btn btn-secondary"
                    tabIndex={0}
                    onKeyDown={(e) => handleKeyDownInputTrigger(e, 'replace-file-input')}
                  >
                    Replace Image
                  </label>
                  <input
                    id="replace-file-input"
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    className="sr-only"
                    onChange={handleInputChange}
                  />
                  <button
                    type="button"
                    className="btn btn-tertiary"
                    onClick={handleClear}
                  >
                    Cancel / Remove
                  </button>
                </div>

                <div className="confirm-section">
                  <button
                    type="button"
                    className="btn btn-primary btn-large"
                    onClick={() => handleUploadAndAnalyze()}
                    disabled={loading}
                    aria-disabled={loading}
                  >
                    Use This Image and Analyze
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="preferred-input-panel image-guidance-panel">
            <PreferredInput />
          </div>
        </div>
        <ImageGuidance selectedFile={selectedFile} includePreferredInput={false} />
        </>
      )}

      {analysisResult && (
        <div className="analysis-summary-card" style={{ marginTop: '1.5rem', padding: '1rem', background: '#161b22', border: '1px solid #30363d', borderRadius: '8px' }}>
          <h3>Latest Analysis Result</h3>
          <p>Profile Type: <strong>{analysisResult.profile_type}</strong></p>
          <p>
            Confidence:{' '}
            <strong style={{ color: analysisResult.confidence < 0.6 ? '#f85149' : '#3fb950' }}>
              {(analysisResult.confidence * 100).toFixed(0)}%
            </strong>
          </p>
          <p>
            Mode:{' '}
            <span className="badge" style={{ padding: '0.2rem 0.5rem', borderRadius: '4px', background: analysisResult.provenance === 'image_extracted' ? '#1f6feb' : '#8b949e', color: '#fff' }}>
              {analysisResult.provenance === 'image_extracted' ? '- AI Vision Extracted' : ' Demo / Mock Profile'}
            </span>
          </p>
        </div>
      )}
    </div>
  );
};

export default UploadPage;

