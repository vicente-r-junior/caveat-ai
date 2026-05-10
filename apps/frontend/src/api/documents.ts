/**
 * Documents API — typed wrappers for the upload-side endpoints.
 *
 * Field shapes mirror exactly the FastAPI response models in
 * `apps/backend/caveat/routers/documents.py`. Do NOT invent fields; if the
 * backend adds one, mirror it here in the same commit.
 *
 * Constitution I (local-only): all calls go through {@link apiGet} /
 * {@link apiPostFormData}, which refuse absolute URLs.
 */

import { apiGet, apiPostFormData } from './client';

export type DocumentSummary = {
  id: string;
  filename: string;
  contract_type: string | null;
  page_count: number;
  created_at: string;
};

export type UploadedDocument = {
  document_id: string;
  filename: string;
  page_count: number;
  contract_type: string | null;
};

/** GET /api/documents/ — metadata-only list of every stored PDF. */
export function listDocuments(): Promise<DocumentSummary[]> {
  return apiGet<DocumentSummary[]>('/documents/');
}

/**
 * POST /api/documents/ — upload a PDF.
 *
 * The form field name `file` matches the FastAPI handler signature
 * (`file: UploadFile = File(...)`); changing it would 422.
 */
export function uploadDocument(file: File): Promise<UploadedDocument> {
  const form = new FormData();
  form.append('file', file);
  return apiPostFormData<UploadedDocument>('/documents/', form);
}
