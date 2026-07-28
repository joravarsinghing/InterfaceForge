/**
 * S10.5H — Input Requirements and Honest Upload Guidance
 * Frontend Vitest Test Suite
 *
 * Verifies:
 * - Preferred input guidance renders on both Interface A and B upload screens
 * - Quality classification messages are shown after file selection
 * - Known-measurement field is present and functional
 * - Unsupported input warning renders
 * - Annotation-heavy input warning renders
 * - No manufacturing-ready claim before scale confirmation
 * - Interface A and B guidance consistency
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import UploadPage from '../pages/UploadPage';
import { ImageGuidance } from '../components/ImageGuidance';
import {
  classifyInputQuality,
  qualityStatusLabel,
  qualityStatusDescription,
  qualityStatusClass,
} from '../utils/qualityClassifier';
import { Project } from '../types/schema';

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api');
  return {
    ...actual,
    uploadInterfaceImage: vi.fn(),
    analyzeInterfaceImage: vi.fn(),
    fetchProject: vi.fn(),
  };
});

if (typeof window !== 'undefined') {
  window.URL.createObjectURL = vi.fn(() => 'blob:mock-preview-url');
  window.URL.revokeObjectURL = vi.fn();
}

const mockProject: Project = {
  project_id: 'proj-s10h',
  project_token: 'tok-s10h',
  schema_version: '0.1',
  state: 'new',
  created_at: '2026-07-28T00:00:00Z',
  updated_at: '2026-07-28T00:00:00Z',
  current_schema_revision: 1,
  interface_a: {
    id: 'interface_a',
    profile_type: 'circle',
    profile_points: [],
    center: { x: 0, y: 0 },
    dimensions: [],
    validation: { is_closed: true, self_intersects: false, warnings: [] },
    approved: false,
  },
  interface_b: {
    id: 'interface_b',
    profile_type: 'circle',
    profile_points: [],
    center: { x: 0, y: 0 },
    dimensions: [],
    validation: { is_closed: true, self_intersects: false, warnings: [] },
    approved: false,
  },
  connection: {
    mode: 'coaxial',
    length_mm: 40,
    offset_x_mm: 0,
    offset_y_mm: 0,
    angle_deg: 0,
  },
  manufacturing: {
    process: 'fdm',
    material: 'PETG',
    wall_thickness_mm: 2.4,
    clearance_a_mm: 0.3,
    clearance_b_mm: 0.1,
  },
  model_revisions: [],
};

// ─── S10.5H-01: Preferred input guidance renders ───────────────────────────────

describe('S10.5H-01: Preferred input guidance renders on upload screens', () => {
  it('shows Preferred Input section on Interface A upload screen', () => {
    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );
    expect(screen.getByText('Preferred Input')).toBeInTheDocument();
  });

  it('shows the plain-language preferred-input callout text', () => {
    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );
    expect(
      screen.getByText(/clean cross-section image/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/one confirmed measurement is enough/i)
    ).toBeInTheDocument();
  });

  it('shows annotation warning explaining why annotations cause problems', () => {
    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );
    expect(screen.getByText(/Why annotations cause problems/i)).toBeInTheDocument();
    // 'false edges' appears in both the annotation warning and geometry rules; use getAllByText
    const falseEdgeMatches = screen.getAllByText(/false edges/i);
    expect(falseEdgeMatches.length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getByText(/Experimental \/ manual review required|experimental.*manual review/i)
    ).toBeInTheDocument();
  });

  it('shows preferred input guidance on Interface B upload screen (consistency)', () => {
    // Make project appear to have interface_a approved so B upload renders
    const projectWithAApproved: Project = {
      ...mockProject,
      interface_a: { ...mockProject.interface_a, approved: true },
    };

    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_b" project={projectWithAApproved} />
      </MemoryRouter>
    );

    expect(screen.getByText('Preferred Input')).toBeInTheDocument();
    expect(screen.getByText(/clean cross-section image/i)).toBeInTheDocument();
  });

  it('shows good and bad capture example labels', () => {
    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );
    expect(screen.getByText(/Clean shaded profile/i)).toBeInTheDocument();
    // 'Dimensioned drawing' appears in example label and checklist — use getAllByText
    const dimMatches = screen.getAllByText(/Dimensioned drawing/i);
    expect(dimMatches.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Angled photo/i)).toBeInTheDocument();
    expect(screen.getByText(/Cropped profile/i)).toBeInTheDocument();
  });
});

// ─── S10.5H-02: Quality classification messages ───────────────────────────────

describe('S10.5H-02: Quality classification logic', () => {
  it('classifies a clean section file as recommended', () => {
    const file = new File(['data'.repeat(200)], 'clean_section.png', { type: 'image/png' });
    expect(classifyInputQuality(file)).toBe('recommended');
  });

  it('classifies a file with "drawing" in name as manual_cleanup_likely', () => {
    const file = new File(['data'.repeat(200)], 'interface_drawing.png', { type: 'image/png' });
    expect(classifyInputQuality(file)).toBe('manual_cleanup_likely');
  });

  it('classifies an angled photo file as unsupported', () => {
    const file = new File(['data'.repeat(200)], 'angled_phone_photo.jpg', { type: 'image/jpeg' });
    expect(classifyInputQuality(file)).toBe('unsupported');
  });

  it('classifies a dimensioned drawing file as manual_cleanup_likely', () => {
    const file = new File(['data'.repeat(200)], 'assembly_dims.png', { type: 'image/png' });
    expect(classifyInputQuality(file)).toBe('manual_cleanup_likely');
  });

  it('classifies a generic image as usable_with_review', () => {
    const file = new File(['data'.repeat(500)], 'interface.png', { type: 'image/png' });
    expect(classifyInputQuality(file)).toBe('usable_with_review');
  });

  it('classifies a very small file as unsupported', () => {
    // Use an empty array so the file has 0 bytes — well below the 500-byte threshold
    const file = new File([], 'tiny.png', { type: 'image/png' });
    expect(classifyInputQuality(file)).toBe('unsupported');
  });

  it('qualityStatusLabel returns correct text for each status', () => {
    expect(qualityStatusLabel('recommended')).toContain('Recommended input');
    expect(qualityStatusLabel('usable_with_review')).toContain('Usable with review');
    expect(qualityStatusLabel('manual_cleanup_likely')).toContain('Manual cleanup likely');
    expect(qualityStatusLabel('unsupported')).toContain('Unsupported');
    expect(qualityStatusLabel(null)).toBe('');
  });

  it('qualityStatusDescription warns about annotations for manual_cleanup_likely', () => {
    expect(qualityStatusDescription('manual_cleanup_likely')).toMatch(
      /Dimensioned drawings introduce false edges/i
    );
  });

  it('qualityStatusClass returns correct CSS class for each status', () => {
    expect(qualityStatusClass('recommended')).toContain('quality-recommended');
    expect(qualityStatusClass('usable_with_review')).toContain('quality-usable');
    expect(qualityStatusClass('manual_cleanup_likely')).toContain('quality-cleanup');
    expect(qualityStatusClass('unsupported')).toContain('quality-unsupported');
  });
});

// ─── S10.5H-03: Quality badge renders in UI after file selection ───────────────

describe('S10.5H-03: Quality status badge renders after file selection', () => {
  it('shows quality badge after file with "section" in name is selected', () => {
    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );

    const cleanFile = new File(['data'.repeat(200)], 'clean_section.png', { type: 'image/png' });
    const fileInput = screen.getByLabelText('Choose Image File');
    fireEvent.change(fileInput, { target: { files: [cleanFile] } });

    // Quality section heading should be visible
    expect(screen.getByText('Input Quality Status')).toBeInTheDocument();
    // Recommended badge text — use getAllByText in case SVG contains overlap
    const recommendedMatches = screen.getAllByText(/Recommended input/i);
    expect(recommendedMatches.length).toBeGreaterThanOrEqual(1);
  });

  it('shows manual cleanup warning badge for annotation-heavy filename', () => {
    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );

    const dimFile = new File(['data'.repeat(200)], 'interface_dims_drawing.png', {
      type: 'image/png',
    });
    const fileInput = screen.getByLabelText('Choose Image File');
    fireEvent.change(fileInput, { target: { files: [dimFile] } });

    const allMatches = screen.getAllByText(/Manual cleanup likely/i);
    expect(allMatches.length).toBeGreaterThanOrEqual(1);
  });

  it('shows unsupported warning badge for angled photo', () => {
    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );

    const angledFile = new File(['data'.repeat(200)], 'angled_photo_scan.jpg', {
      type: 'image/jpeg',
    });
    const fileInput = screen.getByLabelText('Choose Image File');
    fireEvent.change(fileInput, { target: { files: [angledFile] } });

    const allUnsupported = screen.getAllByText(/Unsupported/i);
    expect(allUnsupported.length).toBeGreaterThanOrEqual(1);
  });
});

// ─── S10.5H-04: Known-measurement field ───────────────────────────────────────

describe('S10.5H-04: Known measurement field', () => {
  it('renders the Known Measurement optional field', () => {
    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );

    expect(screen.getByText(/Known Measurement/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Known measurement value in millimetres/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Known dimension type/i)).toBeInTheDocument();
  });

  it('shows dimension type options in select', () => {
    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );

    const select = screen.getByLabelText(/Known dimension type/i) as HTMLSelectElement;
    const options = Array.from(select.options).map((o) => o.value);
    expect(options).toContain('overall_width');
    expect(options).toContain('overall_height');
    expect(options).toContain('hole_diameter');
    expect(options).toContain('reference_distance');
  });

  it('shows scale confirmation note when a value is entered', () => {
    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );

    // Select a file so the preview card (with confirm section) shows
    const file = new File(['data'.repeat(200)], 'profile.png', { type: 'image/png' });
    fireEvent.change(screen.getByLabelText('Choose Image File'), { target: { files: [file] } });

    // Enter a known measurement in the guidance panel
    const measureInput = screen.getByLabelText(/Known measurement value in millimetres/i);
    fireEvent.change(measureInput, { target: { value: '40' } });

    // Confirm section should show the captured measurement via data-testid
    const summary = screen.getByTestId('known-measurement-summary');
    expect(summary).toBeInTheDocument();
    expect(summary.textContent).toMatch(/40 mm/i);
    expect(summary.textContent).toMatch(/scale will be confirmed after the trace/i);
  });

  it('scale confirmation note says "scale will be confirmed" — not manufacturing-ready', () => {
    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );

    const file = new File(['data'.repeat(200)], 'profile.png', { type: 'image/png' });
    fireEvent.change(screen.getByLabelText('Choose Image File'), { target: { files: [file] } });

    const measureInput = screen.getByLabelText(/Known measurement value in millimetres/i);
    fireEvent.change(measureInput, { target: { value: '25' } });

    const summary = screen.getByTestId('known-measurement-summary');
    // Must NOT say "manufacturing-ready" before scale is confirmed
    expect(summary.textContent).not.toMatch(/manufacturing.?ready/i);
    // Must explicitly mention confirmation is pending
    expect(summary.textContent).toMatch(/confirmed after the trace/i);
  });
});

// ─── S10.5H-05: No manufacturing-ready claim before scale confirmation ─────────

describe('S10.5H-05: No premature manufacturing-ready claims', () => {
  it('upload page does not claim manufacturing-ready status anywhere before analysis', () => {
    const { container } = render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );

    expect(container.textContent).not.toMatch(/manufacturing.?ready/i);
    expect(container.textContent).not.toMatch(/production.?ready/i);
  });

  it('ImageGuidance does not claim arbitrary drawings are always supported', () => {
    const { container } = render(
      <MemoryRouter>
        <ImageGuidance />
      </MemoryRouter>
    );

    // Must not claim all drawings work
    expect(container.textContent).not.toMatch(/always supported/i);
    expect(container.textContent).not.toMatch(/any technical drawing/i);
    // Must communicate limitation
    expect(container.textContent).toMatch(/annotation|false edge|manual|cleanup/i);
  });
});

// ─── S10.5H-06: Interface A and B consistency ─────────────────────────────────

describe('S10.5H-06: Interface A and B guidance consistency', () => {
  it('both screens show the same guidance heading structure', () => {
    const projectWithAApproved: Project = {
      ...mockProject,
      interface_a: { ...mockProject.interface_a, approved: true },
    };

    const { unmount } = render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );

    // Preferred Input + Image Guidance + Known Measurement should all be present
    expect(screen.getByText('Preferred Input')).toBeInTheDocument();
    expect(screen.getByText('Image Guidance')).toBeInTheDocument();
    expect(screen.getAllByText(/Known Measurement/i).length).toBeGreaterThanOrEqual(1);

    unmount();

    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_b" project={projectWithAApproved} />
      </MemoryRouter>
    );

    expect(screen.getByText('Preferred Input')).toBeInTheDocument();
    expect(screen.getByText('Image Guidance')).toBeInTheDocument();
    expect(screen.getAllByText(/Known Measurement/i).length).toBeGreaterThanOrEqual(1);
  });
});

// ─── S10.5H-07: ImageGuidance standalone rendering ────────────────────────────

describe('S10.5H-07: ImageGuidance standalone rendering', () => {
  it('renders without selectedFile prop (no quality badge shown)', () => {
    render(<ImageGuidance />);

    expect(screen.getByText('Preferred Input')).toBeInTheDocument();
    expect(screen.getByText('Image Guidance')).toBeInTheDocument();
    // No quality badge when no file selected
    expect(screen.queryByText('Input Quality Status')).not.toBeInTheDocument();
  });

  it('renders quality badge when selectedFile is recommended', () => {
    const file = new File(['data'.repeat(500)], 'clean_cross_section.png', {
      type: 'image/png',
    });

    render(<ImageGuidance selectedFile={file} />);

    expect(screen.getByText('Input Quality Status')).toBeInTheDocument();
    // 'Recommended input' appears in the quality badge
    const allMatches = screen.getAllByText(/Recommended input/i);
    expect(allMatches.length).toBeGreaterThanOrEqual(1);
  });

  it('calls onKnownMeasurement when value changes', () => {
    const onMeasurement = vi.fn();
    render(<ImageGuidance onKnownMeasurement={onMeasurement} />);

    const input = screen.getByLabelText(/Known measurement value in millimetres/i);
    fireEvent.change(input, { target: { value: '40' } });

    expect(onMeasurement).toHaveBeenCalledWith('40', 'overall_width');
  });

  it('calls onKnownMeasurement with updated dimension when select changes', () => {
    const onMeasurement = vi.fn();
    render(<ImageGuidance onKnownMeasurement={onMeasurement} />);

    const select = screen.getByLabelText(/Known dimension type/i);
    fireEvent.change(select, { target: { value: 'hole_diameter' } });

    expect(onMeasurement).toHaveBeenCalledWith('', 'hole_diameter');
  });
});
