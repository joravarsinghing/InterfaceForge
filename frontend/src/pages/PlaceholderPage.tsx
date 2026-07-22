import React from 'react';

interface PlaceholderPageProps {
  stepName: string;
  stepNumber: number;
}

export const PlaceholderPage: React.FC<PlaceholderPageProps> = ({ stepName, stepNumber }) => {
  return (
    <div className="placeholder-page">
      <div className="placeholder-card">
        <span className="step-tag">Step {stepNumber}</span>
        <h1>{stepName}</h1>
        <p className="placeholder-description">
          This workflow stage is scheduled for implementation in a future stage (S3+).
        </p>
        <div className="placeholder-note">
          <p>
            <strong>Stage S2 Scope:</strong> Infrastructure and local environment setup only. Product features remain locked per repository governance.
          </p>
        </div>
        <a href="/" className="btn btn-secondary">
          Return to Landing Page
        </a>
      </div>
    </div>
  );
};
