import { DEMO_MODE } from './lib/demoMode'
import { localTriage } from './lib/localTriage'
import type { Draft, GateConfig, Health, HoldoutMetrics, Pred, Precedent, TriageResponse } from './types'

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || 'http://localhost:8000'
export const OFFLINE = false
const TIMEOUT_MS = 60_000

export type ApiErrorKind = 'timeout' | 'network' | 'validation' | 'server' | 'not_found'

export class ApiError extends Error {
  kind: ApiErrorKind
  status?: number
  constructor(kind: ApiErrorKind, message: string, status?: number) {
    super(message)
    this.kind = kind
    this.status = status
  }
}

/**
 * Turn an error body into one readable sentence. FastAPI's 422 `detail` is a list of
 * { loc, msg } objects; never show raw JSON to the agent.
 */
function formatDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const parts = detail.map((d) => {
      const e = (d ?? {}) as { loc?: unknown[]; msg?: unknown }
      // loc is e.g. ["body", "body"]: drop the leading "body" (the request body), keep the field name.
      const loc = Array.isArray(e.loc) ? e.loc : []
      const field = (loc[0] === 'body' && loc.length > 1 ? loc.slice(1) : loc).join('.')
      const msg = typeof e.msg === 'string' ? e.msg.replace(/^Value error, /, '') : 'invalid value'
      return field ? `${field === 'body' ? 'message' : field}: ${msg}` : msg
    })
    return parts.join('; ') || 'invalid input'
  }
  return 'unexpected response'
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS)
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw new ApiError('timeout', 'The triage API took longer than 60 s to answer. Your text is kept: try again.')
    throw new ApiError('network', `The triage API at ${BASE} is not reachable. Your text is kept: start the API and try again, or switch on "Demo data" in the top bar.`)
  } finally {
    clearTimeout(timer)
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = formatDetail(body.detail ?? body)
    } catch {
      /* non-JSON error body */
    }
    if (res.status === 422) throw new ApiError('validation', `The ticket was not accepted: ${detail}`, 422)
    if (res.status === 404) throw new ApiError('not_found', detail, 404)
    throw new ApiError('server', `Server error ${res.status}: ${detail}`, res.status)
  }
  return (await res.json()) as T
}

const EMPTY_PRED = { label: 'unknown', confidence: 0, probs: {} }

/**
 * Fill safe defaults for any field the backend omitted, so the UI never
 * crashes on a partial response (task C.4 "States"). Field names are the
 * contract's; nothing is renamed.
 */
export function normalizeTriage(raw: Partial<TriageResponse> & Record<string, unknown>): TriageResponse {
  const r = raw ?? {}
  const p = (r.predictions ?? {}) as Partial<TriageResponse['predictions']>
  const pred = (x?: Partial<Pred>): Pred => ({ ...EMPTY_PRED, ...x, probs: x?.probs ?? {} })
  const esc = (r.escalation ?? {}) as Partial<TriageResponse['escalation']>
  const lat = (r.latency_ms ?? {}) as Partial<TriageResponse['latency_ms']>
  const counts = { EMAIL: 0, PHONE: 0, IP: 0, IBAN: 0, CARD: 0, ACCOUNT: 0, ...r.pii?.counts }
  return {
    request_id: r.request_id ?? crypto.randomUUID(),
    mock: r.mock ?? false,
    input: { subject: null, body_chars: 0, truncated: false, ...(r.input as Partial<TriageResponse['input']>) },
    language: { code: 'en', confidence: 0, reply_language: 'en', ...(r.language as Partial<TriageResponse['language']>) },
    pii: { masked: r.pii?.masked ?? Object.values(counts).some((n) => n > 0), counts },
    predictions: { type: pred(p.type), queue: pred(p.queue), priority: pred(p.priority) },
    escalation: {
      status: esc.status ?? 'ESCALATE',
      route: esc.route === undefined ? (esc.status === 'AUTO_DRAFT' ? null : 'HUMAN_REVIEW') : esc.route,
      badge: esc.badge ?? (esc.status === 'AUTO_DRAFT' ? 'Auto-Draft Ready' : 'Human Review Required'),
      reasons: Array.isArray(esc.reasons) ? esc.reasons : [],
    },
    precedents: (Array.isArray(r.precedents) ? (r.precedents as Partial<Precedent>[]) : []).filter((x): x is Partial<Precedent> & { ticket_id: string } => typeof x?.ticket_id === 'string').map((x) => {
      const full = { subject: '', body_snippet: '', answer_snippet: '', answer: '', language: 'en', type: '', queue: '', priority: '', similarity: 0, ...x }
      return { ...full, answer: full.answer || full.answer_snippet, tags: Array.isArray(x.tags) ? x.tags : [] }
    }),
    draft: r.draft ? { status: 'OK', text: '', language: 'en', for_human_review: true, model: '', ...(r.draft as Partial<Draft>), cited_ids: Array.isArray(r.draft.cited_ids) ? r.draft.cited_ids : [] } : null,
    burst: { active: false, cluster_size: 1, window_minutes: 15, label: null, request_ids: [], ...(r.burst as Partial<TriageResponse['burst']>) },
    latency_ms: { pii: 0, language: 0, classify: 0, retrieve: 0, gate: 0, generate: 0, total: 0, ...lat },
  }
}

export interface TriageResult {
  data: TriageResponse
  /** true only in demo mode: the result is the in-browser heuristic (flagged `mock: true`). */
  fallback: boolean
}

/** POST /triage. Network, timeout and validation errors are surfaced to the caller. */
export async function triage(subject: string | null, body: string): Promise<TriageResult> {
  if (DEMO_MODE) return { data: await localTriage(subject, body), fallback: true }
  const raw = await request<TriageResponse>('/triage', {
    method: 'POST',
    body: JSON.stringify({ subject: subject || null, body }),
  })
  return { data: normalizeTriage(raw as TriageResponse & Record<string, unknown>), fallback: false }
}

export const health = () => request<Health>('/health')
export const config = () => request<GateConfig>('/config')
export const metrics = () => request<HoldoutMetrics>('/metrics')
export const resetBurst = () => request<{ ok: boolean }>('/burst/reset', { method: 'POST' })
