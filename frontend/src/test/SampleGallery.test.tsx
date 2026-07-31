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

  it('rotates thumbnails deterministically when Shuffle is clicked', () => {
    render(<SampleGallery onSelectSample={vi.fn()} />);

    const firstSetImgs = screen.getAllByRole('img').map((img) => img.getAttribute('src'));
    expect(firstSetImgs).toHaveLength(3);

    const shuffleBtn = screen.getByRole('button', { name: /shuffle/i });
    fireEvent.click(shuffleBtn);

    const secondSetImgs = screen.getAllByRole('img').map((img) => img.getAttribute('src'));
    expect(secondSetImgs).toHaveLength(3);

    // Verify sets are non-identical (changed)
    expect(secondSetImgs).not.toEqual(firstSetImgs);
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
