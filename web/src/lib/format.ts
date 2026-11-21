import type { Priority, Ticket, WorkflowStatus } from '../types'

// ---- Confidence: bands + %, never a bare 0.73 (research §7 "calibrated confidence")
export type Band = 'High' | 'Medium' | 'Low'
/** Medium starts at the gate's T_CONF_* default (0.45), so "Low" lines up with LOW_CLASSIFIER_CONFIDENCE. */
export function band(conf: number): Band {
  if (conf >= 0.75) return 'High'
  if (conf >= 0.45) return 'Medium'
  return 'Low'
}
export const pct = (x: number, digits = 0) => `${(x * 100).toFixed(digits)}%`

// ---- SLA policy (UI assumption, configurable here in one place)
export const SLA_HOURS: Record<Priority, { first: number; resolve: number }> = {
  high: { first: 1, resolve: 8 },
  medium: { first: 8, resolve: 48 },
  low: { first: 24, resolve: 120 },
}

export type SlaState = 'ok' | 'at_risk' | 'breached' | 'paused' | 'met'
export interface Sla {
  state: SlaState
  kind: 'first_response' | 'resolution'
  dueAt: number
  remainingMs: number
}

export function hasAgentReply(t: Ticket): boolean {
  return t.messages.some((m) => m.role === 'agent' && !m.internal)
}

export function sla(t: Ticket, now: number): Sla {
  const created = Date.parse(t.created_at)
  const kind = hasAgentReply(t) ? 'resolution' : 'first_response'
  const hours = kind === 'first_response' ? SLA_HOURS[t.priority].first : SLA_HOURS[t.priority].resolve
  const dueAt = created + hours * 3_600_000
  const remainingMs = dueAt - now
  if (t.status === 'resolved' || t.status === 'closed') return { state: 'met', kind, dueAt, remainingMs }
  if (t.status === 'awaiting_customer') return { state: 'paused', kind, dueAt, remainingMs }
  if (remainingMs <= 0) return { state: 'breached', kind, dueAt, remainingMs }
  if (remainingMs < hours * 3_600_000 * 0.25) return { state: 'at_risk', kind, dueAt, remainingMs }
  return { state: 'ok', kind, dueAt, remainingMs }
}

export function duration(ms: number): string {
  const abs = Math.abs(ms)
  const m = Math.floor(abs / 60_000)
  const h = Math.floor(m / 60)
  const d = Math.floor(h / 24)
  if (d >= 1) return `${d}d ${h % 24}h`
  if (h >= 1) return `${h}h ${String(m % 60).padStart(2, '0')}m`
  return `${m}m`
}

const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
export function ago(iso: string, now: number): string {
  const diff = Date.parse(iso) - now
  const mins = Math.round(diff / 60_000)
  if (Math.abs(mins) < 1) return 'just now'
  if (Math.abs(mins) < 60) return rtf.format(mins, 'minute')
  const hrs = Math.round(mins / 60)
  if (Math.abs(hrs) < 24) return rtf.format(hrs, 'hour')
  return rtf.format(Math.round(hrs / 24), 'day')
}

/** Agent's local time zone; the customer's local time is shown separately where relevant. */
export const dateTime = (iso: string) =>
  new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso))
export const time = (iso: string) => new Intl.DateTimeFormat(undefined, { timeStyle: 'short' }).format(new Date(iso))

// ---- Labels
export const STATUS_LABEL: Record<WorkflowStatus, string> = {
  new: 'New',
  open: 'Open',
  awaiting_customer: 'Awaiting customer',
  resolved: 'Resolved',
  closed: 'Closed',
}
export const PRIORITY_LABEL: Record<Priority, string> = { high: 'High', medium: 'Medium', low: 'Low' }
export const PRIORITY_RANK: Record<Priority, number> = { high: 0, medium: 1, low: 2 }
export const LANG_LABEL: Record<string, string> = { en: 'English', de: 'German' }

/** Plain-language explanation for each gate reason code (docs/escalation-policy.md). */
export const REASON_COPY: Record<string, { title: string; hint: string }> = {
  HIGH_PRIORITY_INCIDENT: { title: 'High-priority incident', hint: 'Routed to the on-call engineer. The draft is an internal reference only.' },
  LOW_CLASSIFIER_CONFIDENCE: { title: 'Classifier is unsure', hint: 'Check type, queue and priority before you reply. Reclassify if needed.' },
  NO_PRECEDENT: { title: 'No similar past case', hint: 'No draft was generated. Nothing to ground a reply on; write it yourself.' },
  UNSUPPORTED_REQUEST: { title: 'Sensitive request', hint: 'Refunds, pricing, legal or security overrides need a human decision. Do not promise anything not in precedents.' },
  PROMPT_INJECTION_SUSPECTED: { title: 'Possible prompt injection', hint: 'The ticket tries to override instructions. No draft was generated.' },
  LLM_INSUFFICIENT_EVIDENCE: { title: 'Insufficient evidence', hint: 'The draft is a holding reply. Precedents do not answer the question.' },
  CITATION_CHECK_FAILED: { title: 'Citation check failed', hint: 'The draft cites something outside the retrieved precedents. Verify every sentence.' },
  LLM_UNAVAILABLE: { title: 'Draft service unavailable', hint: 'Classification still worked. Reply manually or retry later.' },
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('')
}

export const CITATION_RE = /\[(?:#)?(TKT-\d{3,})\]/g
