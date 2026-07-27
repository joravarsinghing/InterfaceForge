import React from 'react';

export const ImageGuidance: React.FC = () => {
  return (
    <aside className="image-guidance-panel" aria-label="Image capture guidance">
      <h2 className="guidance-title">Image Guidance</h2>
      <div className="guidance-columns">
        <div className="guidance-card guidance-good">
          <h3>
            <span aria-hidden="true" style={{ marginRight: '6px' }}>✓</span>
            GOOD CAPTURE
          </h3>
          <ul>
            <li>Camera directly facing interface</li>
            <li>Full outline visible and uncropped</li>
            <li>High contrast against background</li>
            <li>Minimal glare and reflections</li>
          </ul>
        </div>
        <div className="guidance-card guidance-bad">
          <h3>
            <span aria-hidden="true" style={{ marginRight: '6px' }}>✗</span>
            BAD CAPTURE
          </h3>
          <ul>
            <li>Angled or perspective shot</li>
            <li>Cropped edge or cut-off boundary</li>
            <li>Heavy shadows obscuring contours</li>
            <li>Blurry or low-light photo</li>
          </ul>
        </div>
      </div>
    </aside>
  );
};

export default ImageGuidance;
