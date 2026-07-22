import React from 'react';
import { useLocation, Link } from 'react-router-dom';

interface Step {
  id: number;
  path: string;
  shortName: string;
  fullName: string;
  isLocked: boolean;
}

export const StepNavigation: React.FC = () => {
  const location = useLocation();

  const steps: Step[] = [
    { id: 1, path: '/step1', shortName: '1 Interface A', fullName: 'Interface A Capture', isLocked: false },
    { id: 2, path: '/step2', shortName: '2 Interface B', fullName: 'Interface B Capture', isLocked: false },
    { id: 3, path: '/step3', shortName: '3 Connection', fullName: 'Configure Connection', isLocked: false },
    { id: 4, path: '/step4', shortName: '4 Generate', fullName: 'Generate Model', isLocked: true },
    { id: 5, path: '/step5', shortName: '5 Review & Export', fullName: 'Review & Export', isLocked: true },
  ];

  return (
    <nav className="step-navigation" aria-label="Workflow progress navigation">
      <div className="step-container">
        {steps.map((step) => {
          const isActive = location.pathname === step.path;

          return (
            <div
              key={step.id}
              className={`step-item ${isActive ? 'active' : ''} ${step.isLocked ? 'locked' : ''}`}
            >
              {step.isLocked ? (
                <span
                  className="step-link disabled"
                  aria-disabled="true"
                  title={`${step.fullName} (Implementation in progress - locked in Stage S2)`}
                >
                  <span className="step-number">{step.id}</span>
                  <span className="step-text">{step.fullName}</span>
                  <span className="step-lock-icon" aria-hidden="true">🔒</span>
                </span>
              ) : (
                <Link
                  to={step.path}
                  className="step-link"
                  aria-current={isActive ? 'step' : undefined}
                >
                  <span className="step-number">{step.id}</span>
                  <span className="step-text">{step.fullName}</span>
                </Link>
              )}
            </div>
          );
        })}
      </div>
    </nav>
  );
};
