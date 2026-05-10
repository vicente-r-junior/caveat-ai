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

export type Severity = 'high' | 'medium' | 'low' | 'missing';

export type Finding = {
  severity: Severity;
  title: string;
  quote: string;
  explanation: string;
  redline: string;
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
};

/**
 * Kick off the full pipeline against a previously uploaded document.
 *
 * The backend route is `/api/analyze/{document_id}`; `apiPost` prepends
 * `/api`, so we pass `/analyze/{id}`.
 */
export function analyzeDocument(documentId: string): Promise<AnalyzeResponse> {
  return apiPost<AnalyzeResponse>(`/analyze/${documentId}`, {});
}
