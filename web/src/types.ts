/**
 * Types that mirror docs/contract.md §1 EXACTLY.
 * Do not rename fields. To change the contract, follow CLAUDE.md rule 1.
 */

export type TicketType = 'Incident' | 'Request' | 'Problem' | 'Change'
export type Priority = 'high' | 'medium' | 'low'
export type Queue =
  | 'Technical Support'
  | 'Product Support'
  | 'Customer Service'
  | 'IT Support'
  | 'Billing and Payments'
  | 'Returns and Exchanges'
  | 'Service Outages and Maintenance'
  | 'Sales and Pre-Sales'
  | 'Human Resources'
  | 'General Inquiry'

export const TYPES: TicketType[] = ['Incident', 'Request', 'Problem', 'Change']
export const PRIORITIES: Priority[] = ['high', 'medium', 'low']
export const QUEUES: Queue[] = [
  'Technical Support',
  'Product Support',
  'Customer Service',
  'IT Support',
  'Billing and Payments',
  'Returns and Exchanges',
  'Service Outages and Maintenance',
  'Sales and Pre-Sales',
  'Human Resources',
  'General Inquiry',
]

export interface Pred {
  label: string
  confidence: number
  probs: Record<string, number>
}

export type EscalationStatus = 'ESCALATE' | 'AUTO_DRAFT'
export type Route = 'ON_CALL' | 'HUMAN_REVIEW' | null

export type ReasonCode =
  | 'PROMPT_INJECTION_SUSPECTED'
  | 'HIGH_PRIORITY_INCIDENT'
  | 'LOW_CLASSIFIER_CONFIDENCE'
  | 'NO_PRECEDENT'
  | 'UNSUPPORTED_REQUEST'
  | 'LLM_INSUFFICIENT_EVIDENCE'
  | 'CITATION_CHECK_FAILED'
  | 'LLM_UNAVAILABLE'

export interface Reason {
  code: ReasonCode | string
  message: string
}

export interface Escalation {
  status: EscalationStatus
  route: Route
  badge: string
  reasons: Reason[]
}

export interface Precedent {
  ticket_id: string
  similarity: number
  language: string
  subject: string
  body_snippet: string
  answer_snippet: string
  answer: string
  type: string
  queue: string
  priority: string
  tags: string[]
}

export interface Draft {
  status: 'OK' | 'INSUFFICIENT_EVIDENCE'
  text: string
  cited_ids: string[]
  language: string
  for_human_review: boolean
  model: string
}

export interface Burst {
  active: boolean
  cluster_size: number
  window_minutes: number
  label: string | null
  request_ids: string[]
}

export type PiiKey = 'EMAIL' | 'PHONE' | 'IP' | 'IBAN' | 'CARD' | 'ACCOUNT'

export interface TriageResponse {
  request_id: string
  mock: boolean
  input: { subject: string | null; body_chars: number; truncated: boolean }
  language: { code: string; confidence: number; reply_language: 'en' | 'de' }
  pii: { masked: boolean; counts: Record<PiiKey, number> }
  predictions: { type: Pred; queue: Pred; priority: Pred }
  escalation: Escalation
  precedents: Precedent[]
  draft: Draft | null
  burst: Burst
  latency_ms: {
    pii: number
    language: number
    classify: number
    retrieve: number
    gate: number
    generate: number
    total: number
  }
}

export interface Health {
  status: string
  mock: boolean
  classifier_loaded: boolean
  index_size: number
  llm_configured: boolean
  llm_model: string
}

export type GateConfig = Record<string, number>

/** GET /metrics shape is owned by A2 (task A2.6); kept loose on purpose. */
export type HoldoutMetrics = Record<string, unknown>

// ---------------------------------------------------------------------------
// UI domain model (not part of the contract). A "ticket" in the workspace is
// the customer's message + the triage result + the human workflow around it.
// ---------------------------------------------------------------------------

export type WorkflowStatus = 'new' | 'open' | 'awaiting_customer' | 'resolved' | 'closed'
export type Channel = 'email' | 'portal' | 'phone'

export interface Message {
  id: string
  author: string
  role: 'customer' | 'agent' | 'system'
  /** Internal notes are never visible to the customer. */
  internal: boolean
  body: string
  at: string // ISO
  attachments?: string[]
}

export interface AuditEvent {
  id: string
  at: string
  actor: string
  kind: 'status' | 'priority' | 'assignee' | 'sla' | 'ai' | 'reclassify' | 'escalation' | 'reply' | 'feedback'
  text: string
}

export interface Ticket {
  id: string
  subject: string
  body: string
  requester: { name: string; email: string; org: string }
  channel: Channel
  created_at: string
  updated_at: string
  status: WorkflowStatus
  assignee: string | null
  tags: string[]
  /** Human-confirmed values; start as the AI predictions and can be reclassified. */
  type: TicketType
  queue: Queue
  priority: Priority
  /** null while triage is pending or the API failed (ticket is never lost). */
  triage: TriageResponse | null
  triage_error?: string
  acknowledged_by?: string | null
  messages: Message[]
  audit: AuditEvent[]
  csat?: number
  linked_incidents: string[]
  /**
   * NOT in the contract (gap): machine translation for the agent. Shown only when present.
   * To ship it, add it to POST /triage via the contract change process.
   */
  translation?: { subject: string; body: string; draft?: string }
  /** Recorded when the agent sends: true if the suggested draft went out unedited. */
  draft_sent_unedited?: boolean
  feedback?: { rating: 'up' | 'down'; reason?: string }
}

/**
 * NOT in the contract (gap): GET /analytics. Shape the UI expects from the backend.
 */
export interface AnalyticsSummary {
  period_days: number
  total_tickets: number
  by_priority: Record<Priority, number>
  escalation_rate: number
  on_call_rate: number
  avg_triage_ms: number
  avg_first_response_min: number
  draft_acceptance_rate: number
  sent_without_edits_rate: number
  confidence_histogram: { bucket: string; count: number }[]
  feedback_reasons: { reason: string; count: number }[]
  daily: { date: string; high: number; medium: number; low: number; escalated: number }[]
  hpi_recall: number | null
  previous: { total_tickets: number; escalation_rate: number; avg_triage_ms: number; avg_first_response_min: number; draft_acceptance_rate: number; sent_without_edits_rate: number }
}
