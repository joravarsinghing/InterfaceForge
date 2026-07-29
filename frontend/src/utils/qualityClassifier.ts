// Input Quality Classification Helper

export type InputQualityStatus =
  | 'recommended'
  | 'usable_with_review'
  | 'manual_cleanup_likely'
  | 'unsupported'
  | null;

/**
  * Lightweight heuristic classifier for uploaded image quality.
  *
  * Client-side heuristic pre-upload signal.
  * The authoritative analysis result comes from the backend GeminiAnalysisProvider.
  */
export function classifyInputQuality(file: File): InputQualityStatus {
  if (!file) return null;

  const name = file.name.toLowerCase();
  const sizeBytes = file.size;

  // Unsupported: very small files are likely corrupted/empty or a screenshot thumbnail
  if (sizeBytes < 500) return 'unsupported';

  // Heuristic signals from filename conventions
  const hasAnnotationKeyword =
    /dim(ension)?s?|dwg|drawing|cad|technical|annotated|measured|blueprint/i.test(name);
  const hasScanKeyword = /scan|photo|phone|selfie|angled/i.test(name);
  const hasCleanKeyword = /cross.?sec|profile|section|clean|shaded|filled/i.test(name);

  if (hasScanKeyword) return 'unsupported';
  if (hasAnnotationKeyword && !hasCleanKeyword) return 'manual_cleanup_likely';
  if (hasCleanKeyword) return 'recommended';

  // Default for images without clear filename signals - usable but unconfirmed
  return 'usable_with_review';
}

export function qualityStatusLabel(status: InputQualityStatus): string {
  switch (status) {
    case 'recommended':
      return '[OK] Recommended input';
    case 'usable_with_review':
      return '[WARNING] Usable with review';
    case 'manual_cleanup_likely':
      return '[WARNING] Manual cleanup likely';
    case 'unsupported':
      return '[NO] Unsupported';
    default:
      return '';
  }
}

export function qualityStatusDescription(status: InputQualityStatus): string {
  switch (status) {
    case 'recommended':
      return 'Clean cross-section profile detected. This is the preferred input format.';
    case 'usable_with_review':
      return 'Image may work, but review the traced profile carefully before approving.';
    case 'manual_cleanup_likely':
      return 'Dimensioned drawings introduce false edges. Manual cleanup of the traced profile may be required.';
    case 'unsupported':
      return 'This image type is not supported. Upload a clean cross-section profile instead.';
    default:
      return '';
  }
}

export function qualityStatusClass(status: InputQualityStatus): string {
  switch (status) {
    case 'recommended':
      return 'quality-badge quality-recommended';
    case 'usable_with_review':
      return 'quality-badge quality-usable';
    case 'manual_cleanup_likely':
      return 'quality-badge quality-cleanup';
    case 'unsupported':
      return 'quality-badge quality-unsupported';
    default:
      return 'quality-badge';
  }
}
