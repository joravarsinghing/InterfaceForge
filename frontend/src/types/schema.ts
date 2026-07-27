/**
 * TypeScript contract definitions matching Backend Canonical Design Schema (ADR-001, ADR-005)
 */

export type WorkflowState =
  | 'new'
  | 'interface_a_uploaded'
  | 'interface_a_review_required'
  | 'interface_a_approved'
  | 'interface_b_uploaded'
  | 'interface_b_review_required'
  | 'interfaces_approved'
  | 'connection_configured'
  | 'generation_in_progress'
  | 'generation_failed'
  | 'model_current'
  | 'model_stale'
  | 'revision_draft'
  | 'export_in_progress'
  | 'export_ready';

export type ProfileType =
  | 'circle'
  | 'rectangle'
  | 'rounded_rectangle'
  | 'traced_closed';

export type DimensionProvenance =
  | 'user_entered'
  | 'image_extracted'
  | 'system_inferred'
  | 'unresolved';

export type ConnectionMode = 'coaxial' | 'offset' | 'angled';

export type ManufacturingProcess = 'fdm' | 'sla' | 'cnc';

export type ModelRevisionStatus =
  | 'draft'
  | 'generating'
  | 'current'
  | 'stale'
  | 'failed'
  | 'superseded';

export interface Point2D {
  x: number;
  y: number;
}

export interface Dimension {
  id: string;
  label: string;
  value: number;
  unit: string;
  provenance: DimensionProvenance;
  confidence: number;
  critical: boolean;
}

export interface ProfileValidation {
  is_closed: boolean;
  self_intersects: boolean;
  warnings: string[];
}

export interface InterfaceDefinition {
  id: string;
  source_image_ref?: string | null;
  profile_type: ProfileType;
  profile_points: Point2D[];
  center: Point2D;
  dimensions: Dimension[];
  validation: ProfileValidation;
  approved: boolean;
  approved_at?: string | null;
}

export interface Connection {
  mode: ConnectionMode;
  length_mm: number;
  offset_x_mm: number;
  offset_y_mm: number;
  angle_deg: number;
}

export interface Manufacturing {
  process: ManufacturingProcess;
  material: string;
  wall_thickness_mm: number;
  clearance_a_mm: number;
  clearance_b_mm: number;
}

export interface ExportReferences {
  stl?: string | null;
  step?: string | null;
  kcl?: string | null;
}

export type ExportFormatStatus = 'not_started' | 'preparing' | 'ready' | 'failed';

export interface FormatExportDetail {
  format: string;
  status: ExportFormatStatus;
  artifact_ref?: string | null;
  filename?: string | null;
  size_bytes?: number | null;
  error_id?: string | null;
  error_message?: string | null;
  updated_at?: string | null;
}

export interface ExportStatusResponse {
  project_id: string;
  model_revision: number;
  schema_revision: number;
  units: string;
  model_status: string;
  volume_cm3?: number | null;
  formats: Record<string, FormatExportDetail>;
}

export interface ModelRevision {
  model_revision: number;
  schema_revision: number;
  status: ModelRevisionStatus;
  kcl_artifact_ref?: string | null;
  preview_artifact_ref?: string | null;
  exports: ExportReferences;
  volume_cm3?: number | null;
  warnings: string[];
  generated_at: string;
}

export interface Project {
  project_id: string;
  project_token: string;
  schema_version: string;
  state: WorkflowState;
  created_at: string;
  updated_at: string;
  current_schema_revision: number;
  current_model_revision?: number | null;
  last_known_good_model_revision?: number | null;
  interface_a: InterfaceDefinition;
  interface_b: InterfaceDefinition;
  connection: Connection;
  manufacturing: Manufacturing;
  model_revisions: ModelRevision[];
}

export interface UploadResponseData {
  artifact_ref: string;
  original_filename: string;
  stored_filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
}

export interface AnalysisResult {
  profile_type: ProfileType;
  candidate_points: Point2D[];
  candidate_dimensions: Dimension[];
  provenance: DimensionProvenance;
  confidence: number;
  warnings: string[];
  rejection_reasons: string[];
  success: boolean;
}

export interface ValidationIssue {
  id: string;
  message: string;
  field?: string | null;
  recovery_steps: string[];
}

export interface ConnectionValidationResult {
  is_valid: boolean;
  blocking_errors: ValidationIssue[];
  warnings: ValidationIssue[];
  recommended_values: Record<string, number>;
}

export interface KCLCompileResult {
  success: boolean;
  kcl_code?: string | null;
  artifact_ref?: string | null;
  compiler_version: string;
  schema_revision: number;
  schema_version: string;
  kcl_hash?: string | null;
  preview_snippet?: string | null;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
}

export type JobStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancel_requested'
  | 'cancelled';

export type GenerationStage =
  | 'validating'
  | 'compiling'
  | 'executing'
  | 'rendering'
  | 'finalizing';

export type MockScenario =
  | 'success'
  | 'engine_validation_failure'
  | 'timeout'
  | 'malformed_response'
  | 'cancellation'
  | 'preview_failure';

export interface BoundingBox {
  x_mm: number;
  y_mm: number;
  z_mm: number;
}

export interface PreviewMetadata {
  preview_svg: string;
  bounding_box: BoundingBox;
  volume_cm3: number;
  facet_count: number;
  render_timestamp: string;
  is_mock: boolean;
}

export interface GenerationJob {
  job_id: string;
  project_id: string;
  model_revision: number;
  status: JobStatus;
  current_stage: GenerationStage;
  progress_percent: number;
  mock_scenario: MockScenario;
  error_id?: string | null;
  error_message?: string | null;
  recovery_steps: string[];
  preview_metadata?: PreviewMetadata | null;
  kcl_code_snippet?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}



// --- API Envelopes ---

export interface APISuccessEnvelope<T> {
  success: true;
  data: T;
}

export interface APIErrorDetails {
  id: string;
  message: string;
  details?: unknown;
  recovery_steps: string[];
}

export interface APIErrorEnvelope {
  success: false;
  error: APIErrorDetails;
}

export type APIEnvelope<T> = APISuccessEnvelope<T> | APIErrorEnvelope;

export interface ParameterChange {
  field: string;
  current_value: number;
  proposed_value: number;
  unit: string;
  reason: string;
}

export interface AgentProposalResult {
  changes: ParameterChange[];
  summary: string;
  is_valid: boolean;
  validation_errors: ValidationIssue[];
  validation_warnings: ValidationIssue[];
  raw_response?: string | null;
  provider_used?: string | null;
}

export interface RevisionConfirmResponse {
  project: Project;
  job: GenerationJob;
}


