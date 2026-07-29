import React from 'react';
import { useLocation, Link } from 'react-router-dom';
import { Project } from '../types/schema';
import { getInterfaceStepPath } from '../services/workflow';

interface StepNavigationProps {
  project?: Project | null;
}

interface StepItem {
  id: number;
  path: string;
  analysisPath?: string;
  fullName: string;
  isCompleted: boolean;
  isLocked: boolean;
}

export const StepNavigation: React.FC<StepNavigationProps> = ({ project }) => {
  const location = useLocation();

  const interfaceAApproved = project?.interface_a?.approved ?? false;
  const interfaceBApproved = project?.interface_b?.approved ?? false;
  const connectionConfigured = (project?.connection?.length_mm ?? 0) > 0;
  const modelGenerated =
    (project?.current_model_revision !== null && project?.current_model_revision !== undefined) ||
    (project?.last_known_good_model_revision !== null && project?.last_known_good_model_revision !== undefined) ||
    ((project?.model_revisions?.length ?? 0) > 0);

  const steps: StepItem[] = [
    {
      id: 1,
      path: getInterfaceStepPath(project ?? null, 'interface_a'),
      analysisPath: '/step1/analysis',
      fullName: 'Interface A Capture',
      isCompleted: interfaceAApproved,
      isLocked: false,
    },
    {
      id: 2,
      path: getInterfaceStepPath(project ?? null, 'interface_b'),
      analysisPath: '/step2/analysis',
      fullName: 'Interface B Capture',
      isCompleted: interfaceBApproved,
      isLocked: !interfaceAApproved,
    },
    {
      id: 3,
      path: '/step3',
      fullName: 'Configure Connection',
      isCompleted: connectionConfigured,
      isLocked: !interfaceAApproved || !interfaceBApproved,
    },
    {
      id: 4,
      path: '/step4',
      fullName: 'Generate Model',
      isCompleted: modelGenerated,
      isLocked: !interfaceAApproved || !interfaceBApproved || !connectionConfigured,
    },
    {
      id: 5,
      path: '/step5',
      fullName: 'Review & Export',
      isCompleted: project?.state === 'export_ready',
      isLocked: !modelGenerated,
    },
  ];

  return (
    <nav className="step-navigation" aria-label="Workflow progress navigation">
      <div className="step-container">
        {steps.map((step) => {
          const isActive =
            location.pathname === step.path ||
            (step.analysisPath && location.pathname === step.analysisPath);

          let className = 'step-item';
          if (isActive) className += ' active';
          if (step.isCompleted) className += ' completed';
          if (step.isLocked) className += ' locked';

          return (
            <div key={step.id} className={className}>
              {step.isLocked ? (
                <span
                  className="step-link disabled"
                  aria-disabled="true"
                  title={`${step.fullName} (Locked - complete prior prerequisite steps first)`}
                >
                  <span className="step-number">{step.id}</span>
                  <span className="step-text">{step.fullName}</span>
                  <span className="step-lock-icon" aria-hidden="true"></span>
                </span>
              ) : (
                <Link
                  to={step.path}
                  className="step-link"
                  aria-current={isActive ? 'step' : undefined}
                >
                  <span className="step-number">
                    {step.isCompleted ? '' : step.id}
                  </span>
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

export default StepNavigation;
