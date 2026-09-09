/**
 * Sprint 27 Amendment — R2 Multipart Upload configuration. Mirrors
 * backend/app/modules/uploads/constants.py's values EXACTLY (verified
 * directly before writing this file) — these thresholds must stay in
 * sync across the language boundary since there is no backend
 * endpoint that exposes them at runtime. If the backend values ever
 * change, this file must be updated to match — the single source of
 * truth is the backend, this is a deliberate, documented mirror, not
 * an independent invention.
 */
export const MB = 1024 * 1024;
export const GB = 1024 * MB;

export const MAX_SIZE_VIDEO_BYTES = 2 * GB;
export const MULTIPART_THRESHOLD_BYTES = 100 * MB;
export const MULTIPART_PART_SIZE_BYTES = 20 * MB;
export const MAX_CONCURRENT_PARTS = 4;
export const MULTIPART_PART_RETRY_LIMIT = 3;
