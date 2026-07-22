import React, { useState, ChangeEvent, DragEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { ImageGuidance } from '../components/ImageGuidance';
import { uploadInterfaceImage, analyzeInterfaceImage } from '../services/api';
import { AnalysisResult, Project } from '../types/schema';

interface UploadPageProps {
  interfaceId: 'interface_a' | 'interface_b';
  project: Project | null;
  onAnalysisComplete?: (result: AnalysisResult) => void;
}

export const UploadPage: React.FC<UploadPageProps> = ({
  interfaceId,
  project,
  onAnalysisComplete,
}) => {
  const navigate = useNavigate();

  const isInterfaceB = interfaceId === 'interface_b';
  const interfaceName = isInterfaceB ? 'Interface B' : 'Interface A';
  const isPrerequisiteMet = !isInterfaceB || (project?.interface_a.approved ?? false);

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

  const handleUploadAndAnalyze = async () => {
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
        project.project_token
      );

      // 2. Run analysis
      setLoadingText('Analyzing interface contours...');
      const result = await analyzeInterfaceImage(
        project.project_id,
        interfaceId,
        project.project_token
      );

      setAnalysisResult(result);
      setLoading(false);
      if (onAnalysisComplete) {
        onAnalysisComplete(result);
      }
      navigate(isInterfaceB ? '/step2/analysis' : '/step1/analysis');
    } catch (err: unknown) {
      setLoading(false);
      const msg = err instanceof Error ? err.message : 'An unexpected error occurred during upload.';
      setError(msg);
    }
  };

  if (!isPrerequisiteMet) {
    return (
      <div className="upload-page container">
        <h1 className="page-title">{interfaceName} — Prerequisite Required</h1>
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
      <h1 className="page-title">{interfaceName} — Upload Image or Sketch</h1>
      <p className="page-subtitle">
        Capture the physical mating face that connects to the target product.
      </p>

      {error && (
        <div className="error-banner" role="alert">
          <h3>Upload / Analysis Error</h3>
          <p>{error}</p>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {loading ? (
        <div className="loading-state" role="status" aria-live="polite">
          <div className="spinner" />
          <p>{loadingText}</p>
        </div>
      ) : (
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
                  <p className="dropzone-text">Drag & drop your interface image here</p>
                  <p className="dropzone-or">or</p>
                  <label htmlFor="file-input" className="btn btn-primary">
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
                <div className="file-meta">
                  <p><strong>Filename:</strong> {selectedFile.name}</p>
                  <p><strong>Size:</strong> {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB</p>
                  <p><strong>Type:</strong> {selectedFile.type || 'image/png'}</p>
                </div>
                <div className="preview-actions">
                  <label htmlFor="replace-file-input" className="btn btn-secondary">
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
                    onClick={handleUploadAndAnalyze}
                  >
                    Use This Image and Analyze
                  </button>
                </div>
              </div>
            )}
          </div>

          <ImageGuidance />
        </div>
      )}

      {analysisResult && (
        <div className="analysis-summary-card">
          <h3>Latest Analysis Result</h3>
          <p>Profile Type: <strong>{analysisResult.profile_type}</strong></p>
          <p>Confidence: <strong>{(analysisResult.confidence * 100).toFixed(0)}%</strong></p>
        </div>
      )}
    </div>
  );
};

export default UploadPage;
