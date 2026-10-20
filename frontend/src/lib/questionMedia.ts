/**
 * Task 1 — maps an upload's backend-classified `file_type`
 * (image/audio/video/document) to a question `media_type`.
 *
 * Before Task 1 the admin question form attached every uploaded file
 * with media_type "image", so an uploaded audio file reached students as
 * a broken image. Types question media does not allow (e.g. a PDF
 * "document") keep the previous "image" default, unchanged.
 */
export function mediaTypeForUpload(fileType: string): string {
  return fileType === "audio" || fileType === "video" || fileType === "image" ? fileType : "image";
}
