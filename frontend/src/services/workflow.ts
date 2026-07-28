import { Project } from '../types/schema';

type InterfaceId = 'interface_a' | 'interface_b';

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

export function getInterfaceStepPath(
  project: Project | null,
  interfaceId: InterfaceId
): string {
  const uploadPath = interfaceId === 'interface_b' ? '/step2' : '/step1';
  const reviewPath = interfaceId === 'interface_b' ? '/step2/analysis' : '/step1/analysis';
  const interfaceData = interfaceId === 'interface_b' ? project?.interface_b : project?.interface_a;

  if (!interfaceData) return uploadPath;

  if (interfaceData.approved || interfaceData.source_image_ref) {
    return reviewPath;
  }

  return uploadPath;
}
export function getEarliestIncompleteStep(project: Project | null): string {
  if (!project) return '/';

  // Step 1 Check
  if (!project.interface_a?.approved) {
    return getInterfaceStepPath(project, 'interface_a');
  }

  // Step 2 Check
  if (!project.interface_b?.approved) {
    return getInterfaceStepPath(project, 'interface_b');
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

