import type { Priority, Queue, Ticket, TicketType, TriageResponse } from '../types'

/** Wrap a live POST /triage result as an inbox ticket. Used by "Test a ticket" and the burst scenario. */
export function ticketFromTriage(id: string, subject: string, body: string, data: TriageResponse, opts: { fallback: boolean; source: string }): Ticket {
  const now = new Date().toISOString()
  const p = data.predictions
  return {
    id, subject, body,
    requester: { name: 'Test customer', email: 'test@sentineldesk.local', org: 'Live test' },
    channel: 'email', created_at: now, updated_at: now, status: 'new', assignee: null, tags: [],
    type: p.type.label as TicketType, queue: p.queue.label as Queue, priority: p.priority.label as Priority,
    triage: data, acknowledged_by: null, linked_incidents: [],
    messages: [{ id: crypto.randomUUID(), author: 'Test customer', role: 'customer', internal: false, body, at: now }],
    audit: [
      { id: crypto.randomUUID(), at: now, actor: 'System', kind: 'status', text: `Received via ${opts.source}` },
      { id: crypto.randomUUID(), at: now, actor: 'SentinelDesk', kind: 'ai', text: `Classified as ${p.type.label}, ${p.queue.label}, ${p.priority.label} priority in ${data.latency_ms.total} ms. ${data.escalation.badge}.${opts.fallback ? ' (offline fallback)' : ''}` },
    ],
  }
}
