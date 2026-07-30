import { expect, test } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GeometryPreview } from '../components/GeometryPreview';
import type { Project } from '../types/schema';

const project = {
  interface_a: { profile_type: 'circle', dimensions: [{ id: 'outer_diameter', value: 40 }] },
  interface_b: { profile_type: 'rounded_rectangle', dimensions: [{ id: 'width', value: 50 }, { id: 'height', value: 40 }, { id: 'corner_radius', value: 5 }] },
  connection: { mode: 'coaxial', length_mm: 40, offset_x_mm: 0, offset_y_mm: 0, angle_deg: 0 },
  manufacturing: { wall_thickness_mm: 2.4, clearance_a_mm: 0.3, clearance_b_mm: 0.1 },
} as unknown as Project;

test('shared preview defaults to isometric X/Y/Z geometry with inner boundaries', () => {
  render(<GeometryPreview project={project} />);
  expect(screen.getByTestId('shared-geometry-preview')).toBeInTheDocument();
  expect(screen.getByRole('img', { name: /isometric adapter preview using x, y, and z/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Isometric' })).toHaveAttribute('aria-pressed', 'true');
});
