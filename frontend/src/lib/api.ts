// API contract types + client. Matches spec/api.md exactly.
// Same-origin: the built frontend is served at /app/ and the API lives at the
// same origin root, so all fetches use root-relative absolute paths.

export type ModelId = 'gemini-3.5-flash' | 'gemini-3.1-flash-lite'

export const MODELS: { id: ModelId; label: string }[] = [
  { id: 'gemini-3.5-flash', label: 'Flash 3.5 — higher quality' },
  { id: 'gemini-3.1-flash-lite', label: 'Flash Lite — fastest / cheapest' },
]

export const DEFAULT_MODEL: ModelId = 'gemini-3.5-flash'

export interface RepairAttempt {
  attempt: number
  error: string
  change_summary: string
}

export interface TokenUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export type RunStatus = 'completed' | 'failed'

export interface RunData {
  run_id: string
  part_id: string
  version_number: number
  status: RunStatus
  generated_code: string
  repair_attempts: RepairAttempt[]
  safety_violation: string | null
  token_usage: TokenUsage | null
  cost_usd: number | null
  stl_url: string | null
  step_url: string | null
  code_url: string | null
}

interface Envelope<T> {
  data: T | null
  error: string | null
}

interface ErrorDetail {
  detail?: { code?: string; message?: string }
}

// Raised when the pipeline runs but fails (HTTP 200, status:"failed").
// Distinct from a network error so the UI can show an amber panel, not a red one.
export class ApiError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

export interface GenerateRequest {
  prompt: string
  model_id: ModelId
  mode: 'generate'
}

/**
 * POST /runs — generate a part. Resolves with RunData for BOTH completed and
 * failed pipeline runs (the caller inspects `status`). Throws ApiError for HTTP
 * 4xx/5xx (validation / provider / internal). A thrown TypeError from fetch
 * (server unreachable) propagates so the caller can show the network banner.
 */
export async function generateRun(req: GenerateRequest): Promise<RunData> {
  const res = await fetch('/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })

  let body: (Envelope<RunData> & ErrorDetail) | null = null
  try {
    body = await res.json()
  } catch {
    body = null
  }

  if (!res.ok) {
    const message =
      body?.detail?.message ??
      body?.error ??
      `Request failed (${res.status})`
    throw new ApiError(message)
  }

  const data = body?.data
  if (!data) {
    throw new ApiError('Malformed response from server (no data field).')
  }
  return data
}
