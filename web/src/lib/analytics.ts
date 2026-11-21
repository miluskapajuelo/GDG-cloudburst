import type { AnalyticsSummary, HoldoutMetrics, Ticket } from '../types'

const DAY = 86_400_000
const BUCKETS = ['0–20%', '20–40%', '40–60%', '60–80%', '80–100%']

/** Escalation recall on high-priority incidents from eval/results/metrics.json, if the eval has run. */
export function hpiRecall(m: HoldoutMetrics | null): number | null {
  const hpi = (m as { high_priority_incident?: { escalation_recall?: unknown } } | null)?.high_priority_incident
  return typeof hpi?.escalation_recall === 'number' ? hpi.escalation_recall : null
}

function summarize(tickets: Ticket[]) {
  const triaged = tickets.filter((t) => t.triage)
  const n = triaged.length
  const esc = triaged.filter((t) => t.triage!.escalation.status === 'ESCALATE').length
  const onCall = triaged.filter((t) => t.triage!.escalation.route === 'ON_CALL').length
  const avgTriage = n ? triaged.reduce((s, t) => s + t.triage!.latency_ms.total, 0) / n : 0
  const firstReplies = tickets
    .map((t) => {
      const r = t.messages.find((m) => m.role === 'agent' && !m.internal)
      return r ? (Date.parse(r.at) - Date.parse(t.created_at)) / 60_000 : null
    })
    .filter((x): x is number => x !== null)
  const rated = tickets.filter((t) => t.feedback)
  const withDraftReply = tickets.filter((t) => t.triage?.draft && t.draft_sent_unedited !== undefined)
  return {
    total_tickets: tickets.length,
    escalation_rate: n ? esc / n : 0,
    on_call_rate: n ? onCall / n : 0,
    avg_triage_ms: Math.round(avgTriage),
    avg_first_response_min: firstReplies.length ? Math.round(firstReplies.reduce((a, b) => a + b, 0) / firstReplies.length) : 0,
    draft_acceptance_rate: rated.length ? rated.filter((t) => t.feedback!.rating === 'up').length / rated.length : 0,
    sent_without_edits_rate: withDraftReply.length ? withDraftReply.filter((t) => t.draft_sent_unedited).length / withDraftReply.length : 0,
  }
}

/** Analytics computed from the tickets triaged by the real API in this session, plus holdout recall. */
export function buildAnalytics(all: Ticket[], days: number, metrics: HoldoutMetrics | null, now = Date.now()): AnalyticsSummary {
  const start = now - days * DAY
  const cur = all.filter((t) => Date.parse(t.created_at) >= start)
  const prev = all.filter((t) => Date.parse(t.created_at) >= start - days * DAY && Date.parse(t.created_at) < start)

  const daily = Array.from({ length: days }, (_, i) => {
    const date = new Date(now - (days - 1 - i) * DAY).toISOString().slice(0, 10)
    const day = cur.filter((t) => t.created_at.slice(0, 10) === date)
    return {
      date,
      high: day.filter((t) => t.priority === 'high').length,
      medium: day.filter((t) => t.priority === 'medium').length,
      low: day.filter((t) => t.priority === 'low').length,
      escalated: day.filter((t) => t.triage?.escalation.status === 'ESCALATE').length,
    }
  })

  const hist = BUCKETS.map((bucket) => ({ bucket, count: 0 }))
  for (const t of cur) {
    if (!t.triage) continue
    const c = Math.min(t.triage.predictions.priority.confidence, t.triage.predictions.type.confidence)
    hist[Math.min(4, Math.floor(c * 5))].count++
  }

  const reasons = new Map<string, number>()
  for (const t of cur) if (t.feedback?.rating === 'down' && t.feedback.reason) reasons.set(t.feedback.reason, (reasons.get(t.feedback.reason) ?? 0) + 1)

  const s = summarize(cur)
  return {
    period_days: days,
    ...s,
    by_priority: {
      high: cur.filter((t) => t.priority === 'high').length,
      medium: cur.filter((t) => t.priority === 'medium').length,
      low: cur.filter((t) => t.priority === 'low').length,
    },
    confidence_histogram: hist,
    feedback_reasons: [...reasons].map(([reason, count]) => ({ reason, count })).sort((a, b) => b.count - a.count),
    daily,
    hpi_recall: hpiRecall(metrics),
    previous: summarize(prev),
  }
}
