import React from 'react';
import {
  InputQualityStatus,
  classifyInputQuality,
  qualityStatusLabel,
  qualityStatusDescription,
  qualityStatusClass,
} from '../utils/qualityClassifier';

// ImageGuidance Component

interface ImageGuidanceProps {
  /** Current file selected by the user (optional used for quality classification) */
  selectedFile?: File | null;
  includePreferredInput?: boolean;
}

export const ImageGuidance: React.FC<ImageGuidanceProps> = ({
  selectedFile,
  includePreferredInput = true,
}) => {
  const qualityStatus: InputQualityStatus = selectedFile
    ? classifyInputQuality(selectedFile)
    : null;

  return (
    <aside className="image-guidance-panel" aria-label="Image capture guidance">
      {includePreferredInput && <PreferredInput />}

      {/* Image Checklist */}
      <section className="guidance-section" aria-labelledby="checklist-heading">
        <h2 className="guidance-title" id="checklist-heading">
          Image Guidance
        </h2>
        <div className="guidance-columns">
          <div className="guidance-card guidance-good">
            <h3>
              <span aria-hidden="true" style={{ marginRight: '6px' }}>[OK]</span>
              GOOD CAPTURE
            </h3>
            <ul>
              <li>One cross-section only, front-facing / orthographic</li>
              <li>Plain high-contrast background</li>
              <li>Solid or clearly shaded material region</li>
              <li>Full profile visible and uncropped</li>
              <li>No dimension lines, text, or arrows</li>
              <li>No center marks or overlapping annotations</li>
            </ul>
          </div>
          <div className="guidance-card guidance-bad">
            <h3>
              <span aria-hidden="true" style={{ marginRight: '6px' }}>-</span>
              BAD CAPTURE
            </h3>
            <ul>
              <li>Angled or perspective shot</li>
              <li>Cropped edge or cut-off boundary</li>
              <li>Heavy shadows obscuring contours</li>
              <li>Blurry or low-light photo</li>
              <li>Dimensioned engineering drawing with leaders</li>
              <li>Multiple unrelated profiles in one image</li>
            </ul>
          </div>
        </div>

        {/* Annotation warning */}
        <div className="guidance-annotation-warning" role="note">
          <span aria-hidden="true"></span>
          <span>
            <strong>Why annotations cause problems:</strong> Dimension lines, leaders, and
            center marks create false edges that OpenCV cannot distinguish from the real
            profile boundary. Dimensioned drawings may require manual cleanup of the traced
            profile and are treated as{' '}
            <em>experimental / manual review required</em>.
          </span>
        </div>
      </section>

      {/* Quality Status (shown after file selection) */}
      {qualityStatus && (
        <section className="guidance-section" aria-labelledby="quality-status-heading" aria-live="polite">
          <h2 className="guidance-title" id="quality-status-heading">
            Input Quality Status
          </h2>
          <div
            id="input-quality-badge"
            className={qualityStatusClass(qualityStatus)}
            role="status"
            aria-label={`Input quality: ${qualityStatusLabel(qualityStatus)}`}
          >
            <span className="quality-badge-label">{qualityStatusLabel(qualityStatus)}</span>
          </div>
          <p className="quality-badge-description">
            {qualityStatusDescription(qualityStatus)}
          </p>
          {qualityStatus === 'manual_cleanup_likely' && (
            <div className="guidance-annotation-warning guidance-annotation-warning--error" role="alert">
              <span aria-hidden="true"></span>
              <span>
                This image appears to contain dimension annotations. The trace may include
                false edges from leaders and extension lines. Review the SVG profile
                carefully before approving.
              </span>
            </div>
          )}
          {qualityStatus === 'unsupported' && (
            <div className="guidance-annotation-warning guidance-annotation-warning--error" role="alert">
              <span aria-hidden="true">-</span>
              <span>
                This file is unlikely to produce a usable profile. Upload a clean
                cross-section image without perspective distortion, cropping, or severe blur.
              </span>
            </div>
          )}
        </section>
      )}

    </aside>
  );
};

export const PreferredInput: React.FC = () => (
<section className="guidance-section" aria-labelledby="preferred-input-heading">
    <h2 className="guidance-title" id="preferred-input-heading">
      Preferred Input
    </h2>
    <div
      className="guidance-callout guidance-callout-primary"
      role="note"
      aria-label="Best results guidance"
    >
      <p>
    For best results, upload a <strong>clean cross-section image</strong> without
    dimensions or annotations. One confirmed measurement is enough to calibrate
    the profile scale after review.
      </p>
    </div>

    {/* Good example placeholder */}
    <div className="guidance-example-pair">
      <div className="guidance-example guidance-example-good">
    <div className="guidance-example-visual" aria-hidden="true">
      <svg viewBox="0 0 120 80" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <rect width="120" height="80" fill="#0a1628" />
        {/* Solid shaded cross-section shape */}
        <path
      d="M20 60 L20 20 Q20 15 25 15 L95 15 Q100 15 100 20 L100 60 Q100 65 95 65 L25 65 Q20 65 20 60 Z"
      fill="#2d4a7a"
      stroke="#00e676"
      strokeWidth="2"
        />
        {/* Interior hole */}
        <circle cx="60" cy="40" r="12" fill="#0a1628" stroke="#00e676" strokeWidth="1.5" />
      </svg>
    </div>
    <div className="guidance-example-label guidance-label-good">
      <span aria-hidden="true">[OK]</span> Clean shaded profile
    </div>
    <div className="guidance-example-caption">
      Recommended - solid fill, no annotations
    </div>
      </div>

      <div className="guidance-example guidance-example-bad">
    <div className="guidance-example-visual" aria-hidden="true">
      <svg viewBox="0 0 120 80" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <rect width="120" height="80" fill="#0a1628" />
        {/* Profile outline */}
        <rect
      x="20"
      y="15"
      width="80"
      height="50"
      fill="none"
      stroke="#8b949e"
      strokeWidth="1.5"
        />
        {/* Dimension lines */}
        <line x1="20" y1="8" x2="100" y2="8" stroke="#f59e0b" strokeWidth="0.8" strokeDasharray="3,2" />
        <line x1="20" y1="5" x2="20" y2="11" stroke="#f59e0b" strokeWidth="0.8" />
        <line x1="100" y1="5" x2="100" y2="11" stroke="#f59e0b" strokeWidth="0.8" />
        <text x="55" y="7" fontSize="5" fill="#f59e0b" textAnchor="middle">40 mm</text>
        {/* Extension lines */}
        <line x1="10" y1="15" x2="10" y2="65" stroke="#f59e0b" strokeWidth="0.8" strokeDasharray="2,2" />
        <line x1="7" y1="15" x2="13" y2="15" stroke="#f59e0b" strokeWidth="0.8" />
        <line x1="7" y1="65" x2="13" y2="65" stroke="#f59e0b" strokeWidth="0.8" />
        <text x="4" y="43" fontSize="4.5" fill="#f59e0b" textAnchor="middle" transform="rotate(-90 4 43)">20</text>
        {/* Center mark */}
        <line x1="57" y1="37" x2="63" y2="43" stroke="#f59e0b" strokeWidth="0.8" />
        <line x1="63" y1="37" x2="57" y2="43" stroke="#f59e0b" strokeWidth="0.8" />
      </svg>
    </div>
    <div className="guidance-example-label guidance-label-bad">
      <span aria-hidden="true">-</span> Dimensioned drawing
    </div>
    <div className="guidance-example-caption">
      Not recommended - annotations cause false edges
    </div>
      </div>
    </div>

    {/* Unsupported examples */}
    <div className="guidance-example-pair">
      <div className="guidance-example guidance-example-bad">
    <div className="guidance-example-visual" aria-hidden="true">
      <svg viewBox="0 0 120 80" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <rect width="120" height="80" fill="#0a1628" />
        {/* Angled/perspective shape */}
        <polygon
      points="30,70 25,20 90,15 95,65"
      fill="#2d4a7a"
      stroke="#ef4444"
      strokeWidth="1.5"
      opacity="0.7"
        />
        <text x="60" y="75" fontSize="6" fill="#ef4444" textAnchor="middle">perspective</text>
      </svg>
    </div>
    <div className="guidance-example-label guidance-label-bad">
      <span aria-hidden="true">-</span> Angled photo
    </div>
    <div className="guidance-example-caption">
      Unsupported - perspective distortion
    </div>
      </div>

      <div className="guidance-example guidance-example-bad">
    <div className="guidance-example-visual" aria-hidden="true">
      <svg viewBox="0 0 120 80" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <rect width="120" height="80" fill="#0a1628" />
        {/* Cropped profile cut off edges */}
        <clipPath id="crop-clip">
      <rect x="0" y="0" width="120" height="80" />
        </clipPath>
        <path
      d="M-10 60 L-10 20 Q-10 15 -5 15 L85 15 Q90 15 90 20 L90 60 Q90 65 85 65 L-5 65 Q-10 65 -10 60 Z"
      fill="#2d4a7a"
      stroke="#ef4444"
      strokeWidth="1.5"
      clipPath="url(#crop-clip)"
        />
        {/* Crop indicator */}
        <line x1="0" y1="0" x2="0" y2="80" stroke="#ef4444" strokeWidth="2" strokeDasharray="4,3" />
        <text x="60" y="75" fontSize="6" fill="#ef4444" textAnchor="middle">cropped</text>
      </svg>
    </div>
    <div className="guidance-example-label guidance-label-bad">
      <span aria-hidden="true">-</span> Cropped profile
    </div>
    <div className="guidance-example-caption">
      Unsupported - full contour must be visible
    </div>
      </div>
    </div>
  </section>
);

export default ImageGuidance;
