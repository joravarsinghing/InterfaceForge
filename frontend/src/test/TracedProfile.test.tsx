import { render, screen } from '@testing-library/react';
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

  it('displays example illustration notice when outer contour is null or insufficient', () => {
    render(<TracedProfileSvgViewer outerContour={null} isExample={true} />);
    expect(screen.getByText('EXAMPLE ILLUSTRATION - NOT YOUR MODEL')).toBeInTheDocument();
  });
});
