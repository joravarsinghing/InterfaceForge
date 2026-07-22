import React, { useEffect, useState, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { SkipLink } from './components/SkipLink';
import { Header } from './components/Header';
import { StepNavigation } from './components/StepNavigation';
import { Footer } from './components/Footer';
import { ErrorBoundary } from './components/ErrorBoundary';
import { LandingPage } from './pages/LandingPage';
import { UploadPage } from './pages/UploadPage';
import { ProfileReviewPage } from './pages/ProfileReviewPage';
import { ConnectionConfigPage } from './pages/ConnectionConfigPage';
import { ModelGenerationPage } from './pages/ModelGenerationPage';
import { PlaceholderPage } from './pages/PlaceholderPage';
import { fetchHealthStatus, createProject, HealthResponse, APIState } from './services/api';
import { AnalysisResult, Project } from './types/schema';

export const AppContent: React.FC = () => {
  const [healthState, setHealthState] = useState<APIState<HealthResponse>>({
    data: null,
    loading: true,
    error: null,
  });

  const [project, setProject] = useState<Project | null>(null);
  const [, setLatestAnalysisA] = useState<AnalysisResult | null>(null);
  const [, setLatestAnalysisB] = useState<AnalysisResult | null>(null);

  const checkBackendHealth = useCallback(async () => {
    setHealthState({ data: null, loading: true, error: null });
    try {
      const data = await fetchHealthStatus();
      setHealthState({ data, loading: false, error: null });
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to reach backend server';
      setHealthState({
        data: null,
        loading: false,
        error: errorMessage,
      });
    }
  }, []);

  useEffect(() => {
    checkBackendHealth();
  }, [checkBackendHealth]);

  const handleStartProject = useCallback(async (): Promise<Project> => {
    const newProject = await createProject();
    setProject(newProject);
    return newProject;
  }, []);

  return (
    <div className="app-shell">
      <SkipLink />
      <Header healthState={healthState} onRetryHealth={checkBackendHealth} />
      <StepNavigation />

      <main id="main-content" className="app-main" tabIndex={-1}>
        <Routes>
          <Route
            path="/"
            element={
              <LandingPage
                healthState={healthState}
                onRetryHealth={checkBackendHealth}
                onStartProject={handleStartProject}
              />
            }
          />
          <Route
            path="/step1"
            element={
              <UploadPage
                interfaceId="interface_a"
                project={project}
                onAnalysisComplete={(res) => setLatestAnalysisA(res)}
              />
            }
          />
          <Route
            path="/step1/analysis"
            element={
              <ProfileReviewPage
                interfaceId="interface_a"
                project={project}
                onProjectUpdate={(updated) => setProject(updated)}
              />
            }
          />
          <Route
            path="/step2"
            element={
              <UploadPage
                interfaceId="interface_b"
                project={project}
                onAnalysisComplete={(res) => setLatestAnalysisB(res)}
              />
            }
          />
          <Route
            path="/step2/analysis"
            element={
              <ProfileReviewPage
                interfaceId="interface_b"
                project={project}
                onProjectUpdate={(updated) => setProject(updated)}
              />
            }
          />
          <Route
            path="/step3"
            element={
              <ConnectionConfigPage
                project={project}
                onProjectUpdate={(updated) => setProject(updated)}
              />
            }
          />
          <Route
            path="/step4"
            element={
              <ModelGenerationPage
                project={project}
                onProjectUpdate={(updated) => setProject(updated)}
              />
            }
          />
          <Route
            path="/step5"
            element={<PlaceholderPage stepNumber={5} stepName="Review & Export" />}
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      <Footer healthState={healthState} />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <Router>
        <AppContent />
      </Router>
    </ErrorBoundary>
  );
};

export default App;
