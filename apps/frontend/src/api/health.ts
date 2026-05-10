/**
 * Health API — used by App shell to populate Topbar's status pill.
 *
 * The backend exposes `GET /api/health` and returns the configured Ollama
 * model name so the user can see at a glance which model is loaded.
 */

import { apiGet } from './client';

export type HealthResponse = {
  status: string;
  model: string;
};

export function getHealth(): Promise<HealthResponse> {
  return apiGet<HealthResponse>('/health');
}
