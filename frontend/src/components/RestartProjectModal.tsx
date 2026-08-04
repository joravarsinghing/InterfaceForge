import React, { useEffect, useRef } from 'react';

interface RestartProjectModalProps {
  onCancel: () => void;
  onConfirm: () => void;
}

export const RestartProjectModal: React.FC<RestartProjectModalProps> = ({ onCancel, onConfirm }) => {
  const cancelButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cancelButtonRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCancel();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onCancel]);

  return (
    <div className="modal-overlay" role="presentation" onMouseDown={(event) => event.stopPropagation()}>
      <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="restart-project-heading">
        <h3 id="restart-project-heading">Restart Project?</h3>
        <p>Are you sure you want to start a new project? Your current active project state will be reset in this browser session.</p>
        <div className="modal-actions">
          <button ref={cancelButtonRef} type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
          <button type="button" className="btn btn-primary btn-danger-confirm" onClick={onConfirm}>Confirm &amp; Restart</button>
        </div>
      </div>
    </div>
  );
};

export default RestartProjectModal;
