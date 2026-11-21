import type { Ticket } from '../types'
import { PRIORITY_RANK, sla } from './format'

export type Decision = 'critical' | 'review' | 'ready' | 'pending'

export const isOpen = (t: Ticket) => t.status !== 'resolved' && t.status !== 'closed'
export const isEscalated = (t: Ticket) => t.triage?.escalation.status === 'ESCALATE'

export function decision(t: Ticket): Decision {
  if (!t.triage) return 'pending'
  if (t.triage.escalation.route === 'ON_CALL') return 'critical'
  if (t.triage.escalation.status === 'ESCALATE') return 'review'
  return 'ready'
}

export const DECISION_COPY: Record<Decision, { label: string; short: string; group: string; hint: string }> = {
  critical: { label: 'Escalated to on-call', short: 'On-call', group: 'Critical incidents', hint: 'Engineering owns these. No automatic customer response.' },
  review: { label: 'Human review required', short: 'Review', group: 'Needs human review', hint: 'The safety check flagged something. Read the reason before replying.' },
  ready: { label: 'Safe for AI draft', short: 'Draft ready', group: 'Ready to respond', hint: 'A suggested response grounded in past resolutions is waiting for your review.' },
  pending: { label: 'Classification pending', short: 'Pending', group: 'Awaiting classification', hint: 'Classify these manually if the service is unavailable.' },
}
export const DECISION_ORDER: Decision[] = ['critical', 'review', 'ready', 'pending']

/** The weakest of the three predictions: the honest headline confidence for a ticket. */
export function minConfidence(t: Ticket): number | null {
  const p = t.triage?.predictions
  if (!p) return null
  return Math.min(p.type.confidence, p.queue.confidence, p.priority.confidence)
}

/** Time the customer has been waiting since their last message. */
export function waitingMs(t: Ticket, now: number): number {
  const lastCustomer = [...t.messages].reverse().find((m) => m.role === 'customer')
  const lastAgent = [...t.messages].reverse().find((m) => m.role === 'agent' && !m.internal)
  if (lastAgent && lastCustomer && Date.parse(lastAgent.at) > Date.parse(lastCustomer.at)) return 0
  return now - Date.parse(lastCustomer?.at ?? t.created_at)
}

/** Critical first, then unacknowledged, then priority, then longest wait. */
export function riskSort(now: number) {
  return (a: Ticket, b: Ticket) =>
    DECISION_ORDER.indexOf(decision(a)) - DECISION_ORDER.indexOf(decision(b)) ||
    Number(!!a.acknowledged_by) - Number(!!b.acknowledged_by) ||
    PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority] ||
    sla(a, now).remainingMs - sla(b, now).remainingMs
}
