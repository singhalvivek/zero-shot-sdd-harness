// API client + SSE parsing for the Analysis Console.
// Same-origin relative paths: FastAPI serves both the API and the static /app/ export.

export interface Column {
  name: string
  dtype: string
}

export interface DatasetResult {
  dataset_id: string
  df_name: string
  row_count: number
  columns: Column[]
  session_id: string
}

export interface Usage {
  prompt_tokens: number
  completion_tokens: number
}

// SSE events emitted by POST /sessions/{id}/ask
export type AskEvent =
  | { type: 'token'; text: string }
  | { type: 'usage'; prompt_tokens: number; completion_tokens: number }
  | { type: 'done'; run_id?: string; status?: string }
  | { type: 'error'; message: string }
  | { type: 'clarify'; question: string }
  | { type: 'suggestions'; items: string[] }

interface ApiEnvelope<T> {
  ok: boolean
  data?: T
  detail?: { message?: string }
}

/** Upload a CSV. Returns the profiled dataset record. Throws Error with a user-facing message on failure. */
export async function uploadDataset(file: File, sessionId?: string): Promise<DatasetResult> {
  const form = new FormData()
  form.append('file', file)
  if (sessionId) form.append('session_id', sessionId)

  let res: Response
  try {
    res = await fetch('/datasets', { method: 'POST', body: form })
  } catch {
    throw new Error('Network error — is the server running?')
  }

  let body: ApiEnvelope<DatasetResult> | null = null
  try {
    body = await res.json()
  } catch {
    /* non-JSON body */
  }

  if (!res.ok || !body?.ok || !body.data) {
    throw new Error('Could not read this file — is it a valid CSV?')
  }
  return body.data
}

/**
 * Ask a question against a session and stream the answer.
 * Consumes the text/event-stream via fetch + ReadableStream (EventSource cannot POST).
 * Invokes `onEvent` for each parsed SSE event.
 */
export async function askQuestion(
  sessionId: string,
  question: string,
  onEvent: (event: AskEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(`/sessions/${sessionId}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ question }),
      signal,
    })
  } catch {
    throw new Error('Network error — is the server running?')
  }

  if (!res.ok || !res.body) {
    let msg = `Request failed (${res.status})`
    try {
      const j = await res.json()
      if (j?.detail?.message) msg = j.detail.message
    } catch {
      /* ignore */
    }
    onEvent({ type: 'error', message: msg })
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE frames are separated by a blank line.
    let sep: number
    while ((sep = indexOfFrameBoundary(buffer)) !== -1) {
      const rawFrame = buffer.slice(0, sep)
      buffer = buffer.slice(sep).replace(/^(\r?\n){2}/, '')
      const evt = parseFrame(rawFrame)
      if (evt) onEvent(evt)
    }
  }

  // Flush any trailing frame without a terminating blank line.
  const tail = parseFrame(buffer)
  if (tail) onEvent(tail)
}

function indexOfFrameBoundary(buffer: string): number {
  const a = buffer.indexOf('\n\n')
  const b = buffer.indexOf('\r\n\r\n')
  if (a === -1) return b
  if (b === -1) return a
  return Math.min(a, b)
}

/** Parse one SSE frame ("event: x\n data: {...}") into a typed AskEvent. */
function parseFrame(frame: string): AskEvent | null {
  let eventName = 'message'
  const dataLines: string[] = []
  for (const line of frame.split(/\r?\n/)) {
    if (line.startsWith('event:')) eventName = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (dataLines.length === 0) return null

  let payload: Record<string, unknown> = {}
  try {
    payload = JSON.parse(dataLines.join('\n'))
  } catch {
    // token streams may send raw text rather than JSON
    if (eventName === 'token') return { type: 'token', text: dataLines.join('\n') }
    return null
  }

  switch (eventName) {
    case 'token':
      return { type: 'token', text: String(payload.text ?? '') }
    case 'usage':
      return {
        type: 'usage',
        prompt_tokens: Number(payload.prompt_tokens ?? 0),
        completion_tokens: Number(payload.completion_tokens ?? 0),
      }
    case 'done':
      return { type: 'done', run_id: payload.run_id as string, status: payload.status as string }
    case 'error':
      return { type: 'error', message: String(payload.message ?? 'The agent failed. Please try again.') }
    case 'clarify':
      return { type: 'clarify', question: String(payload.question ?? '') }
    case 'suggestions':
      return { type: 'suggestions', items: (payload.items as string[]) ?? [] }
    default:
      return null
  }
}
