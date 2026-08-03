import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { SampleGallery } from '../components/SampleGallery';

describe('SampleGallery Component', () => {
  it('renders section title "Try these samples", shuffle button, and exactly 3 unique thumbnails', () => {
    render(<SampleGallery onSelectSample={vi.fn()} />);

    expect(screen.getByText('Try these samples')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /shuffle/i })).toBeInTheDocument();

    const thumbnails = screen.getAllByRole('button', { name: /select sample/i });
    expect(thumbnails).toHaveLength(3);
  });

  it('keeps manual-QA profiles in the sample pool when they are present', async () => {
    const { SAMPLE_MANIFEST } = await import('../data/sampleManifest');

    const manualQaProfiles = SAMPLE_MANIFEST.filter((sample) => sample.id.startsWith('manual-qa-'));
    expect(manualQaProfiles.length).toBeGreaterThan(0);
    expect(new Set(manualQaProfiles.map((sample) => sample.src)).size).toBe(manualQaProfiles.length);
  });

  it('randomizes three unique thumbnails when Shuffle is clicked', async () => {
    render(<SampleGallery onSelectSample={vi.fn()} />);

    const firstSetImgs = screen.getAllByRole('img').map((img) => img.getAttribute('src'));
    expect(firstSetImgs).toHaveLength(3);

    const shuffleBtn = screen.getByRole('button', { name: /shuffle/i });
    fireEvent.click(shuffleBtn);

    const secondSetImgs = screen.getAllByRole('img').map((img) => img.getAttribute('src'));
    expect(secondSetImgs).toHaveLength(3);

    // The shuffle guarantees a different set while randomizing the order.
    expect(new Set(secondSetImgs).size).toBe(3);
    expect(secondSetImgs).not.toEqual(firstSetImgs);

    const { SAMPLE_MANIFEST } = await import('../data/sampleManifest');
    expect(new Set(SAMPLE_MANIFEST.map((sample) => sample.src)).size).toBe(SAMPLE_MANIFEST.length);
  });

  it('opens choice modal when a sample thumbnail is clicked', () => {
    render(<SampleGallery onSelectSample={vi.fn()} />);

    const thumbnails = screen.getAllByRole('button', { name: /select sample/i });
    fireEvent.click(thumbnails[0]);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Use Sample Image')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Use for Interface A' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Use for Interface B' })).toBeInTheDocument();
  });

  it('invokes onSelectSample with target interface when Interface A or B is chosen', () => {
    const onSelectSample = vi.fn();
    render(<SampleGallery onSelectSample={onSelectSample} />);

    const thumbnails = screen.getAllByRole('button', { name: /select sample/i });
    fireEvent.click(thumbnails[0]);

    const useForA = screen.getByRole('button', { name: 'Use for Interface A' });
    fireEvent.click(useForA);

    expect(onSelectSample).toHaveBeenCalledTimes(1);
    expect(onSelectSample).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'sample-1' }),
      'interface_a'
    );
  });

  it('renders "Use for Interface B" as primary and "Replace Interface A" as secondary when currentInterface="interface_b"', () => {
    const onSelectSample = vi.fn();
    render(<SampleGallery onSelectSample={onSelectSample} currentInterface="interface_b" />);

    const thumbnails = screen.getAllByRole('button', { name: /select sample/i });
    fireEvent.click(thumbnails[0]);

    const primaryBtn = screen.getByRole('button', { name: 'Use for Interface B' });
    const secondaryBtn = screen.getByRole('button', { name: 'Replace Interface A' });

    expect(primaryBtn).toHaveClass('btn-primary');
    expect(secondaryBtn).toHaveClass('btn-secondary');

    fireEvent.click(primaryBtn);
    expect(onSelectSample).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'sample-1' }),
      'interface_b'
    );
  });
});
