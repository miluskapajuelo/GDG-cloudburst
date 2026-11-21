import type { PiiKey, TriageResponse } from '../types'
import { Icon, LangChip, PanelHeader } from './ui'

// ---------------------------------------------------------------------------
// Chips: detected language and masked PII (task C.4)
// ---------------------------------------------------------------------------
const PII_LABEL: Record<PiiKey, [string, string]> = {
  EMAIL: ['email', 'emails'],
  PHONE: ['phone number', 'phone numbers'],
  IP: ['IP', 'IPs'],
  IBAN: ['IBAN', 'IBANs'],
  CARD: ['card number', 'card numbers'],
  ACCOUNT: ['account number', 'account numbers'],
}

/** "1 email, 1 IP", or null when nothing was masked. */
export function piiSummary(counts: Partial<Record<PiiKey, number>> | undefined): string | null {
  if (!counts) return null
  const parts = (Object.keys(PII_LABEL) as PiiKey[])
    .filter((k) => (counts[k] ?? 0) > 0)
    .map((k) => `${counts[k]} ${PII_LABEL[k][counts[k] === 1 ? 0 : 1]}`)
  return parts.length ? parts.join(', ') : null
}

export function SignalChips({ tri }: { tri: TriageResponse }) {
  const pii = piiSummary(tri.pii?.counts)
  return (
    <div className="flex flex-wrap items-center gap-2">
      <LangChip code={tri.language.code} confidence={tri.language.confidence} />
      {pii && (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-3 px-2.5 py-0.5 text-xs font-medium text-ink-2" title="Personal data was replaced before any text left the server">
          <Icon name="shieldCheck" className="h-3 w-3 text-accent" />
          PII masked: {pii}
        </span>
      )}
      {tri.input?.truncated && (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-review-soft px-2.5 py-0.5 text-xs font-medium text-review">
          <Icon name="info" className="h-3 w-3" />
          Long message: first 8,000 characters analysed
        </span>
      )}
      {tri.mock && (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-3 px-2.5 py-0.5 text-xs font-medium text-muted" title="Mock mode or offline fallback. Not the trained model.">
          Mock result
        </span>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Latency: stacked bar per pipeline stage (task C.4)
// ---------------------------------------------------------------------------
const STAGES = [
  { key: 'pii', label: 'PII', cls: 'bg-ink-2/35' },
  { key: 'language', label: 'Language', cls: 'bg-ink-2/50' },
  { key: 'classify', label: 'Classify', cls: 'bg-ink-2/65' },
  { key: 'retrieve', label: 'Retrieve', cls: 'bg-accent' },
  { key: 'gate', label: 'Gate', cls: 'bg-review' },
  { key: 'generate', label: 'Generate', cls: 'bg-ai' },
] as const

export function LatencyBar({ latency }: { latency: TriageResponse['latency_ms'] }) {
  const total = latency.total || STAGES.reduce((a, s) => a + (latency[s.key] ?? 0), 0)
  const sum = STAGES.reduce((a, s) => a + (latency[s.key] ?? 0), 0) || 1
  const slowest = STAGES.reduce((m, s) => ((latency[s.key] ?? 0) > (latency[m.key] ?? 0) ? s : m), STAGES[0])
  return (
    <section aria-label="End-to-end latency" className="rounded-2xl border border-line bg-surface shadow-soft">
      <PanelHeader icon="timer" title="End-to-end latency" />
      <div className="grid gap-6 px-5 pb-5 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-end">
        <div>
          <p className="text-[13px] text-muted">This ticket</p>
          <p className="mt-2 flex items-baseline gap-1.5 text-ink">
            <span className="numeral text-[44px]">{total.toLocaleString()}</span>
            <span className="text-lg font-light text-ink-2">ms</span>
          </p>
          <p className="mt-2 text-xs text-muted">Slowest step: <span className="text-ink-2">{slowest.label.toLowerCase()}</span></p>
        </div>
        <div className="min-w-0">
          <div className="flex h-2.5 overflow-hidden rounded-full bg-surface-3" role="img"
            aria-label={STAGES.map((s) => `${s.label} ${latency[s.key] ?? 0} ms`).join(', ')}>
            {STAGES.map((s) => {
              const v = latency[s.key] ?? 0
              return v > 0 ? <span key={s.key} className={`${s.cls} h-full border-r-2 border-surface last:border-r-0`} style={{ width: `${(v / sum) * 100}%`, minWidth: 4 }} title={`${s.label}: ${v} ms`} /> : null
            })}
          </div>
          <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs sm:grid-cols-3">
            {STAGES.map((s) => (
              <li key={s.key} className="flex items-center gap-1.5">
                <span aria-hidden className={`h-2 w-2 rounded-full ${s.cls}`} />
                <span className="text-ink-2">{s.label}</span>
                <span className="tabular ml-auto text-muted">{(latency[s.key] ?? 0).toLocaleString()} ms</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Skeleton shaped like the result: badge, prediction rows, draft, precedents
// ---------------------------------------------------------------------------
export function ResultSkeleton() {
  return (
    <div aria-hidden className="space-y-4">
      <div className="skeleton h-12 w-64 rounded-full" />
      <div className="space-y-2">
        <div className="skeleton h-3 w-3/4" />
        <div className="skeleton h-3 w-1/2" />
      </div>
      <div className="space-y-3 rounded-2xl border border-line p-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="skeleton h-3 w-16" />
            <div className="skeleton h-3 flex-1" />
            <div className="skeleton h-2 w-20 rounded-full" />
          </div>
        ))}
      </div>
      <div className="space-y-2 rounded-2xl border border-line p-4">
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-3 w-11/12" />
        <div className="skeleton h-3 w-4/5" />
      </div>
      {[0, 1].map((i) => (
        <div key={i} className="flex items-center gap-3 rounded-xl border border-line p-3">
          <div className="skeleton h-3 w-20" />
          <div className="skeleton h-3 flex-1" />
          <div className="skeleton h-2 w-12 rounded-full" />
        </div>
      ))}
    </div>
  )
}
