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

    expect(screen.getByText(/Interface A — Profile Review & Approval/i)).toBeInTheDocument();
    expect(screen.getByText(/Source Image/i)).toBeInTheDocument();
    expect(screen.getByText(/Clean SVG Profile/i)).toBeInTheDocument();
    expect(screen.getByTitle(/circle Profile Preview/i)).toBeInTheDocument();
  });

  it('supports profile-type selector and updates dimensions list', () => {
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={mockProject} />
      </BrowserRouter>
    );

    const select = screen.getByLabelText(/Detected Profile Type/i) as HTMLSelectElement;
    expect(select.value).toBe('circle');

    fireEvent.change(select, { target: { value: 'rectangle' } });
    expect(select.value).toBe('rectangle');
    expect(screen.getByText(/Width/i)).toBeInTheDocument();
    expect(screen.getByText(/Height/i)).toBeInTheDocument();
  });

  it('displays provenance labels with explicit text and icons (not color alone)', () => {
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={mockProject} />
      </BrowserRouter>
    );

    expect(screen.getByText(/Legend:/i)).toBeInTheDocument();
    expect(screen.getByText(/👤 User Entered/i)).toBeInTheDocument();
    expect(screen.getByText(/📷 Image Extracted/i)).toBeInTheDocument();
    expect(screen.getByText(/⚙️ System Inferred/i)).toBeInTheDocument();
    expect(screen.getByText(/❓ Unresolved/i)).toBeInTheDocument();
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
    expect(screen.getByText(/Scale Unconfirmed/i)).toBeInTheDocument();
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
        primitive_fallback_label: 'Simplified envelope — not the exact cross-section',
      },
    };

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={fallbackProject} />
      </BrowserRouter>
    );

    expect(screen.getAllByText(/Simplified envelope — not the exact cross-section/i).length).toBeGreaterThan(0);
  });
});
