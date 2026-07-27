import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Project } from '../types/schema';
import { STEP_ORDER, getEarliestIncompleteStep } from '../services/workflow';

interface ProtectedRouteProps {
  project: Project | null;
  isHydrating?: boolean;
  children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  project,
  isHydrating = false,
  children,
}) => {
  const location = useLocation();

  if (isHydrating) {
    return (
      <div className="loading-state container" role="status" aria-live="polite" style={{ padding: '3rem', textAlign: 'center' }}>
        <div className="spinner" />
        <p style={{ marginTop: '1rem', color: 'var(--text-secondary)' }}>Restoring project session...</p>
      </div>
    );
  }

  // Redirect to start/landing page if no project is loaded
  if (!project) {
    return <Navigate to="/" replace />;
  }

  const currentPath = location.pathname;
  const targetOrder = STEP_ORDER[currentPath] ?? 0;
  const earliestPath = getEarliestIncompleteStep(project);
  const maxAllowedOrder = STEP_ORDER[earliestPath] ?? 0;

  // If attempting to access a step beyond what's allowed by project state, redirect
  if (targetOrder > maxAllowedOrder) {
    return <Navigate to={earliestPath} replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
