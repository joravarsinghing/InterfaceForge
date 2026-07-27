import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import UploadPage from '../pages/UploadPage';
import * as apiModule from '../services/api';
import { Project } from '../types/schema';

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api');
  return {
    ...actual,
    uploadInterfaceImage: vi.fn(),
    analyzeInterfaceImage: vi.fn(),
  };
});

// Mock URL.createObjectURL and revokeObjectURL for Vitest jsdom environment
if (typeof window !== 'undefined') {
  window.URL.createObjectURL = vi.fn(() => 'blob:mock-preview-url');
  window.URL.revokeObjectURL = vi.fn();
}

const mockProject: Project = {
  project_id: 'proj-123',
  project_token: 'tok-123',
  schema_version: '0.1',
  state: 'new',
  created_at: '2026-07-22T00:00:00Z',
  updated_at: '2026-07-22T00:00:00Z',
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
    length_mm: 20,
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

describe('UploadPage Component', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('renders upload dropzone and guidance panel for Interface A', () => {
    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );

    expect(screen.getByText('Interface A — Upload Image or Sketch')).toBeInTheDocument();
    expect(screen.getByText(/Drag & drop your interface image here/i)).toBeInTheDocument();
    expect(screen.getByText('Image Guidance')).toBeInTheDocument();
    expect(screen.getByText(/GOOD CAPTURE/i)).toBeInTheDocument();
    expect(screen.getByText(/BAD CAPTURE/i)).toBeInTheDocument();
  });

  it('supports keyboard navigation and activation on Choose Image label', () => {
    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );

    const chooseLabel = screen.getByText('Choose Image File');
    expect(chooseLabel).toHaveAttribute('tabindex', '0');
    fireEvent.keyDown(chooseLabel, { key: 'Enter', code: 'Enter' });
    fireEvent.keyDown(chooseLabel, { key: ' ', code: 'Space' });
  });

  it('shows prerequisite warning when Interface B is opened before Interface A is approved', () => {
    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_b" project={mockProject} />
      </MemoryRouter>
    );

    expect(screen.getByText('Interface B — Prerequisite Required')).toBeInTheDocument();
    expect(screen.getByText(/Interface A must be reviewed and approved/i)).toBeInTheDocument();
  });

  it('handles file selection, preview generation, and cancel actions', async () => {
    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );

    const file = new File(['fake-png-content'], 'test_circle.png', { type: 'image/png' });
    const fileInput = screen.getByLabelText('Choose Image File');

    fireEvent.change(fileInput, { target: { files: [file] } });

    expect(screen.getByText('Selected Image Preview')).toBeInTheDocument();
    expect(screen.getByText('test_circle.png')).toBeInTheDocument();
    expect(screen.getByText('Use This Image and Analyze')).toBeInTheDocument();

    // Test cancel action
    const cancelButton = screen.getByText('Cancel / Remove');
    fireEvent.click(cancelButton);

    expect(screen.queryByText('Selected Image Preview')).not.toBeInTheDocument();
    expect(screen.getByText('Drag & drop your interface image here')).toBeInTheDocument();
  });

  it('executes upload and analysis flow on button click', async () => {
    vi.mocked(apiModule.uploadInterfaceImage).mockResolvedValue({
      artifact_ref: 'artifacts/uploads/upload_test.png',
      original_filename: 'test_circle.png',
      stored_filename: 'upload_test.png',
      content_type: 'image/png',
      size_bytes: 100,
      uploaded_at: '2026-07-22T00:00:00Z',
    });

    vi.mocked(apiModule.analyzeInterfaceImage).mockResolvedValue({
      profile_type: 'circle',
      candidate_points: [],
      candidate_dimensions: [],
      provenance: 'image_extracted',
      confidence: 0.95,
      warnings: [],
      rejection_reasons: [],
      success: true,
    });

    const onComplete = vi.fn();

    render(
      <MemoryRouter>
        <UploadPage
          interfaceId="interface_a"
          project={mockProject}
          onAnalysisComplete={onComplete}
        />
      </MemoryRouter>
    );

    const file = new File(['fake-png-content'], 'test_circle.png', { type: 'image/png' });
    const fileInput = screen.getByLabelText('Choose Image File');
    fireEvent.change(fileInput, { target: { files: [file] } });

    const confirmButton = screen.getByText('Use This Image and Analyze');
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(apiModule.uploadInterfaceImage).toHaveBeenCalledWith(
        'proj-123',
        'interface_a',
        file,
        'tok-123'
      );
      expect(apiModule.analyzeInterfaceImage).toHaveBeenCalledWith(
        'proj-123',
        'interface_a',
        'tok-123'
      );
      expect(onComplete).toHaveBeenCalled();
    });
  });

  it('displays error banner when upload fails', async () => {
    vi.mocked(apiModule.uploadInterfaceImage).mockRejectedValue(
      new Error('[IF-FILE-400] Unsupported image format')
    );

    render(
      <MemoryRouter>
        <UploadPage interfaceId="interface_a" project={mockProject} />
      </MemoryRouter>
    );

    const file = new File(['fake-content'], 'bad.txt', { type: 'text/plain' });
    const fileInput = screen.getByLabelText('Choose Image File');
    fireEvent.change(fileInput, { target: { files: [file] } });

    fireEvent.click(screen.getByText('Use This Image and Analyze'));

    await waitFor(() => {
      expect(screen.getByText('[IF-FILE-400] Unsupported image format')).toBeInTheDocument();
    });
  });
});
