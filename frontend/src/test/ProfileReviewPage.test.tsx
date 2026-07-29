import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { ProfileReviewPage } from '../pages/ProfileReviewPage';
import { Project } from '../types/schema';
import * as api from '../services/api';

vi.mock('../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../services/api');
  return {
    ...actual,
    patchInterface: vi.fn(),
    approveInterface: vi.fn(),
    snapScalePoint: vi.fn(),
    calibrateInterfaceScale: vi.fn(),
    resetInterfaceScaleCalibration: vi.fn(),
  };

});

const mockProject: Project = {
  project_id: 'proj_123',
  project_token: 'tok_abc',
  schema_version: '0.1',
  state: 'interface_a_review_required',
  created_at: '2026-07-22T00:00:00Z',
  updated_at: '2026-07-22T00:00:00Z',
  current_schema_revision: 1,
  interface_a: {
    id: 'interface_a',
    source_image_ref: 'artifacts/uploads/test.png',
    profile_type: 'circle',
    profile_points: [],
    center: { x: 0, y: 0 },
    dimensions: [
      {
        id: 'outer_diameter',
        label: 'Outer Diameter',
        value: 50.0,
        unit: 'mm',
        provenance: 'image_extracted',
        confidence: 0.95,
        critical: true,
      },
      {
        id: 'wall_thickness',
        label: 'Wall Thickness',
        value: 5.0,
        unit: 'mm',
        provenance: 'image_extracted',
        confidence: 0.9,
        critical: false,
      },
    ],
    validation: {
      is_closed: true,
      self_intersects: false,
      warnings: [],
    },
    approved: false,
  },
  interface_b: {
    id: 'interface_b',
    profile_type: 'rectangle',
    profile_points: [],
    center: { x: 0, y: 0 },
    dimensions: [],
    validation: {
      is_closed: true,
      self_intersects: false,
      warnings: [],
    },
    approved: false,
  },
  connection: {
    mode: 'coaxial',
    length_mm: 0,
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

describe('ProfileReviewPage Component', () => {
  it('renders side-by-side view with source image and clean SVG profile viewer', () => {
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={mockProject} />
      </BrowserRouter>
    );

    expect(screen.getByRole('heading', { name: /Interface A.*Profile Review & Approval/i })).toBeInTheDocument();
    expect(screen.getByText(/Source Image/i)).toBeInTheDocument();
    expect(screen.getByText(/Clean SVG Profile/i)).toBeInTheDocument();
    expect(screen.getByTitle(/circle Profile Preview/i)).toBeInTheDocument();
  });

  it('shows detected profile type only in collapsed technical details', () => {
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={mockProject} />
      </BrowserRouter>
    );

    expect(screen.queryByLabelText(/Detected Profile Type/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: /Detected Profile Type/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Technical details/i)).toBeInTheDocument();
    expect(screen.getByText(/Detected profile type/i)).toBeInTheDocument();
    expect(screen.getByText('Circle')).toBeInTheDocument();
  });
  it('displays provenance labels with explicit text and icons (not color alone)', () => {
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={mockProject} />
      </BrowserRouter>
    );

    expect(screen.getByText(/Legend:/i)).toBeInTheDocument();
    expect(screen.getAllByText(/User Entered/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Image Extracted/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/System Inferred/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Unresolved/i).length).toBeGreaterThan(0);
  });

  it('displays validation summary error when fewer than two known dimensions exist', async () => {
    const singleDimProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        dimensions: [
          {
            id: 'outer_diameter',
            label: 'Outer Diameter',
            value: 50.0,
            unit: 'mm',
            provenance: 'image_extracted',
            confidence: 0.95,
            critical: true,
          },
        ],
      },
    };

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={singleDimProject} />
      </BrowserRouter>
    );

    expect(screen.getByText(/Validation Error/i)).toBeInTheDocument();
    expect(screen.getByText(/At least two known dimensions are required/i)).toBeInTheDocument();

    const approveButton = screen.getByRole('button', { name: /Approve Interface A/i });
    expect(approveButton).toBeDisabled();
  });

  it('calls patchInterface and approveInterface APIs when user approves', async () => {
    const patchMock = vi.mocked(api.patchInterface).mockResolvedValue(mockProject);
    const approveMock = vi.mocked(api.approveInterface).mockResolvedValue({
      ...mockProject,
      interface_a: { ...mockProject.interface_a, approved: true },
      state: 'interface_a_approved',
    });

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={mockProject} />
      </BrowserRouter>
    );

    const approveButton = screen.getByRole('button', { name: /Approve Interface A/i });
    expect(approveButton).not.toBeDisabled();

    fireEvent.click(approveButton);

    await waitFor(() => {
      expect(patchMock).toHaveBeenCalledWith(
        'proj_123',
        'interface_a',
        expect.objectContaining({ profile_type: 'circle' }),
        'tok_abc'
      );
      expect(approveMock).toHaveBeenCalledWith('proj_123', 'interface_a', 'tok_abc');
    });
  });

  it('pre-populates uploaded measurement scale and requires explicit confirmation for primitive profiles', () => {
    const measuredProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        dimensions: [
          ...mockProject.interface_a.dimensions,
          {
            id: 'overall_width',
            label: 'Overall Width',
            value: 41.5,
            unit: 'mm',
            provenance: 'user_entered',
            confidence: 1.0,
            critical: true,
            feature_ref: 'outer_contour',
          },
        ],
        scale_calibration: {
          source: 'user_calibration',
          reference_dimension: 'overall_width',
          pixel_distance: 96,
          real_distance_mm: 41.5,
          confidence: 1.0,
          confirmed: false,
        },
      },
    };

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={measuredProject} />
      </BrowserRouter>
    );

    expect(screen.getByText(/Millimetre Scale Calibration/i)).toBeInTheDocument();
    expect(screen.getByText(/Scale unconfirmed/i)).toBeInTheDocument();
    expect(screen.getAllByText(/41.5 mm/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /Approve Interface A/i })).toBeDisabled();
  });

  it('hydrates confirmed scale after refresh and keeps approval available', () => {
    const hydratedProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        scale_calibration: {
          source: 'user_calibration',
          reference_dimension: 'overall_width',
          pixel_distance: 96,
          real_distance_mm: 41.5,
          confidence: 1.0,
          confirmed: true,
        },
      },
    };

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={hydratedProject} />
      </BrowserRouter>
    );

    expect(screen.getAllByText(/Scale confirmed/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /Approve Interface A/i })).not.toBeDisabled();
  });

  it('shows backend approval rejection without presenting approved state', async () => {
    vi.mocked(api.patchInterface).mockResolvedValue(mockProject);
    vi.mocked(api.approveInterface).mockRejectedValue(
      new Error('[IF-APPROVAL-400] Scale calibration must be confirmed')
    );

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={mockProject} />
      </BrowserRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /Approve Interface A/i }));

    await waitFor(() => {
      expect(screen.getByText(/Scale calibration must be confirmed/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Status: Approved/i)).not.toBeInTheDocument();
  });

  it('renders approved state and allows re-editing', () => {
    const approvedProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        approved: true,
        approved_at: '2026-07-22T01:00:00Z',
      },
      state: 'interface_a_approved',
    };

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={approvedProject} />
      </BrowserRouter>
    );

    expect(screen.getByText(/Status: Approved/i)).toBeInTheDocument();
    const editBtn = screen.getByRole('button', { name: /Edit Profile Again/i });
    expect(editBtn).toBeInTheDocument();
    fireEvent.click(editBtn);

    expect(screen.getByRole('button', { name: /Update Profile/i })).toBeInTheDocument();
  });

  it('renders traced closed profile with scale confirmation and region controls', () => {
    const tracedProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        profile_type: 'traced_closed',
        traced_outer_contour: {
          id: 'outer_contour',
          points: [
            { x: -20, y: -20 },
            { x: 20, y: -20 },
            { x: 20, y: 20 },
            { x: -20, y: 20 },
          ],
          is_closed: true,
          classification: 'outer_contour',
          provenance: 'analysis',
          confidence: 0.9,
          point_count: 4,
        },
        traced_hole_contours: [
          {
            id: 'region_1',
            points: [
              { x: -5, y: -5 },
              { x: 5, y: -5 },
              { x: 5, y: 5 },
              { x: -5, y: 5 },
            ],
            is_closed: true,
            classification: 'hole',
            decision: 'include',
            provenance: 'analysis',
            confidence: 0.85,
            point_count: 4,
          },
        ],
        scale_calibration: {
          source: 'drawing_dimension',
          reference_dimension: 'overall_width',
          pixel_distance: 400,
          real_distance_mm: 40,
          confidence: 0.95,
          confirmed: false,
        },
      },
    };

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={tracedProject} />
      </BrowserRouter>
    );

    expect(screen.getByText(/Millimetre Scale Calibration/i)).toBeInTheDocument();
    expect(screen.getByText(/Scale unconfirmed/i)).toBeInTheDocument();
    expect(screen.getByText(/Internal Cavities & Openings/i)).toBeInTheDocument();
    expect(screen.getByText(/region_1/i)).toBeInTheDocument();

    // Scale unconfirmed blocks approval
    expect(screen.getByRole('button', { name: /Approve Interface A/i })).toBeDisabled();

    // Confirming scale
    const confirmScaleBtn = screen.getByRole('button', { name: /Confirm Scale/i });
    expect(confirmScaleBtn).toBeInTheDocument();
  });

  it('renders primitive fallback badge when primitive fallback is activated', () => {
    const fallbackProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        profile_type: 'traced_closed',
        primitive_fallback_active: true,
        primitive_fallback_label: 'Simplified envelope Ã¢â‚¬â€ not the exact cross-section',
      },
    };

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={fallbackProject} />
      </BrowserRouter>
    );

    expect(screen.getAllByText(/Simplified envelope.*not the exact cross-section/i).length).toBeGreaterThan(0);
  });

  it('uses original upload for Original and processed artifact SVG for Overlay', () => {
    const tracedProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        profile_type: 'traced_closed',
        analysis_image_ref: 'artifacts/cleaned_profile.png',
        analysis_image_width: 512,
        analysis_image_height: 256,
        trace_svg_ref: 'artifacts/trace_profile.svg',
        overlay_svg_ref: 'artifacts/overlay_profile.svg',
        traced_outer_contour: {
          id: 'outer_contour',
          points: [
            { x: -20, y: -20 },
            { x: 20, y: -20 },
            { x: 20, y: 20 },
            { x: -20, y: 20 },
          ],
          is_closed: true,
          classification: 'outer_contour',
          provenance: 'analysis',
          confidence: 0.9,
          point_count: 4,
        },
        traced_hole_contours: [],
        scale_calibration: {
          source: 'drawing_dimension',
          reference_dimension: 'overall_width',
          pixel_distance: 400,
          real_distance_mm: 40,
          confidence: 0.95,
          confirmed: true,
        },
      },
    };

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={tracedProject} />
      </BrowserRouter>
    );

    const overlay = screen.getByAltText(/Analysis crop overlay for Interface A/i) as HTMLImageElement;
    expect(overlay.src).toContain('/api/projects/proj_123/interfaces/interface_a/overlay_svg');
    expect(overlay).toHaveAttribute('width', '512');
    expect(overlay).toHaveAttribute('height', '256');
    expect(screen.getByText(/Overlay base: Analysis crop/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /Original/i }));
    const original = screen.getByAltText(/Original source file for Interface A/i) as HTMLImageElement;
    expect(original.src).toContain('/api/projects/proj_123/interfaces/interface_a/image');
  });

  it('hydrates aligned overlay metadata after refresh', () => {
    const hydratedProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        profile_type: 'traced_closed',
        analysis_image_ref: 'artifacts/cleaned_profile.png',
        analysis_image_width: 640,
        analysis_image_height: 480,
        overlay_svg_ref: 'artifacts/overlay_profile.svg',
        traced_outer_contour: {
          id: 'outer_contour',
          points: [
            { x: -20, y: -20 },
            { x: 20, y: -20 },
            { x: 20, y: 20 },
            { x: -20, y: 20 },
          ],
          is_closed: true,
          classification: 'outer_contour',
          provenance: 'analysis',
          confidence: 0.9,
          point_count: 4,
        },
        traced_hole_contours: [],
      },
    };

    const { rerender } = render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={hydratedProject} />
      </BrowserRouter>
    );
    rerender(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={{ ...hydratedProject }} />
      </BrowserRouter>
    );

    const overlay = screen.getByAltText(/Analysis crop overlay for Interface A/i);
    expect(overlay).toHaveAttribute('width', '640');
    expect(overlay).toHaveAttribute('height', '480');
  });

  it('shows unavailable overlay state instead of falling back to original upload', () => {
    const missingArtifactProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        profile_type: 'traced_closed',
        overlay_svg_ref: null,
        analysis_image_ref: null,
        traced_outer_contour: {
          id: 'outer_contour',
          points: [
            { x: -20, y: -20 },
            { x: 20, y: -20 },
            { x: 20, y: 20 },
            { x: -20, y: 20 },
          ],
          is_closed: true,
          classification: 'outer_contour',
          provenance: 'analysis',
          confidence: 0.9,
          point_count: 4,
        },
        traced_hole_contours: [],
      },
    };

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={missingArtifactProject} />
      </BrowserRouter>
    );

    expect(screen.getByText(/Overlay unavailable because the analysis crop artifact is missing/i)).toBeInTheDocument();
    expect(screen.queryByAltText(/overlay background/i)).not.toBeInTheDocument();
  });


  it('supports two-point SVG scale calibration with snapping and backend confirmation', async () => {
    const tracedProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        profile_type: 'traced_closed',
        traced_outer_contour: {
          id: 'outer_contour',
          points: [
            { x: 0, y: 0 },
            { x: 100, y: 0 },
            { x: 100, y: 50 },
            { x: 0, y: 50 },
          ],
          is_closed: true,
          classification: 'outer_contour',
          provenance: 'analysis',
          confidence: 1,
          point_count: 4,
        },
        traced_hole_contours: [],
        scale_calibration: {
          source: 'user_calibration',
          method: 'two_point_trace',
          reference_dimension: 'two_point_distance',
          pixel_distance: 0,
          real_distance_mm: 40,
          scale_factor: 0,
          confidence: 1,
          confirmed: false,
        },
      },
    };
    vi.mocked(api.snapScalePoint)
      .mockResolvedValueOnce({ point: { x: 0, y: 0 }, distance_px: 3, feature_id: 'outer_contour' })
      .mockResolvedValueOnce({ point: { x: 100, y: 0 }, distance_px: 2, feature_id: 'outer_contour' });
    vi.mocked(api.calibrateInterfaceScale).mockResolvedValue({
      ...tracedProject,
      interface_a: {
        ...tracedProject.interface_a,
        scale_calibration: {
          source: 'user_calibration',
          method: 'two_point_trace',
          reference_dimension: 'two_point_distance',
          point_a: { x: 0, y: 0 },
          point_b: { x: 100, y: 0 },
          pixel_distance: 100,
          real_distance_mm: 40,
          scale_factor: 0.4,
          confidence: 1,
          confirmed: true,
        },
      },
    });

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={tracedProject} />
      </BrowserRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /Calibrate Scale/i }));
    const svg = screen.getByRole('img', { name: /Traced closed profile SVG/i });
    fireEvent.click(svg);
    fireEvent.click(svg);

    await waitFor(() => expect(api.calibrateInterfaceScale).toHaveBeenCalledWith(
      'proj_123',
      'interface_a',
      expect.objectContaining({ confirmed: false }),
      'tok_abc'
    ));

    fireEvent.click(screen.getByRole('button', { name: /Confirm Two-point Scale/i }));
    await waitFor(() => expect(api.calibrateInterfaceScale).toHaveBeenCalledWith(
      'proj_123',
      'interface_a',
      expect.objectContaining({ confirmed: true, real_distance_mm: 40 }),
      'tok_abc'
    ));
  });

  it('hydrates two-point calibration markers after refresh and invalidates on real distance edit', () => {
    const hydratedProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        profile_type: 'traced_closed',
        traced_outer_contour: {
          id: 'outer_contour',
          points: [
            { x: 0, y: 0 },
            { x: 100, y: 0 },
            { x: 100, y: 50 },
            { x: 0, y: 50 },
          ],
          is_closed: true,
          classification: 'outer_contour',
          provenance: 'analysis',
          confidence: 1,
          point_count: 4,
        },
        traced_hole_contours: [],
        scale_calibration: {
          source: 'user_calibration',
          method: 'two_point_trace',
          reference_dimension: 'two_point_distance',
          point_a: { x: 0, y: 0 },
          point_b: { x: 100, y: 0 },
          pixel_distance: 100,
          real_distance_mm: 40,
          scale_factor: 0.4,
          confidence: 1,
          confirmed: true,
        },
      },
    };
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={hydratedProject} />
      </BrowserRouter>
    );

    expect(screen.getByText(/A: 0.00, 0.00/i)).toBeInTheDocument();
    expect(screen.getByText(/B: 100.00, 0.00/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Or enter real distance/i), { target: { value: '50' } });
    expect(screen.getAllByText(/Scale unconfirmed/i).length).toBeGreaterThan(0);
  });
});
