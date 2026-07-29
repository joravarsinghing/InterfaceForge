import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
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


beforeEach(() => {
  vi.clearAllMocks();
});
describe('ProfileReviewPage Component', () => {
  it('renders source image, clean SVG, calibration, and display-only dimensions', () => {
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={mockProject} />
      </BrowserRouter>
    );

    expect(screen.getByRole('heading', { name: /Interface A.*Profile Review & Approval/i })).toBeInTheDocument();
    expect(screen.getByText(/Source Image/i)).toBeInTheDocument();
    expect(screen.getByText(/Clean SVG Profile/i)).toBeInTheDocument();
    expect(screen.getByRole('region', { name: /Calibration/i })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: /Interface Dimensions/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Add Dimension Parameter/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Update Profile/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Confirm Scale/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Update & Confirm/i })).not.toBeInTheDocument();
  });

  it('shows detected profile type and raw scale only in collapsed technical details', () => {
    const project: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
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
        <ProfileReviewPage interfaceId="interface_a" project={project} />
      </BrowserRouter>
    );

    expect(screen.queryByLabelText(/Detected Profile Type/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Technical details/i)).toBeInTheDocument();
    expect(screen.getByText(/Detected profile type/i)).toBeInTheDocument();
    expect(screen.getByText(/Pixel distance/i)).toBeInTheDocument();
    expect(screen.getByText(/Scale factor/i)).toBeInTheDocument();
  });

  it('uses one consistent Replace Image action', () => {
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={mockProject} />
      </BrowserRouter>
    );

    expect(screen.getAllByRole('button', { name: /Replace Image/i })).toHaveLength(2);
    expect(screen.queryByRole('button', { name: /Upload Better Image/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Re-upload Image/i })).not.toBeInTheDocument();
  });

  it('blocks approval before confirmed two-point calibration', () => {
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={mockProject} />
      </BrowserRouter>
    );

    expect(screen.getByText(/Two-point calibration must be confirmed/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Approve Interface A/i })).toBeDisabled();
  });

  it('shows display-only primitive dimensions after confirmed calibration', () => {
    const calibratedProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
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
        scale_calibration: {
          source: 'user_calibration',
          method: 'two_point_trace',
          reference_dimension: 'two_point_distance',
          point_a: { x: 0, y: 0 },
          point_b: { x: 100, y: 0 },
          pixel_distance: 100,
          real_distance_mm: 50,
          scale_factor: 0.5,
          confidence: 1,
          confirmed: true,
        },
      },
    };

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={calibratedProject} />
      </BrowserRouter>
    );

    expect(screen.getAllByText(/Outer Diameter/i).length).toBeGreaterThan(0);
    expect(screen.queryByRole('spinbutton', { name: /Value for Outer Diameter/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: /Provenance/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: /Critical/i })).not.toBeInTheDocument();
  });

  it('preserves legacy unmapped dimensions only in technical compatibility details', () => {
    const legacyProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        dimensions: [
          ...mockProject.interface_a.dimensions,
          {
            id: 'custom_dim_1',
            label: 'Custom Dimension 1',
            value: 12,
            unit: 'mm',
            provenance: 'user_entered',
            confidence: 1,
            critical: true,
            feature_ref: null,
            consistency_state: 'unmapped',
          },
        ],
      },
    };
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={legacyProject} />
      </BrowserRouter>
    );

    expect(screen.getByText(/Legacy unmapped dimensions/i)).toBeInTheDocument();
    expect(screen.getByText(/Custom Dimension 1: stored for compatibility, not used for generation/i)).toBeInTheDocument();
  });

  it('calls snap and calibration APIs for two-point SVG calibration', async () => {
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

    fireEvent.click(screen.getByRole('button', { name: /Calibrate/i }));
    const svg = screen.getByRole('img', { name: /Traced closed profile SVG/i });
    fireEvent.click(svg);
    fireEvent.click(svg);

    await waitFor(() => expect(api.calibrateInterfaceScale).toHaveBeenCalledWith(
      'proj_123',
      'interface_a',
      expect.objectContaining({ confirmed: false }),
      'tok_abc'
    ));

    fireEvent.click(screen.getByRole('button', { name: /Confirm Calibration/i }));
    await waitFor(() => expect(api.calibrateInterfaceScale).toHaveBeenCalledWith(
      'proj_123',
      'interface_a',
      expect.objectContaining({ confirmed: true, real_distance_mm: 40 }),
      'tok_abc'
    ));
  });

  it('hydrates markers after refresh and invalidates on real distance edit', () => {
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
    fireEvent.change(screen.getByLabelText(/Real distance in mm/i), { target: { value: '50' } });
    expect(screen.getAllByText(/Calibration needed/i).length).toBeGreaterThan(0);
  });

  it('renders approved state and uses recalibrate action', () => {
    const approvedProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        approved: true,
        approved_at: '2026-07-22T01:00:00Z',
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
      state: 'interface_a_approved',
    };

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={approvedProject} />
      </BrowserRouter>
    );

    expect(screen.getByText(/Status: Approved/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Recalibrate/i })).toBeInTheDocument();
  });
});


const primitiveContour = {
  id: 'outer_contour',
  points: [
    { x: -25, y: 0 },
    { x: 0, y: 25 },
    { x: 25, y: 0 },
    { x: 0, y: -25 },
  ],
  is_closed: true,
  classification: 'outer_contour' as const,
  provenance: 'opencv_primitive',
  confidence: 1,
  point_count: 4,
};

describe('Primitive Profile Calibration', () => {
  it('registers first and second primitive calibration points immediately without double-scaling markers', async () => {
    const primitiveProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        analysis_provider_name: 'opencv',
        traced_outer_contour: primitiveContour,
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
      .mockResolvedValueOnce({ point: { x: -25, y: 0 }, distance_px: 1, feature_id: 'outer_contour' })
      .mockResolvedValueOnce({ point: { x: 25, y: 0 }, distance_px: 1, feature_id: 'outer_contour' });
    vi.mocked(api.calibrateInterfaceScale).mockResolvedValue({
      ...primitiveProject,
      interface_a: {
        ...primitiveProject.interface_a,
        scale_calibration: {
          source: 'user_calibration',
          method: 'two_point_trace',
          reference_dimension: 'two_point_distance',
          point_a: { x: -25, y: 0 },
          point_b: { x: 25, y: 0 },
          pixel_distance: 50,
          real_distance_mm: 40,
          scale_factor: 0.8,
          confidence: 1,
          confirmed: false,
        },
      },
    });

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={primitiveProject} />
      </BrowserRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /Calibrate/i }));
    const svg = screen.getByRole('img', { name: /SVG geometry preview for circle profile/i });
    vi.spyOn(svg, 'getBoundingClientRect').mockReturnValue({
      left: 0,
      top: 0,
      width: 360,
      height: 280,
      right: 360,
      bottom: 280,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });

    fireEvent.click(svg, { clientX: 80, clientY: 140 });
    await waitFor(() => expect(screen.getByText(/A: -25.00, 0.00/i)).toBeInTheDocument());
    const markerA = await screen.findByTestId('calibration-marker-a');
    expect(markerA).toHaveAttribute('cx', '-25');
    expect(markerA).toHaveAttribute('cy', '0');

    fireEvent.click(svg, { clientX: 280, clientY: 140 });
    await waitFor(() => expect(screen.getByText(/B: 25.00, 0.00/i)).toBeInTheDocument());
    expect(await screen.findByTestId('calibration-marker-b')).toHaveAttribute('cx', '25');
    await waitFor(() => expect(api.calibrateInterfaceScale).toHaveBeenCalledWith(
      'proj_123',
      'interface_a',
      expect.objectContaining({ point_a: { x: -25, y: 0 }, point_b: { x: 25, y: 0 }, confirmed: false }),
      'tok_abc'
    ));
  });

  it('shows backend snap errors for primitive clicks outside boundary tolerance', async () => {
    const primitiveProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        traced_outer_contour: primitiveContour,
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
    vi.mocked(api.snapScalePoint).mockRejectedValueOnce(new Error('[IF-APPROVAL-400] Calibration point is too far from the visible profile boundary.'));

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={primitiveProject} />
      </BrowserRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /Calibrate/i }));
    const svg = screen.getByRole('img', { name: /SVG geometry preview for circle profile/i });
    vi.spyOn(svg, 'getBoundingClientRect').mockReturnValue({
      left: 0,
      top: 0,
      width: 360,
      height: 280,
      right: 360,
      bottom: 280,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
    fireEvent.click(svg, { clientX: 180, clientY: 140 });
    expect(await screen.findByRole('alert')).toHaveTextContent(/too far from the visible profile boundary/i);
  });

  it('uses accurate provider badges for OpenCV and AI-guided analysis', () => {
    const { rerender } = render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={{ ...mockProject, interface_a: { ...mockProject.interface_a, analysis_provider_name: 'opencv' } }} />
      </BrowserRouter>
    );
    expect(screen.getAllByText('OpenCV profile detection').length).toBeGreaterThan(0);
    rerender(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={{ ...mockProject, interface_a: { ...mockProject.interface_a, analysis_provider_name: 'gemini_guided_opencv' } }} />
      </BrowserRouter>
    );
    expect(screen.getAllByText('AI guidance used').length).toBeGreaterThan(0);
  });
});

const roundedRectangleCandidateProject: Project = {
  ...mockProject,
  interface_a: {
    ...mockProject.interface_a,
    profile_type: 'traced_closed',
    primitive_fallback_active: false,
    primitive_promotion_confirmed: false,
    primitive_detection_confidence: 0.9,
    primitive_detection_reason: 'corner_offsets_support_rounded_rectangle',
    generation_unsupported: true,
    generation_unsupported_reason: 'Adapter generation for arbitrary traced profiles is not yet enabled.',
    traced_outer_contour: {
      id: 'outer_contour',
      points: [
        { x: 10, y: 0 }, { x: 50, y: 0 }, { x: 90, y: 0 },
        { x: 100, y: 10 }, { x: 100, y: 30 }, { x: 100, y: 50 },
        { x: 90, y: 60 }, { x: 50, y: 60 }, { x: 10, y: 60 },
        { x: 0, y: 50 }, { x: 0, y: 30 }, { x: 0, y: 10 },
      ],
      is_closed: true,
      classification: 'outer_contour',
      provenance: 'analysis',
      confidence: 1,
      point_count: 12,
    },
    traced_hole_contours: [],
    scale_calibration: {
      source: 'user_calibration',
      method: 'two_point_trace',
      reference_dimension: 'two_point_distance',
      point_a: { x: 0, y: 30 },
      point_b: { x: 100, y: 30 },
      pixel_distance: 100,
      real_distance_mm: 50,
      scale_factor: 0.5,
      confidence: 1,
      confirmed: true,
    },
    dimensions: [
      { id: 'overall_width', label: 'Overall Width', value: 50, unit: 'mm', provenance: 'system_inferred', confidence: 1, critical: true, feature_ref: 'outer_contour' },
      { id: 'overall_height', label: 'Overall Height', value: 30, unit: 'mm', provenance: 'system_inferred', confidence: 1, critical: true, feature_ref: 'outer_contour' },
    ],
  },
};

const confirmedRoundedRectangleProject: Project = {
  ...roundedRectangleCandidateProject,
  interface_a: {
    ...roundedRectangleCandidateProject.interface_a,
    profile_type: 'rounded_rectangle',
    primitive_fallback_active: true,
    primitive_promotion_confirmed: true,
    generation_unsupported: false,
    generation_unsupported_reason: null,
    dimensions: [
      { id: 'width', label: 'Width', value: 50, unit: 'mm', provenance: 'user_entered', confidence: 1, critical: true, feature_ref: 'outer_contour' },
      { id: 'height', label: 'Height', value: 30, unit: 'mm', provenance: 'user_entered', confidence: 1, critical: true, feature_ref: 'outer_contour' },
      { id: 'corner_radius', label: 'Corner Radius', value: 5, unit: 'mm', provenance: 'image_extracted', confidence: 0.82, critical: false, feature_ref: 'outer_contour' },
    ],
  },
};

describe('Profile Review shape confirmation regressions', () => {
  it('shows Use Rounded Rectangle for a calibrated rounded-rectangle trace and hides the unsupported warning', () => {
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={roundedRectangleCandidateProject} />
      </BrowserRouter>
    );

    expect(screen.getByRole('heading', { name: /Detected shape: Rounded rectangle/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Use Rounded Rectangle' })).toBeInTheDocument();
    expect(screen.queryByText(/Arbitrary traced profiles are not supported/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Approve Interface A/i })).toBeDisabled();
  });

  it('clicking Use Rounded Rectangle persists the supported profile and keeps calibration confirmed', async () => {
    vi.mocked(api.patchInterface).mockResolvedValueOnce(confirmedRoundedRectangleProject);
    const onProjectUpdate = vi.fn();

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={roundedRectangleCandidateProject} onProjectUpdate={onProjectUpdate} />
      </BrowserRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Use Rounded Rectangle' }));

    await waitFor(() => expect(api.patchInterface).toHaveBeenCalledWith(
      'proj_123',
      'interface_a',
      expect.objectContaining({
        profile_type: 'rounded_rectangle',
        primitive_fallback_active: true,
        primitive_promotion_confirmed: true,
      }),
      'tok_abc'
    ));
    await waitFor(() => expect(onProjectUpdate).toHaveBeenCalledWith(confirmedRoundedRectangleProject));
    expect(screen.getAllByText(/Shape confirmed/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Arbitrary traced profiles are not supported/i)).not.toBeInTheDocument();
  });

  it('enables approval after valid shape confirmation and persists rounded_rectangle approval', async () => {
    vi.mocked(api.patchInterface).mockResolvedValueOnce(confirmedRoundedRectangleProject);
    vi.mocked(api.approveInterface).mockResolvedValueOnce({
      ...confirmedRoundedRectangleProject,
      interface_a: { ...confirmedRoundedRectangleProject.interface_a, approved: true },
      state: 'interface_a_approved',
    });

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={confirmedRoundedRectangleProject} />
      </BrowserRouter>
    );

    const approve = screen.getByRole('button', { name: /Approve Interface A/i });
    expect(approve).toBeEnabled();
    fireEvent.click(approve);

    await waitFor(() => expect(api.patchInterface).toHaveBeenCalledWith(
      'proj_123',
      'interface_a',
      expect.objectContaining({ profile_type: 'rounded_rectangle', primitive_promotion_confirmed: true }),
      'tok_abc'
    ));
    await waitFor(() => expect(api.approveInterface).toHaveBeenCalled());
  });

  it('keeps confirmed shape visible after refresh', () => {
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={confirmedRoundedRectangleProject} />
      </BrowserRouter>
    );

    expect(screen.getByRole('heading', { name: /Detected shape: Rounded rectangle/i })).toBeInTheDocument();
    expect(screen.getAllByText(/Shape confirmed/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /Approve Interface A/i })).toBeEnabled();
  });

  it('shows the unsupported warning for genuinely complex traces', () => {
    const complexProject: Project = {
      ...roundedRectangleCandidateProject,
      interface_a: {
        ...roundedRectangleCandidateProject.interface_a,
        primitive_detection_confidence: null,
        primitive_detection_reason: null,
        traced_outer_contour: {
          ...roundedRectangleCandidateProject.interface_a.traced_outer_contour!,
          points: [
            { x: 0, y: 0 },
            { x: 80, y: 0 },
            { x: 70, y: 20 },
            { x: 95, y: 35 },
            { x: 60, y: 60 },
            { x: 20, y: 45 },
            { x: 0, y: 60 },
            { x: 15, y: 25 },
          ],
          point_count: 8,
        },
      },
    };

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={complexProject} />
      </BrowserRouter>
    );

    expect(screen.queryByRole('button', { name: /Use Rounded Rectangle/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Arbitrary traced profiles are not supported/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Approve Interface A/i })).toBeDisabled();
  });
});
