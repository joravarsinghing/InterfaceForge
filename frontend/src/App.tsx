import React, { useEffect, useState, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
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
import { fetchHealthStatus, createProject, fetchProject, fetchProviderModeStatus, updateProviderMode, validateDefaultProviderMode, HealthResponse, APIState } from './services/api';
import { AnalysisResult, Project, ProviderMode, ProviderModeStatus } from './types/schema';

const PROVIDER_MODE_PREFERENCE_KEY = 'interfaceforge_provider_mode';

export const AppContent: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  }, [location.pathname, location.search]);
  const [healthState, setHealthState] = useState<APIState<HealthResponse>>({
    data: null,
    loading: true,
    error: null,
  });

  const [project, setProject] = useState<Project | null>(null);
  const [preProjectProviderMode, setPreProjectProviderMode] = useState<ProviderMode>(() => {
    return sessionStorage.getItem(PROVIDER_MODE_PREFERENCE_KEY) === 'live' ? 'live' : 'mock';
  });
  const [providerStatus, setProviderStatus] = useState<ProviderModeStatus | null>(null);
  const [providerModeError, setProviderModeError] = useState<string | null>(null);
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
            fetchProviderModeStatus(hydrated.project_id, savedToken || undefined)
              .then(setProviderStatus)
              .catch(() => setProviderStatus(null));
          } else {
            sessionStorage.removeItem('interfaceforge_project_id');
            sessionStorage.removeItem('interfaceforge_project_token');
            setProject(null);
            setProviderStatus(null);
          }
        })
        .catch(() => {
          sessionStorage.removeItem('interfaceforge_project_id');
          sessionStorage.removeItem('interfaceforge_project_token');
          setProject(null);
          setProviderStatus(null);
        })
        .finally(() => {
          setIsHydrating(false);
        });
    } else {
      const preferred = sessionStorage.getItem(PROVIDER_MODE_PREFERENCE_KEY) === 'live' ? 'live' : 'mock';
      setPreProjectProviderMode(preferred);
      validateDefaultProviderMode(preferred)
        .then((status) => {
          setProviderStatus(status);
          setProviderModeError(null);
          const effectiveMode = status.effective_mode;
          setPreProjectProviderMode(effectiveMode);
          sessionStorage.setItem(PROVIDER_MODE_PREFERENCE_KEY, effectiveMode);
        })
        .catch((err: unknown) => {
          const errorMessage = err instanceof Error ? err.message : 'Provider mode could not be checked.';
          setProviderModeError(errorMessage);
          setPreProjectProviderMode('mock');
          sessionStorage.setItem(PROVIDER_MODE_PREFERENCE_KEY, 'mock');
          validateDefaultProviderMode('mock').then(setProviderStatus).catch(() => setProviderStatus(null));
        })
        .finally(() => {
          setIsHydrating(false);
        });
    }
  }, [checkBackendHealth]);

  // Project Creation Handler
  const handleStartProject = useCallback(async (): Promise<Project> => {
    const newProject = await createProject(preProjectProviderMode);
    sessionStorage.setItem('interfaceforge_project_id', newProject.project_id);
    sessionStorage.setItem('interfaceforge_project_token', newProject.project_token);
    setProject(newProject);
    setProviderModeError(null);
    setProviderStatus(await fetchProviderModeStatus(newProject.project_id, newProject.project_token));
    return newProject;
  }, [preProjectProviderMode]);

  const handleContinueProject = useCallback(async (): Promise<Project | null> => {
    const savedId = sessionStorage.getItem('interfaceforge_project_id') || project?.project_id;
    const savedToken = sessionStorage.getItem('interfaceforge_project_token') || project?.project_token;
    if (!savedId) return project;
    const hydrated = await fetchProject(savedId, savedToken || undefined);
    setProject(hydrated);
    fetchProviderModeStatus(hydrated.project_id, savedToken || undefined)
      .then(setProviderStatus)
      .catch(() => setProviderStatus(null));
    return hydrated;
  }, [project]);
  // Project Restart Handler
  const handleRestartProject = useCallback(() => {
    sessionStorage.removeItem('interfaceforge_project_id');
    sessionStorage.removeItem('interfaceforge_project_token');
    setProject(null);
    navigate('/');
  }, [navigate]);

  const handleProviderModeChange = useCallback(async (mode: ProviderMode): Promise<void> => {
    setProviderModeError(null);
    try {
      if (project) {
        const result = await updateProviderMode(project.project_id, mode, project.project_token);
        setProject(result.project);
        setProviderStatus(result.provider_status);
        setPreProjectProviderMode(result.provider_status.effective_mode);
        sessionStorage.setItem(PROVIDER_MODE_PREFERENCE_KEY, result.provider_status.effective_mode);
        return;
      }

      const status = await validateDefaultProviderMode(mode);
      setProviderStatus(status);
      setPreProjectProviderMode(status.effective_mode);
      sessionStorage.setItem(PROVIDER_MODE_PREFERENCE_KEY, status.effective_mode);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Provider mode could not be changed.';
      setProviderModeError(errorMessage);
      if (project) {
        try {
          const status = await fetchProviderModeStatus(project.project_id, project.project_token);
          setProviderStatus(status);
          setPreProjectProviderMode(status.effective_mode);
          sessionStorage.setItem(PROVIDER_MODE_PREFERENCE_KEY, status.effective_mode);
        } catch {
          setProviderStatus(null);
        }
      } else {
        setPreProjectProviderMode('mock');
        sessionStorage.setItem(PROVIDER_MODE_PREFERENCE_KEY, 'mock');
        try {
          setProviderStatus(await validateDefaultProviderMode('mock'));
        } catch {
          setProviderStatus(null);
        }
      }
    }
  }, [project]);
  return (
    <div className="app-shell">
      <SkipLink />
      <Header
        healthState={healthState}
        project={project}
        onRetryHealth={checkBackendHealth}
        onRestartProject={handleRestartProject}
      providerStatus={providerStatus}
        providerModeError={providerModeError}
        onProviderModeChange={handleProviderModeChange}
      />
      <StepNavigation project={project} onStartProject={handleStartProject} />

      <main id="main-content" className="app-main" tabIndex={-1}>
        <Routes>
          <Route
            path="/"
            element={
              <LandingPage
                healthState={healthState}
                project={project}
                isHydrating={isHydrating}
                onRetryHealth={checkBackendHealth}
                onStartProject={handleStartProject}
                onContinueProject={handleContinueProject}
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
                  onProjectUpdate={(updated) => setProject(updated)}
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
                  onProjectUpdate={(updated) => setProject(updated)}
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
