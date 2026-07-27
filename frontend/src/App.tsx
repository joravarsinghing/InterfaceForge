import React, { useEffect, useState, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { SkipLink } from './components/SkipLink';
import { Header } from './components/Header';
import { StepNavigation } from './components/StepNavigation';
import { Footer } from './components/Footer';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LandingPage } from './pages/LandingPage';
import { UploadPage } from './pages/UploadPage';
import { ProfileReviewPage } from './pages/ProfileReviewPage';
import { ConnectionConfigPage } from './pages/ConnectionConfigPage';
import { ModelGenerationPage } from './pages/ModelGenerationPage';
import { ResultPage } from './pages/ResultPage';
import { fetchHealthStatus, createProject, fetchProject, HealthResponse, APIState } from './services/api';
import { AnalysisResult, Project } from './types/schema';

export const AppContent: React.FC = () => {
  const navigate = useNavigate();
  const [healthState, setHealthState] = useState<APIState<HealthResponse>>({
    data: null,
    loading: true,
    error: null,
  });

  const [project, setProject] = useState<Project | null>(null);
  const [isHydrating, setIsHydrating] = useState<boolean>(() => {
    return !!sessionStorage.getItem('interfaceforge_project_id');
  });
  const [, setLatestAnalysisA] = useState<AnalysisResult | null>(null);
  const [, setLatestAnalysisB] = useState<AnalysisResult | null>(null);

  // Check Backend Health
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

  // Hydrate session project from sessionStorage on mount
  useEffect(() => {
    checkBackendHealth();
    const savedId = sessionStorage.getItem('interfaceforge_project_id');
    const savedToken = sessionStorage.getItem('interfaceforge_project_token');

    if (savedId) {
      setIsHydrating(true);
      fetchProject(savedId, savedToken || undefined)
        .then((hydrated) => {
          if (hydrated && hydrated.project_id && hydrated.interface_a && hydrated.interface_b) {
            setProject(hydrated);
          } else {
            sessionStorage.removeItem('interfaceforge_project_id');
            sessionStorage.removeItem('interfaceforge_project_token');
            setProject(null);
          }
        })
        .catch(() => {
          sessionStorage.removeItem('interfaceforge_project_id');
          sessionStorage.removeItem('interfaceforge_project_token');
          setProject(null);
        })
        .finally(() => {
          setIsHydrating(false);
        });
    } else {
      setIsHydrating(false);
    }
  }, [checkBackendHealth]);

  // Project Creation Handler
  const handleStartProject = useCallback(async (): Promise<Project> => {
    const newProject = await createProject();
    sessionStorage.setItem('interfaceforge_project_id', newProject.project_id);
    sessionStorage.setItem('interfaceforge_project_token', newProject.project_token);
    setProject(newProject);
    return newProject;
  }, []);

  // Project Restart Handler
  const handleRestartProject = useCallback(() => {
    sessionStorage.removeItem('interfaceforge_project_id');
    sessionStorage.removeItem('interfaceforge_project_token');
    setProject(null);
    navigate('/');
  }, [navigate]);

  return (
    <div className="app-shell">
      <SkipLink />
      <Header
        healthState={healthState}
        project={project}
        onRetryHealth={checkBackendHealth}
        onRestartProject={handleRestartProject}
      />
      <StepNavigation project={project} />

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
              <ProtectedRoute project={project} isHydrating={isHydrating}>
                <UploadPage
                  interfaceId="interface_a"
                  project={project}
                  onAnalysisComplete={(res) => setLatestAnalysisA(res)}
                />
              </ProtectedRoute>
            }
          />
          <Route
            path="/step1/analysis"
            element={
              <ProtectedRoute project={project} isHydrating={isHydrating}>
                <ProfileReviewPage
                  interfaceId="interface_a"
                  project={project}
                  onProjectUpdate={(updated) => setProject(updated)}
                />
              </ProtectedRoute>
            }
          />
          <Route
            path="/step2"
            element={
              <ProtectedRoute project={project} isHydrating={isHydrating}>
                <UploadPage
                  interfaceId="interface_b"
                  project={project}
                  onAnalysisComplete={(res) => setLatestAnalysisB(res)}
                />
              </ProtectedRoute>
            }
          />
          <Route
            path="/step2/analysis"
            element={
              <ProtectedRoute project={project} isHydrating={isHydrating}>
                <ProfileReviewPage
                  interfaceId="interface_b"
                  project={project}
                  onProjectUpdate={(updated) => setProject(updated)}
                />
              </ProtectedRoute>
            }
          />
          <Route
            path="/step3"
            element={
              <ProtectedRoute project={project} isHydrating={isHydrating}>
                <ConnectionConfigPage
                  project={project}
                  onProjectUpdate={(updated) => setProject(updated)}
                />
              </ProtectedRoute>
            }
          />
          <Route
            path="/step4"
            element={
              <ProtectedRoute project={project} isHydrating={isHydrating}>
                <ModelGenerationPage
                  project={project}
                  onProjectUpdate={(updated) => setProject(updated)}
                />
              </ProtectedRoute>
            }
          />
          <Route
            path="/step5"
            element={
              <ProtectedRoute project={project} isHydrating={isHydrating}>
                <ResultPage
                  project={project}
                  onProjectUpdate={(updated) => setProject(updated)}
                  onRestartProject={handleRestartProject}
                />
              </ProtectedRoute>
            }
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
