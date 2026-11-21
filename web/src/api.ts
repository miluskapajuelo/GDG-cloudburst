import type { GateConfig, Health, HoldoutMetrics, TriageResponse } from './types'
import { localTriage } from './lib/localTriage'

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || 'http://localhost:8000'
export const OFFLINE = import.meta.env.VITE_OFFLINE === '1'
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
    if ((e as Error).name === 'AbortError') throw new ApiError('timeout', 'The request took longer than 60 s.')
    throw new ApiError('network', 'The triage API is not reachable.')
  } finally {
    clearTimeout(timer)
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body)
    } catch {
      /* non-JSON error body */
    }
    if (res.status === 422) throw new ApiError('validation', `Invalid input: ${detail}`, 422)
    if (res.status === 404) throw new ApiError('not_found', detail, 404)
    throw new ApiError('server', `Server error ${res.status}: ${detail}`, res.status)
  }
  return (await res.json()) as T
}

export interface TriageResult {
  data: TriageResponse
  /** true when the API was unreachable and the in-browser fallback produced the result. */
  fallback: boolean
}

/**
 * POST /triage. If the API is offline, falls back to an in-browser heuristic
 * (clearly flagged `mock: true`) so a submitted ticket is never lost.
 * Validation errors (422) are surfaced, never masked by the fallback.
 */
export async function triage(subject: string | null, body: string): Promise<TriageResult> {
  if (OFFLINE) return { data: await localTriage(subject, body), fallback: true }
  try {
    const data = await request<TriageResponse>('/triage', {
      method: 'POST',
      body: JSON.stringify({ subject: subject || null, body }),
    })
    return { data, fallback: false }
  } catch (e) {
    if (e instanceof ApiError && (e.kind === 'network' || e.kind === 'timeout')) {
      return { data: await localTriage(subject, body), fallback: true }
    }
    throw e
  }
}

export const health = () => request<Health>('/health')
export const config = () => request<GateConfig>('/config')
export const metrics = () => request<HoldoutMetrics>('/metrics')
export const resetBurst = () => request<{ ok: boolean }>('/burst/reset', { method: 'POST' })
