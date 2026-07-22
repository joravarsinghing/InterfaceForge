/**
 * Backend API Client Abstraction
 */

import type {
  AnalysisResult,
  APIEnvelope,
  Project,
  UploadResponseData,
} from '../types/schema';


export interface HealthResponse {
  service_name: string;
  status: string;
  environment: string;
  version: string;
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

/**
 * Project API client functions matching S3 contracts
 */
export async function createProject(): Promise<Project> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
  projectToken?: string
): Promise<UploadResponseData> {
  const formData = new FormData();
  formData.append('file', file);

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
  projectToken?: string
): Promise<AnalysisResult> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (projectToken) {
    headers['X-Project-Token'] = projectToken;
  }

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/projects/${projectId}/interfaces/${interfaceId}/analyze`,
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

export async function patchInterface(
  projectId: string,
  interfaceId: 'interface_a' | 'interface_b',
  patch: {
    profile_type?: string;
    dimensions?: unknown[];
    source_image_ref?: string | null;
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
  return json.data;
}



