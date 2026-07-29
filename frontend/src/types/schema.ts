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

export type ProviderMode = 'mock' | 'live';

export type FitMode = 'fit_over' | 'fit_inside';

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

export interface ScaleCalibration {
  source: 'drawing_dimension' | 'user_calibration' | 'inferred' | string;
  method?: 'known_measurement' | 'two_point_trace' | string;
  reference_dimension?: string | null;
  point_a?: Point2D | null;
  point_b?: Point2D | null;
  pixel_distance: number;
  real_distance_mm: number;
  scale_factor?: number;
  confidence: number;
  confirmed: boolean;
}

export interface ScaleSnapResponse {
  point: Point2D;
  distance_px: number;
  feature_id: string;
}

export interface TwoPointScaleCalibrationRequest {
  point_a: Point2D;
  point_b: Point2D;
  real_distance_mm: number;
  confirmed: boolean;
}

export interface TracedContour {
  id?: string;
  points: Point2D[];
  is_closed: boolean;
  classification?: 'hole' | 'cavity' | 'slot' | 'outer_contour' | 'unknown';
  decision?: 'include' | 'ignore' | 'unsure';
  provenance: string; // 'analysis' | 'user_edited'
  confidence: number;
  point_count: number;
}

export interface Dimension {
  id: string;
  label: string;
  value: number;
  unit: string;
  provenance: DimensionProvenance;
  confidence: number;
  critical: boolean;
  feature_ref?: string | null;
  source_annotation?: string | null;
  consistency_state?: 'valid' | 'conflict' | 'unmapped' | 'recalculated' | string;
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
  fit_mode?: FitMode;
  validation: ProfileValidation;
  approved: boolean;
  approved_at?: string | null;
  // S10.3 & S10.4 traced profile fields
  traced_outer_contour?: TracedContour | null;
  traced_hole_contours?: TracedContour[];
  scale_calibration?: ScaleCalibration | null;
  verification_status?: 'exact_trace_ready' | 'trace_requires_correction' | 'simplified_envelope_only' | 'unsupported_insufficient_image' | string;
  primitive_fallback_active?: boolean;
  primitive_fallback_label?: string | null;
  analysis_provider_name?: string | null;
  generation_unsupported?: boolean;
  generation_unsupported_reason?: string | null;
  cleaned_image_ref?: string | null;
  analysis_image_ref?: string | null;
  analysis_image_width?: number | null;
  analysis_image_height?: number | null;
  trace_svg_ref?: string | null;
  overlay_svg_ref?: string | null;
  raw_outer_point_count?: number | null;
  simplified_outer_point_count?: number | null;
  inner_contour_count?: number | null;
}

export interface InterfacePatchRequest {
  source_image_ref?: string | null;
  profile_type?: string;
  dimensions?: Dimension[];
  fit_mode?: FitMode;
  traced_outer_contour?: TracedContour | null;
  traced_hole_contours?: TracedContour[];
  scale_calibration?: ScaleCalibration | null;
  verification_status?: string | null;
  primitive_fallback_active?: boolean;
  primitive_fallback_label?: string | null;
  approved?: boolean;
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
  display_name?: string;
  provider_mode?: ProviderMode;
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

export interface ProviderModeStatus {
  selected_mode: ProviderMode;
  effective_mode: ProviderMode;
  live_available: boolean;
  engine_provider: string;
  export_provider: string;
  analysis_provider: string;
  agent_provider: string;
  message: string;
}

export interface ProviderModeUpdateResponse {
  project: Project;
  provider_status: ProviderModeStatus;
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
  input_type?: string;
  profile_type: ProfileType;
  candidate_points: Point2D[];
  candidate_dimensions: Dimension[];
  provenance: DimensionProvenance;
  confidence: number;
  warnings: string[];
  rejection_reasons: string[];
  success: boolean;
  analysis_provider_name?: string | null; // S10.3: 'mock', 'gemini', etc.
  traced_outer_contour?: TracedContour | null;
  traced_hole_contours?: TracedContour[];
  scale_calibration?: ScaleCalibration | null;
  is_complex?: boolean;
  complex_reason?: string | null;
  cleaned_image_ref?: string | null;
  analysis_image_ref?: string | null;
  analysis_image_width?: number | null;
  analysis_image_height?: number | null;
  trace_svg_ref?: string | null;
  overlay_svg_ref?: string | null;
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
