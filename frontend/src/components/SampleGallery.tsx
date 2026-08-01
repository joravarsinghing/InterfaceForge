import React, { useState } from 'react';
import { SAMPLE_MANIFEST, SampleAsset } from '../data/sampleManifest';

const SAMPLE_DISPLAY_COUNT = 3;

function getRandomSamples(pool: SampleAsset[], previous: SampleAsset[] = []): SampleAsset[] {
  if (pool.length <= SAMPLE_DISPLAY_COUNT) return [...pool];

  const shuffled = [...pool];
  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    const randomIndex = Math.floor(Math.random() * (index + 1));
    [shuffled[index], shuffled[randomIndex]] = [shuffled[randomIndex], shuffled[index]];
  }

  const next = shuffled.slice(0, SAMPLE_DISPLAY_COUNT);
  const unchanged = previous.length === next.length && next.every((sample) => previous.some((item) => item.id === sample.id));
  if (unchanged) {
    [next[0], next[1]] = [next[1], next[0]];
  }
  return next;
}

export interface SampleGalleryProps {
  onSelectSample: (sample: SampleAsset, targetInterface: 'interface_a' | 'interface_b') => void;
  currentInterface?: 'interface_a' | 'interface_b';
  disabled?: boolean;
}

export const SampleGallery: React.FC<SampleGalleryProps> = ({
  onSelectSample,
  currentInterface = 'interface_a',
  disabled = false,
}) => {
  const [visibleSamples, setVisibleSamples] = useState<SampleAsset[]>(() =>
    SAMPLE_MANIFEST.slice(0, SAMPLE_DISPLAY_COUNT)
  );
  const [selectedSampleForModal, setSelectedSampleForModal] = useState<SampleAsset | null>(null);

  const handleShuffle = () => {
    if (disabled) return;
    setVisibleSamples((previous) => getRandomSamples(SAMPLE_MANIFEST, previous));
  };

  const handleThumbnailClick = (sample: SampleAsset) => {
    if (disabled) return;
    setSelectedSampleForModal(sample);
  };

  const handleChooseInterface = (targetInterface: 'interface_a' | 'interface_b') => {
    if (!selectedSampleForModal || disabled) return;
    const sample = selectedSampleForModal;
    setSelectedSampleForModal(null);
    onSelectSample(sample, targetInterface);
  };

  const handleCloseModal = () => {
    setSelectedSampleForModal(null);
  };

  const isInterfaceB = currentInterface === 'interface_b';

  return (
    <div className="sample-gallery-section" style={{ marginBottom: '2rem' }}>
      <div className="sample-gallery-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h2 className="sample-gallery-title" style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0, color: 'var(--text-color, #e6edf3)' }}>
          Try these samples
        </h2>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={handleShuffle}
          disabled={disabled}
          aria-label="Shuffle samples"
        >
          Shuffle
        </button>
      </div>

      <div
        className="sample-gallery-grid"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '1rem',
        }}
      >
        {visibleSamples.map((sample, idx) => (
          <button
            key={sample.id}
            type="button"
            className="sample-thumbnail-btn"
            onClick={() => handleThumbnailClick(sample)}
            disabled={disabled}
            aria-label={`Select sample ${idx + 1}`}
            style={{
              padding: 0,
              border: '1px solid var(--border-color, #30363d)',
              borderRadius: '8px',
              overflow: 'hidden',
              background: '#0d1117',
              cursor: disabled ? 'not-allowed' : 'pointer',
              aspectRatio: '1 / 1',
              display: 'block',
              width: '100%',
              opacity: disabled ? 0.6 : 1,
              transition: 'border-color 0.2s, transform 0.2s',
            }}
          >
            <img
              src={sample.src}
              alt=""
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                display: 'block',
              }}
            />
          </button>
        ))}
      </div>

      {selectedSampleForModal && (
        <div
          className="sample-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="sample-modal-title"
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
        >
          <div
            className="sample-modal-content"
            style={{
              background: 'var(--bg-secondary, #161b22)',
              border: '1px solid var(--border-color, #30363d)',
              borderRadius: '12px',
              padding: '1.5rem',
              maxWidth: '400px',
              width: '100%',
              boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
            }}
          >
            <h3 id="sample-modal-title" style={{ marginTop: 0, marginBottom: '1rem', fontSize: '1.1rem', color: '#e6edf3' }}>
              Use Sample Image
            </h3>
            <div
              style={{
                width: '120px',
                height: '120px',
                margin: '0 auto 1.25rem auto',
                borderRadius: '8px',
                overflow: 'hidden',
                border: '1px solid #30363d',
              }}
            >
              <img
                src={selectedSampleForModal.src}
                alt=""
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            </div>
            <p style={{ fontSize: '0.9rem', color: '#8b949e', marginBottom: '1.25rem', textAlign: 'center' }}>
              Select which interface to set with this sample image:
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {isInterfaceB ? (
                <>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => handleChooseInterface('interface_b')}
                    disabled={disabled}
                  >
                    Use for Interface B
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => handleChooseInterface('interface_a')}
                    disabled={disabled}
                  >
                    Replace Interface A
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => handleChooseInterface('interface_a')}
                    disabled={disabled}
                  >
                    Use for Interface A
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => handleChooseInterface('interface_b')}
                    disabled={disabled}
                  >
                    Use for Interface B
                  </button>
                </>
              )}
              <button
                type="button"
                className="btn btn-tertiary"
                onClick={handleCloseModal}
                disabled={disabled}
                style={{ marginTop: '0.25rem' }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SampleGallery;
