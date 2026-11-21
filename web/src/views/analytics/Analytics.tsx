import { useMemo, useState, type ReactNode } from 'react'
import { Icon, Segmented } from '../../components/ui'
import { buildAnalytics as demoAnalytics } from '../../data/mockBackend'
import { buildAnalytics } from '../../lib/analytics'
import { DEMO_MODE } from '../../lib/demoMode'
import { useMetrics } from '../../lib/useApi'
import { useStore } from '../../store'
import { pct } from '../../lib/format'
import { HBars, Histogram, Legend, StackedBars, type Series } from './charts'

const PRIO_SERIES: Series[] = [
  { key: 'low', label: 'Low', color: 'var(--chart-low)' },
  { key: 'medium', label: 'Medium', color: 'var(--chart-medium)' },
  { key: 'high', label: 'High', color: 'var(--chart-high)' },
]

export default function Analytics() {
  const [days, setDays] = useState<7 | 14 | 30>(14)
  const { tickets } = useStore()
  const m = useMetrics()
  const a = useMemo(() => (DEMO_MODE ? demoAnalytics(days) : buildAnalytics(tickets, days, m.state === 'ok' ? m.metrics : null)), [tickets, days, m])
  const [table, setTable] = useState(false)

  const fmtDay = (iso: string) => new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  const lowConf = a.confidence_histogram.slice(0, 2).reduce((s, r) => s + r.count, 0)
  const totalConf = a.confidence_histogram.reduce((s, r) => s + r.count, 0)
  const topReason = a.feedback_reasons[0]
  const totalFeedback = a.feedback_reasons.reduce((s, r) => s + r.count, 0)
  const highShare = a.total_tickets ? a.by_priority.high / a.total_tickets : 0

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-[1400px] space-y-8 px-4 pb-12 pt-8 sm:px-8">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <h1 className="text-[40px] leading-[1.1] text-ink">Analytics</h1>
            <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-muted">How fast the team responds, how often the safety check escalates, and how much agents trust the suggestions.</p>
          </div>
          <div className="ml-auto"><Segmented label="Time range" value={String(days) as '7' | '14' | '30'} options={[['7', '7 days'], ['14', '14 days'], ['30', '30 days']] as const} onChange={(v) => setDays(Number(v) as 7 | 14 | 30)} /></div>
        </div>

        <section className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-2xl border border-auto/25 bg-auto-soft px-5 py-4">
          <Icon name="shieldCheck" className="h-6 w-6 text-auto" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-ink">{a.hpi_recall !== null ? `${pct(a.hpi_recall)} of high-priority incidents were escalated` : 'High-priority incident recall: evaluation not run yet'}</p>
            <p className="text-sm text-ink-2">Measured on held-out tickets the system has never seen. This is the number that keeps critical incidents from being buried.</p>
          </div>
          <span className="text-xs text-muted">{pct(a.on_call_rate, 1)} of tickets go to on-call</span>
        </section>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Kpi label="Total tickets" value={a.total_tickets.toLocaleString()} cur={a.total_tickets} prev={a.previous.total_tickets} neutral />
          <Kpi label="Escalation rate" value={pct(a.escalation_rate)} cur={a.escalation_rate} prev={a.previous.escalation_rate} goodWhenDown />
          <Kpi label="Avg triage time" value={`${(a.avg_triage_ms / 1000).toFixed(1)} s`} cur={a.avg_triage_ms} prev={a.previous.avg_triage_ms} goodWhenDown />
          <Kpi label="Avg first response" value={`${a.avg_first_response_min} min`} cur={a.avg_first_response_min} prev={a.previous.avg_first_response_min} goodWhenDown />
          <Kpi label="Draft acceptance" value={pct(a.draft_acceptance_rate)} cur={a.draft_acceptance_rate} prev={a.previous.draft_acceptance_rate} />
          <Kpi label="Sent without edits" value={pct(a.sent_without_edits_rate)} cur={a.sent_without_edits_rate} prev={a.previous.sent_without_edits_rate} />
        </div>

        <div className="grid gap-6 xl:grid-cols-3">
          <Panel className="xl:col-span-2" title="Ticket volume" takeaway={`${pct(highShare)} of tickets are high priority.`}
            action={<button onClick={() => setTable((t) => !t)} aria-pressed={table} className="text-xs font-medium text-accent hover:underline">{table ? 'Show chart' : 'Show table'}</button>}>
            <div className="mb-3"><Legend series={[...PRIO_SERIES].reverse()} /></div>
            {table ? (
              <div className="max-h-64 overflow-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-surface text-left text-xs text-muted"><tr><th className="py-1.5 font-medium">Day</th><th className="py-1.5 text-right font-medium">High</th><th className="py-1.5 text-right font-medium">Medium</th><th className="py-1.5 text-right font-medium">Low</th><th className="py-1.5 text-right font-medium">Escalated</th></tr></thead>
                  <tbody className="tabular">{a.daily.map((d) => <tr key={d.date} className="border-t border-line"><td className="py-1.5">{fmtDay(d.date)}</td><td className="text-right">{d.high}</td><td className="text-right">{d.medium}</td><td className="text-right">{d.low}</td><td className="text-right">{d.escalated}</td></tr>)}</tbody>
                </table>
              </div>
            ) : (
              <StackedBars data={a.daily.map((d) => ({ label: fmtDay(d.date), values: { high: d.high, medium: d.medium, low: d.low } }))} series={PRIO_SERIES} />
            )}
          </Panel>

          <Panel title="Tickets by priority" takeaway="Low-priority tickets are the best candidates for suggested responses; high-priority ones are watched by the safety check.">
            <ul className="space-y-4">
              {(['high', 'medium', 'low'] as const).map((p) => {
                const n = a.by_priority[p]
                return (
                  <li key={p}>
                    <div className="mb-1.5 flex items-baseline justify-between text-sm">
                      <span className="flex items-center gap-2 font-medium capitalize text-ink"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: `var(--chart-${p})` }} />{p}</span>
                      <span className="tabular text-ink">{n.toLocaleString()} <span className="text-muted">· {pct(a.total_tickets ? n / a.total_tickets : 0)}</span></span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-surface-3"><div className="h-full rounded-full" style={{ width: pct(a.total_tickets ? n / a.total_tickets : 0), background: `var(--chart-${p})` }} /></div>
                  </li>
                )
              })}
            </ul>
          </Panel>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <Panel title="Confidence distribution" takeaway={`${pct(totalConf ? lowConf / totalConf : 0)} of tickets fall below 40% confidence and always go to a person. Most predictions are confident.`}>
            <Histogram rows={a.confidence_histogram} markerAfter={1} markerLabel="Left of the line: classifier unsure → human review" />
          </Panel>
          <Panel title="Why agents rejected suggestions" takeaway={topReason ? `“${topReason.reason}” is the most common reason (${pct(topReason.count / totalFeedback)} of negative feedback). Use it to improve the knowledge base.` : 'No negative feedback in this period.'}>
            <HBars rows={a.feedback_reasons.map((r) => ({ label: r.reason, value: r.count }))} />
            <p className="mt-3 text-xs text-muted">{totalFeedback} negative ratings in this period.</p>
          </Panel>
        </div>

        <p className="pb-4 text-xs text-muted">{DEMO_MODE ? 'Demo data, not live. Switch off "Demo data" in the top bar to see real numbers.' : 'Computed from tickets triaged by the live API in this session. Holdout recall comes from the evaluation run (GET /metrics).'}</p>
      </div>
    </div>
  )
}

function Kpi({ label, value, cur, prev, goodWhenDown, neutral }: { label: string; value: string; cur: number; prev: number; goodWhenDown?: boolean; neutral?: boolean }) {
  const delta = prev ? (cur - prev) / prev : 0
  const up = delta > 0
  const good = neutral ? null : up !== !!goodWhenDown
  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
      <p className="text-[13px] text-ink-2">{label}</p>
      <p className="numeral mt-3 text-[34px] text-ink">{value}</p>
      <p className={`mt-2 inline-flex items-center gap-0.5 text-xs ${good === null ? 'text-muted' : good ? 'text-auto' : 'text-oncall'}`}>
        <Icon name="chevronDown" className={`h-3.5 w-3.5 ${up ? 'rotate-180' : ''}`} />
        {Math.abs(delta * 100).toFixed(0)}%{good !== null && <span className="ml-1">{good ? 'better' : 'worse'}</span>}
        <span className="ml-1 text-muted">vs previous</span>
      </p>
    </div>
  )
}

function Panel({ title, takeaway, action, children, className = '' }: { title: string; takeaway: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-line bg-surface shadow-soft ${className}`}>
      <header className="flex items-start gap-3 px-5 pt-4">
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          <p className="mt-0.5 text-xs text-ink-2">{takeaway}</p>
        </div>
        {action}
      </header>
      <div className="p-5">{children}</div>
    </section>
  )
}
