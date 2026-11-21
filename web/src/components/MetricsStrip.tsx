import { summarizeMetrics } from '../lib/metrics'
import { useMetrics } from '../lib/useApi'
import { Icon } from './ui'

const f = (x: number | null) => (x === null ? '–' : x.toFixed(2))
const pctOrDash = (x: number | null) => (x === null ? '–' : `${Math.round(x * 100)}%`)

/** Task C.6: holdout metrics from GET /metrics. 404 means the eval has not run yet. */
export function MetricsStrip() {
  const m = useMetrics()
  if (m.state !== 'ok') {
    const text = m.state === 'loading' ? 'Loading holdout metrics…' : m.state === 'not_run' ? 'Eval not run yet' : 'Holdout metrics unavailable: the triage API is offline'
    return (
      <section aria-label="Holdout metrics" className="flex items-center gap-3 rounded-2xl border border-dashed border-line px-4 py-3 text-sm text-muted">
        <Icon name="chart" className="h-4 w-4" />
        <span className="font-medium text-ink-2">Holdout metrics</span>
        <span>{text}</span>
        {m.state === 'not_run' && <span className="hidden text-xs sm:inline">Run <code className="font-mono">python -m eval.run_eval</code> to fill this in.</span>}
      </section>
    )
  }
  const s = summarizeMetrics(m.metrics)
  const items: { label: string; value: string; hint: string }[] = [
    { label: 'Type macro-F1', value: f(s.f1.type), hint: 'Ticket type, averaged equally over classes' },
    { label: 'Queue macro-F1', value: f(s.f1.queue), hint: 'Routing queue, averaged equally over classes' },
    { label: 'Priority macro-F1', value: f(s.f1.priority), hint: 'Priority, averaged equally over classes' },
    { label: 'HPI escalation recall', value: pctOrDash(s.hpiRecall), hint: `High-priority incidents that were escalated${s.hpiSupport !== null ? ` (n = ${s.hpiSupport})` : ''}` },
    { label: 'p50 latency', value: s.p50 === null ? '–' : `${Math.round(s.p50).toLocaleString()} ms`, hint: `Median end-to-end time, ${s.p50Label}` },
  ]
  return (
    <section aria-label="Holdout metrics" className="rounded-2xl border border-line bg-surface px-4 py-3">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink"><Icon name="chart" className="h-4 w-4 text-muted" />Holdout metrics</h2>
        <p className="text-xs text-muted">
          Held-out test set{s.nTest !== null ? `, ${s.nTest.toLocaleString()} tickets` : ''}, never used for training or tuning
          {s.generatedAt ? ` · evaluated ${new Date(s.generatedAt).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}` : ''}
        </p>
      </div>
      <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-3 lg:grid-cols-5">
        {items.map((it) => (
          <div key={it.label} title={it.hint}>
            <dt className="text-xs text-muted">{it.label}</dt>
            <dd className="tabular text-xl font-semibold text-ink">{it.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
