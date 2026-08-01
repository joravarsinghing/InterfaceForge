/**
  * Backend API Client Abstraction
  */

import type {
  AnalysisResult,
  APIEnvelope,
  InterfacePatchRequest,
  Project,
  ProviderMode,
  ProviderModeStatus,
  ProviderModeUpdateResponse,
  ScaleSnapResponse,
  TwoPointScaleCalibrationRequest,
  UploadResponseData,
} from '../types/schema';


export type ServiceState = 'Available' | 'Not configured' | 'Unavailable' | 'Checking';

export interface ServiceStatusRow {
  id: string;
  label: string;
  status: ServiceState;
  message: string;
  model?: string | null;
}

export interface HealthResponse {
  service_name: string;
  status: string;
  environment: string;
  version: string;
  services?: ServiceStatusRow[];
}

export interface ReadyResponse {
  status: string;
  service: string;
  checks: Record<string, string>;
}

export interface APIState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

const BACKEND_BASE_URL =
  import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

export async function fetchHealthStatus(): Promise<HealthResponse> {
  const response = await fetch(`${BACKEND_BASE_URL}/health`, {
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Health check failed with HTTP status ${response.status}`);
  }

  const json = await response.json();
  if (!json.success || !json.data) {
    throw new Error('Invalid health response format from backend');
  }

  return json.data as HealthResponse;
}

export async function fetchReadinessStatus(): Promise<ReadyResponse> {
  const response = await fetch(`${BACKEND_BASE_URL}/ready`, {
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Readiness check failed with HTTP status ${response.status}`);
  }

  const json = await response.json();
  if (!json.success || !json.data) {
    throw new Error('Invalid readiness response format from backend');
  }

  return json.data as ReadyResponse;
}


export async function validateDefaultProviderMode(
  providerMode: ProviderMode
): Promise<ProviderModeStatus> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/projects/provider-mode`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider_mode: providerMode }),
  });
  const json: APIEnvelope<ProviderModeStatus> = await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function fetchProviderModeStatus(
  projectId: string,
  projectToken?: string
): Promise<ProviderModeStatus> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (projectToken) headers['X-Project-Token'] = projectToken;
  const response = await fetch(`${BACKEND_BASE_URL}/api/projects/${projectId}/provider-mode`, {
    headers,
  });
  const json: APIEnvelope<ProviderModeStatus> = await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function updateProviderMode(
  projectId: string,
  providerMode: ProviderMode,
  projectToken?: string
): Promise<ProviderModeUpdateResponse> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (projectToken) headers['X-Project-Token'] = projectToken;
  const response = await fetch(`${BACKEND_BASE_URL}/api/projects/${projectId}/provider-mode`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify({ provider_mode: providerMode }),
  });
  const json: APIEnvelope<ProviderModeUpdateResponse> = await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}
/**
  * Project API client functions matching S3 contracts
  */
export async function createProject(providerMode: ProviderMode = 'mock'): Promise<Project> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider_mode: providerMode }),
  });
  const json: APIEnvelope<Project> = await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function fetchProject(
  projectId: string,
  projectToken?: string
): Promise<Project> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }
  const response = await fetch(`${BACKEND_BASE_URL}/api/projects/${projectId}`, {
    headers,
  });
  const json: APIEnvelope<Project> = await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function approveInterface(
  projectId: string,
  interfaceId: 'interface_a' | 'interface_b',
  projectToken?: string
): Promise<Project> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/interfaces/${interfaceId}/approve`,
    {
      method: 'POST',
      headers,
    }
  );
  const json: APIEnvelope<Project> = await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function uploadInterfaceImage(
  projectId: string,
  interfaceId: 'interface_a' | 'interface_b',
  file: File,
  projectToken?: string,
  knownMeasurement?: { type: string; value: number; unit: string }
): Promise<UploadResponseData> {
  const formData = new FormData();
  formData.append('file', file);
  if (knownMeasurement && Number.isFinite(knownMeasurement.value) && knownMeasurement.value > 0) {
    formData.append('known_measurement_type', knownMeasurement.type);
    formData.append('known_measurement_value', String(knownMeasurement.value));
    formData.append('known_measurement_unit', knownMeasurement.unit);
  }

  const headers: Record<string, string> = {};
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/interfaces/${interfaceId}/upload`,
    {
      method: 'POST',
      headers,
      body: formData,
    }
  );

  const json: APIEnvelope<UploadResponseData> = await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function analyzeInterfaceImage(
  projectId: string,
  interfaceId: 'interface_a' | 'interface_b',
  projectToken?: string,
  provider?: string
): Promise<AnalysisResult> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const query = provider ? `?provider=${encodeURIComponent(provider)}` : '';
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/interfaces/${interfaceId}/analyze${query}`,
    {
      method: 'POST',
      headers,
    }
  );

  const json: APIEnvelope<AnalysisResult> = await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function snapScalePoint(
  projectId: string,
  interfaceId: 'interface_a' | 'interface_b',
  point: { x: number; y: number },
  projectToken?: string
): Promise<ScaleSnapResponse> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (projectToken) headers['X-Project-Token'] = projectToken;
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/interfaces/${interfaceId}/scale/snap`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({ point }),
    }
  );
  const json: APIEnvelope<ScaleSnapResponse> = await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function calibrateInterfaceScale(
  projectId: string,
  interfaceId: 'interface_a' | 'interface_b',
  calibration: TwoPointScaleCalibrationRequest,
  projectToken?: string
): Promise<Project> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (projectToken) headers['X-Project-Token'] = projectToken;
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/interfaces/${interfaceId}/scale/calibrate`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify(calibration),
    }
  );
  const json: APIEnvelope<Project> = await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function resetInterfaceScaleCalibration(
  projectId: string,
  interfaceId: 'interface_a' | 'interface_b',
  projectToken?: string
): Promise<Project> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (projectToken) headers['X-Project-Token'] = projectToken;
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/interfaces/${interfaceId}/scale/calibration`,
    { method: 'DELETE', headers }
  );
  const json: APIEnvelope<Project> = await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function patchInterface(
  projectId: string,
  interfaceId: 'interface_a' | 'interface_b',
  patch: InterfacePatchRequest,
  projectToken?: string
): Promise<Project> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/interfaces/${interfaceId}`,
    {
      method: 'PATCH',
      headers,
      body: JSON.stringify(patch),
    }
  );

  const json: APIEnvelope<Project> = await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function validateConnectionConfig(
  projectId: string,
  connection: {
    mode: string;
    length_mm: number;
    offset_x_mm: number;
    offset_y_mm: number;
    angle_deg: number;
    extension_a_mm?: number;
    extension_b_mm?: number;
  },
  manufacturing: {
    process: string;
    material: string;
    wall_thickness_mm: number;
    clearance_a_mm: number;
    clearance_b_mm: number;
  },
  projectToken?: string
): Promise<import('../types/schema').ConnectionValidationResult> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/validate-connection`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({ connection, manufacturing }),
    }
  );

  const json: APIEnvelope<import('../types/schema').ConnectionValidationResult> =
    await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function updateConnectionConfig(
  projectId: string,
  connection: {
    mode: string;
    length_mm: number;
    offset_x_mm: number;
    offset_y_mm: number;
    angle_deg: number;
    extension_a_mm?: number;
    extension_b_mm?: number;
  },
  manufacturing: {
    process: string;
    material: string;
    wall_thickness_mm: number;
    clearance_a_mm: number;
    clearance_b_mm: number;
  },
  projectToken?: string
): Promise<Project> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/connection-config`,
    {
      method: 'PUT',
      headers,
      body: JSON.stringify({ connection, manufacturing }),
    }
  );

  const json: APIEnvelope<Project> = await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function fetchKclReadiness(
  projectId: string,
  projectToken?: string
): Promise<import('../types/schema').ConnectionValidationResult> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/kcl/readiness`,
    {
      headers,
    }
  );

  const json: APIEnvelope<import('../types/schema').ConnectionValidationResult> =
    await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function compileKcl(
  projectId: string,
  projectToken?: string
): Promise<import('../types/schema').KCLCompileResult> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/kcl/compile`,
    {
      method: 'POST',
      headers,
    }
  );

  const json: APIEnvelope<import('../types/schema').KCLCompileResult> =
    await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

/**
  * 3D Model Generation API Client Functions per ADR-006 & S5.5
  */
export async function startGeneration(
  projectId: string,
  projectToken?: string,
  mockScenario: import('../types/schema').MockScenario = 'success'
): Promise<import('../types/schema').GenerationJob> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/generation/start`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({ mock_scenario: mockScenario }),
    }
  );

  const json: APIEnvelope<import('../types/schema').GenerationJob> =
    await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function fetchGenerationStatus(
  projectId: string,
  jobId: string,
  projectToken?: string
): Promise<import('../types/schema').GenerationJob> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/generation/${jobId}`,
    {
      headers,
    }
  );

  const json: APIEnvelope<import('../types/schema').GenerationJob> =
    await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function cancelGeneration(
  projectId: string,
  jobId: string,
  projectToken?: string
): Promise<import('../types/schema').GenerationJob> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/generation/${jobId}/cancel`,
    {
      method: 'POST',
      headers,
    }
  );

  const json: APIEnvelope<import('../types/schema').GenerationJob> =
    await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function retryGeneration(
  projectId: string,
  jobId: string,
  projectToken?: string,
  mockScenario: import('../types/schema').MockScenario = 'success'
): Promise<import('../types/schema').GenerationJob> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/generation/${jobId}/retry`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({ mock_scenario: mockScenario }),
    }
  );

  const json: APIEnvelope<import('../types/schema').GenerationJob> =
    await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function fetchPreviewMetadata(
  projectId: string,
  jobId: string,
  projectToken?: string
): Promise<import('../types/schema').PreviewMetadata> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/generation/${jobId}/preview`,
    {
      headers,
    }
  );

  const json: APIEnvelope<import('../types/schema').PreviewMetadata> =
    await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

/**
  * File Format Export API Functions per S8
  */
export async function generateExports(
  projectId: string,
  formats: string[] = ['stl', 'step', 'kcl'],
  projectToken?: string,
  mockScenario?: string
): Promise<import('../types/schema').ExportStatusResponse> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/exports/generate`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({ formats, mock_scenario: mockScenario }),
    }
  );

  const json: APIEnvelope<import('../types/schema').ExportStatusResponse> =
    await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function fetchExportStatus(
  projectId: string,
  projectToken?: string
): Promise<import('../types/schema').ExportStatusResponse> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/exports/status`,
    {
      headers,
    }
  );

  const json: APIEnvelope<import('../types/schema').ExportStatusResponse> =
    await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function retryFormatExport(
  projectId: string,
  formatName: string,
  projectToken?: string
): Promise<import('../types/schema').ExportStatusResponse> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/exports/${formatName}/retry`,
    {
      method: 'POST',
      headers,
    }
  );

  const json: APIEnvelope<import('../types/schema').ExportStatusResponse> =
    await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export interface CurrentKclArtifact {
  text: string;
  artifact_ref: string;
  schema_revision: number;
  model_revision: number;
  kcl_hash: string;
}

export async function fetchCurrentKcl(
  projectId: string,
  projectToken?: string
): Promise<CurrentKclArtifact> {
  const headers: Record<string, string> = {};
  if (projectToken) headers['X-Project-Token'] = projectToken;
  const response = await fetch(`${BACKEND_BASE_URL}/api/projects/${projectId}/kcl`, { headers });
  const json: APIEnvelope<CurrentKclArtifact> = await response.json();
  if (!json.success) throw new Error(`[${json.error.id}] ${json.error.message}`);
  return json.data;
}
export function getExportDownloadUrl(
  projectId: string,
  formatName: string,
  projectToken?: string
): string {
  const tokenQuery = projectToken ? `?token=${encodeURIComponent(projectToken)}` : '';
  return `${BACKEND_BASE_URL}/api/projects/${projectId}/exports/${formatName}/download${tokenQuery}`;
}

/**
  * Returns a browser-accessible URL for the uploaded interface source image.
  * The project token is passed as a query parameter so <img src> can load it directly.
  */
export function getInterfaceImageUrl(
  projectId: string,
  interfaceId: 'interface_a' | 'interface_b',
  projectToken?: string
): string {
  const tokenQuery = projectToken ? `?token=${encodeURIComponent(projectToken)}` : '';
  return `${BACKEND_BASE_URL}/api/projects/${projectId}/interfaces/${interfaceId}/image${tokenQuery}`;
}


export function getInterfaceArtifactUrl(
  projectId: string,
  interfaceId: 'interface_a' | 'interface_b',
  artifact: 'analysis_image' | 'cleaned_image' | 'trace_svg' | 'overlay_svg',
  projectToken?: string
): string {
  const tokenQuery = projectToken ? `?token=${encodeURIComponent(projectToken)}` : '';
  return `${BACKEND_BASE_URL}/api/projects/${projectId}/interfaces/${interfaceId}/${artifact}${tokenQuery}`;
}

export async function proposeRevision(
  projectId: string,
  prompt: string,
  projectToken?: string,
  provider?: string
): Promise<import('../types/schema').AgentProposalResult> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/revision/propose`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({ prompt, provider }),
    }
  );

  const json: APIEnvelope<import('../types/schema').AgentProposalResult> = await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}

export async function confirmRevision(
  projectId: string,
  changes: import('../types/schema').ParameterChange[],
  projectToken?: string,
  mockScenario: string = 'success'
): Promise<import('../types/schema').RevisionConfirmResponse> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/revision/confirm?mock_scenario=${encodeURIComponent(mockScenario)}`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({ changes }),
    }
  );

  const json: APIEnvelope<import('../types/schema').RevisionConfirmResponse> = await response.json();
  if (!json.success) {
    throw new Error(`[${json.error.id}] ${json.error.message}`);
  }
  return json.data;
}
