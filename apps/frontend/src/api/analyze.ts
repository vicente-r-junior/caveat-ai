/**
 * Analyze API — typed wrapper for POST /api/analyze/{document_id}.
 *
 * Types mirror exactly `AnalyzeResponse` / `FindingOut` / `ClientSummaryOut`
 * in `apps/backend/caveat/routers/analyze.py`.
 *
 * Note on timeouts: the backend can take 30–180s on E4B (model cold-start
 * + actual inference). `apiPost` uses `fetch` which has no default timeout,
 * so the request will simply remain in flight until the server responds.
 * The Processing screen displays a timer-driven UI in parallel.
 */

import { apiPost } from './client';

export type AnalyzeOptions = {
  /**
   * Optional AbortSignal — when its `aborted` flag flips, the underlying
   * fetch is aborted and the promise rejects with a DOMException named
   * `'AbortError'`. Callers should swallow that rejection silently
   * (StrictMode double-mount, unmount during fetch, etc.).
   */
  signal?: AbortSignal;
};

export type Severity = 'high' | 'medium' | 'low' | 'missing';

/**
 * One parsed contract section as surfaced by the backend's parse stage.
 * Mirrors `SourceSection` in `apps/backend/caveat/routers/analyze.py`.
 *
 * `body` is the raw text slice from `char_start` (inclusive) to `char_end`
 * (exclusive) of the canonical document text; the Source tab renders it
 * verbatim and overlays `<mark>` highlights using `SourceOffset` ranges.
 */
export type SourceSection = {
  idx: number;
  number: string;
  title: string;
  body: string;
  char_start: number;
  char_end: number;
  page: number;
};

/**
 * The location of a finding's quote inside the parsed source text, produced
 * by the `map_finding_offsets` pipeline stage. Mirrors `SourceOffset` in
 * `apps/backend/caveat/routers/analyze.py`.
 *
 * `start`/`end` are absolute character offsets into the canonical document
 * text (matching `SourceSection.char_start`/`char_end`'s coordinate system).
 * `section_index` is the `SourceSection.idx` of the section that contains
 * `start`. Always `null` (never `undefined`) when the offset stage failed
 * to locate the quote — Constitution VI: honest miss over silent miss.
 */
export type SourceOffset = {
  section_index: number;
  start: number;
  end: number;
};

export type Finding = {
  severity: Severity;
  title: string;
  quote: string;
  explanation: string;
  redline: string;
  /**
   * Where this finding's `quote` lives in the source document, or `null`
   * when the offset stage could not locate it (in which case a Constitution
   * VI warning is appended to `AnalyzeResponse.warnings`). Never `undefined`.
   */
  source_offset: SourceOffset | null;
};

export type ClientSummary = {
  what_this_contract_is: string;
  what_youre_committing_to: string;
  biggest_risks: string[];
  recommendation: string;
  disclaimer: string;
};

export type AnalyzeResponse = {
  document_id: string;
  contract_type: string | null;
  findings: Finding[];
  client_summary: ClientSummary;
  warnings: string[];
  elapsed_seconds: number;
  /**
   * The full parsed contract, section by section, in document order. The
   * Source tab renders these directly. Always present — even on the honest
   * empty path (`findings=[]`), `source_sections` is populated so the
   * lawyer can still read the contract.
   */
  source_sections: SourceSection[];
};

/**
 * Kick off the full pipeline against a previously uploaded document.
 *
 * The backend route is `/api/analyze/{document_id}`; `apiPost` prepends
 * `/api`, so we pass `/analyze/{id}`.
 *
 * When `options.signal` is provided and fires, the underlying fetch is
 * aborted. The promise then rejects with `DOMException('AbortError')`.
 */
export function analyzeDocument(
  documentId: string,
  options?: AnalyzeOptions,
): Promise<AnalyzeResponse> {
  return apiPost<AnalyzeResponse>(`/analyze/${documentId}`, {}, options);
}
