/**
 * Visual Snapshot helper (disabled in production to prevent canvas DOM lag)
 */
export async function captureAndSendSnapshot(_viewName = 'dashboard') {
  // No-op to prevent DOM lag and re-render glitching
  return;
}
