import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { TracedProfileSvgViewer } from '../components/TracedProfileSvgViewer';
import type { TracedContour } from '../types/schema';

describe('TracedProfileSvgViewer Component (Stage S10.4)', () => {
  const mockOuter: TracedContour = {
    id: 'outer_contour',
    points: [
      { x: -40, y: -40 },
      { x: 40, y: -40 },
      { x: 40, y: 40 },
      { x: -40, y: 40 },
    ],
    is_closed: true,
    classification: 'outer_contour',
    provenance: 'analysis',
    confidence: 0.9,
    point_count: 4,
  };

  const mockHole: TracedContour = {
    id: 'region_1',
    points: [
      { x: -10, y: -10 },
      { x: 10, y: -10 },
      { x: 10, y: 10 },
      { x: -10, y: 10 },
    ],
    is_closed: true,
    classification: 'hole',
    decision: 'include',
    provenance: 'analysis',
    confidence: 0.85,
    point_count: 4,
  };

  it('renders SVG with outer contour polygon and legend', () => {
    render(<TracedProfileSvgViewer outerContour={mockOuter} width={300} height={280} />);
    const svgEl = screen.getByRole('img', { name: /Traced closed profile SVG/i });
    expect(svgEl).toBeInTheDocument();
    expect(screen.getByText('Outer boundary')).toBeInTheDocument();
  });

  it('renders SVG with inner hole and included opening legend', () => {
    render(
      <TracedProfileSvgViewer
        outerContour={mockOuter}
        holeContours={[mockHole]}
        width={300}
        height={280}
      />
    );
    expect(screen.getByText(/Included opening/i)).toBeInTheDocument();
  });


  it('fills the available card width responsively while preserving aspect ratio', () => {
    render(<TracedProfileSvgViewer outerContour={mockOuter} />);
    const wrapper = screen.getByTestId('traced-profile-viewer');
    const svgEl = screen.getByRole('img', { name: /Traced closed profile SVG/i });
    expect(wrapper).toHaveStyle({ width: '100%', minHeight: '360px' });
    expect(wrapper.style.aspectRatio).not.toEqual('');
    expect(svgEl).toHaveAttribute('preserveAspectRatio', 'xMidYMid meet');
  });

  it('renders simplified contour nodes as active calibration hit targets only in calibration mode', () => {
    const { rerender } = render(<TracedProfileSvgViewer outerContour={mockOuter} />);
    expect(screen.getAllByTestId('trace-node')).toHaveLength(mockOuter.points.length);
    expect(screen.getAllByTestId('trace-node-hit-target')[0]).toHaveAttribute('pointer-events', 'none');

    rerender(<TracedProfileSvgViewer outerContour={mockOuter} calibrationMode />);
    expect(screen.getAllByTestId('trace-node-hit-target')[0]).toHaveAttribute('pointer-events', 'all');
  });

  it('selects a visible node directly from the enlarged hit target', () => {
    const picks: Array<{ x: number; y: number }> = [];
    render(<TracedProfileSvgViewer outerContour={mockOuter} calibrationMode onCalibrationPick={(point) => picks.push(point)} />);
    fireEvent.click(screen.getAllByTestId('trace-node-hit-target')[0]);
    expect(picks).toEqual([{ x: -40, y: -40 }]);
  });

  it('shows A immediately and B with a dimension line after the second selection', () => {
    const { rerender } = render(
      <TracedProfileSvgViewer outerContour={mockOuter} calibrationMode calibrationPointA={{ x: -40, y: -40 }} />
    );
    expect(screen.getByText('A')).toBeInTheDocument();

    rerender(
      <TracedProfileSvgViewer
        outerContour={mockOuter}
        calibrationMode
        calibrationPointA={{ x: -40, y: -40 }}
        calibrationPointB={{ x: 40, y: -40 }}
      />
    );
    expect(screen.getByText('B')).toBeInTheDocument();
    expect(document.querySelector('line')).toBeInTheDocument();
  });
  it('displays example illustration notice when outer contour is null or insufficient', () => {
    render(<TracedProfileSvgViewer outerContour={null} isExample={true} />);
    expect(screen.getByText('EXAMPLE ILLUSTRATION - NOT YOUR MODEL')).toBeInTheDocument();
  });
});
