import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RestartProjectModal } from '../components/RestartProjectModal';

describe('RestartProjectModal', () => {
  it('uses the shared backdrop/dialog contract and supports cancel, escape, and confirm', () => {
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    render(<RestartProjectModal onCancel={onCancel} onConfirm={onConfirm} />);

    expect(screen.getByRole('presentation')).toHaveClass('modal-overlay');
    expect(screen.getByRole('dialog', { name: 'Restart Project?' })).toHaveClass('modal-card');
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onCancel).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: 'Confirm & Restart' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
