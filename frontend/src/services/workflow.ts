import { Project } from '../types/schema';

export const STEP_ORDER: Record<string, number> = {
  '/': 0,
  '/step1': 1,
  '/step1/analysis': 2,
  '/step2': 3,
  '/step2/analysis': 4,
  '/step3': 5,
  '/step4': 6,
  '/step5': 7,
};

export function getEarliestIncompleteStep(project: Project | null): string {
  if (!project) return '/';

  // Step 1 Check
  if (!project.interface_a?.approved) {
    if (!project.interface_a?.source_image_ref) {
      return '/step1';
    }
    return '/step1/analysis';
  }

  // Step 2 Check
  if (!project.interface_b?.approved) {
    if (!project.interface_b?.source_image_ref) {
      return '/step2';
    }
    return '/step2/analysis';
  }

  // Step 3 Check: Connection configured
  const hasConnection = (project.connection?.length_mm ?? 0) > 0;
  if (!hasConnection) {
    return '/step3';
  }

  // Step 4 Check: Model generation completed
  const hasModel =
    project.current_model_revision !== null && project.current_model_revision !== undefined ||
    project.last_known_good_model_revision !== null && project.last_known_good_model_revision !== undefined ||
    ((project.model_revisions?.length ?? 0) > 0);

  if (!hasModel && project.state !== 'model_current' && project.state !== 'model_stale') {
    return '/step4';
  }

  // Step 5: Ready
  return '/step5';
}
