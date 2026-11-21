import { useEffect, useRef, useState } from 'react'
import * as api from '../../api'
import { BurstBanner } from '../../components/BurstBanner'
import { Button, Icon, LangChip, RouteBadge } from '../../components/ui'
import { DEMO_TICKETS, type DemoTicket } from '../../data/demoTickets'
import { ticketFromTriage } from '../../lib/liveTicket'
import { useBurstReset } from '../../lib/useBurstReset'
import { navigate } from '../../lib/router'
import { useStore, useToast } from '../../store'
import type { Burst, TriageResponse } from '../../types'

/** Presets tagged `"burst": true`, in file order (B2 says they must run consecutively). */
const BURST_PRESETS = DEMO_TICKETS.filter((d) => d.burst)
const GAP_MS = 1000
/** Offline only: mirrors BURST_MIN / BURST_WINDOW_MIN defaults so the demo still tells the story. */
const OFFLINE_MIN = 3
const OFFLINE_WINDOW = 15

type Row = { preset: DemoTicket; state: 'waiting' | 'running' | 'done' | 'error'; ticketId?: string; data?: TriageResponse; fallback?: boolean; error?: string }

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/**
 * Task C.5: POST /burst/reset, then send each burst preset one after another
 * with a 1 s gap, showing each result as it arrives.
 */
export default function BurstScenarioDialog({ onClose }: { onClose: () => void }) {
  const store = useStore()
  const toast = useToast()
  const resetDetector = useBurstReset()
  const [rows, setRows] = useState<Row[]>([])
  const [running, setRunning] = useState(false)
  const [resetting, setResetting] = useState(false)
  const alive = useRef(true)
  const storeRef = useRef(store)
  storeRef.current = store

  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])
  useEffect(() => {
    const on = (e: KeyboardEvent) => e.key === 'Escape' && !running && onClose()
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  }, [running, onClose])

  const setRow = (i: number, patch: Partial<Row>) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)))

  const run = async () => {
    if (running) return
    setRunning(true)
    setRows(BURST_PRESETS.map((preset) => ({ preset, state: 'waiting' })))
    if (!(await resetDetector())) { setRunning(false); setRows([]); return }
    const offlineIds: string[] = []
    for (let i = 0; i < BURST_PRESETS.length; i++) {
      if (!alive.current) return
      if (i > 0) await sleep(GAP_MS)
      if (!alive.current) return
      const p = BURST_PRESETS[i]
      setRow(i, { state: 'running' })
      try {
        const { data, fallback } = await api.triage(p.subject || null, p.body)
        if (fallback) {
          // The local fallback has no burst detector: simulate one, clearly labelled.
          offlineIds.push(data.request_id)
          const active = offlineIds.length >= OFFLINE_MIN
          data.burst = active
            ? { active, cluster_size: offlineIds.length, window_minutes: OFFLINE_WINDOW, label: 'VPN / remote access failures (offline simulation)', request_ids: [...offlineIds] }
            : { active, cluster_size: offlineIds.length, window_minutes: OFFLINE_WINDOW, label: null, request_ids: [] }
        }
        const id = storeRef.current.nextId()
        storeRef.current.add(ticketFromTriage(id, p.subject, p.body, data, { fallback, source: `burst scenario (${i + 1}/${BURST_PRESETS.length})` }))
        if (alive.current) setRow(i, { state: 'done', ticketId: id, data, fallback })
      } catch (e) {
        if (alive.current) setRow(i, { state: 'error', error: e instanceof Error ? e.message : 'Request failed' })
      }
    }
    if (alive.current) setRunning(false)
  }

  const reset = async () => {
    setResetting(true)
    if (await resetDetector()) {
      setRows([])
      toast({ tone: 'success', text: 'Burst cleared. The next similar ticket starts a new cluster.' })
    }
    if (alive.current) setResetting(false)
  }

  const latest: Burst | undefined = [...rows].reverse().find((r) => r.data?.burst.active)?.data?.burst
  const done = rows.filter((r) => r.state === 'done' || r.state === 'error').length

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-scrim backdrop-blur-sm sm:items-center sm:p-6" onClick={() => !running && onClose()}>
      <div role="dialog" aria-modal="true" aria-labelledby="burst-title" onClick={(e) => e.stopPropagation()} className="flex max-h-[92dvh] w-full max-w-2xl flex-col overflow-hidden rounded-t-3xl border border-line bg-dialog shadow-pop glass-strong sm:rounded-3xl">
        <header className="flex items-start gap-3 border-b border-line px-5 py-4">
          <div className="flex-1">
            <h2 id="burst-title" className="text-xl font-medium tracking-[-0.015em] text-ink">Burst scenario</h2>
            <p className="mt-0.5 text-sm text-muted">
              Resets the burst detector, then sends {BURST_PRESETS.length} similar VPN tickets one second apart. Watch the cluster grow until it is flagged as a possible major incident.
            </p>
          </div>
          <button aria-label="Close" onClick={onClose} disabled={running} className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-line bg-surface-2 text-muted hover:text-ink disabled:opacity-50"><Icon name="x" /></button>
        </header>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {latest && <BurstBanner burst={latest} />}
          <ol className="space-y-2" aria-live="polite" aria-label="Scenario results">
            {(rows.length ? rows : BURST_PRESETS.map((preset) => ({ preset, state: 'waiting' as const }))).map((r: Row, i) => (
              <li key={r.preset.id} className={`rounded-2xl border px-4 py-3 ${r.data?.burst.active ? 'border-oncall/40 bg-oncall-soft' : 'border-line bg-surface-2'}`}>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                  <span className="tabular w-8 shrink-0 font-mono text-xs text-muted">{i + 1}/{BURST_PRESETS.length}</span>
                  <p className="min-w-0 flex-1 truncate text-sm font-medium text-ink" title={r.preset.subject || r.preset.body}>{r.preset.subject || <span className="italic text-muted">(no subject) {r.preset.body.slice(0, 40)}…</span>}</p>
                  <RowState row={r} />
                </div>
                {r.data && (
                  <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 pl-11 text-xs">
                    <LangChip code={r.data.language.code} confidence={r.data.language.confidence} />
                    <RouteBadge route={r.data.escalation.route} label={r.data.escalation.badge} />
                    {r.data.burst.active ? (
                      <span className="inline-flex items-center gap-1 font-semibold text-oncall"><Icon name="zap" className="h-3.5 w-3.5" />In burst: <span className="tabular">{r.data.burst.cluster_size}</span> in {r.data.burst.window_minutes} min</span>
                    ) : (
                      <span className="text-muted">No burst yet (cluster of <span className="tabular">{r.data.burst.cluster_size}</span>)</span>
                    )}
                    {r.fallback && <span className="rounded-full bg-review-soft px-2 py-px font-medium text-review">Offline fallback</span>}
                    {r.ticketId && !running && (
                      <button className="ml-auto inline-flex items-center gap-1 font-medium text-accent hover:underline" onClick={() => { onClose(); navigate(`/inbox/${r.ticketId}`) }}>
                        Open {r.ticketId}<Icon name="chevronRight" className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                )}
                {r.error && <p role="alert" className="mt-2 pl-11 text-xs text-oncall">{r.error}</p>}
              </li>
            ))}
          </ol>
        </div>

        <footer className="flex flex-wrap items-center gap-2 border-t border-line px-5 py-3">
          <span className="tabular text-xs text-muted" aria-live="polite">{running ? `Sending ${Math.min(done + 1, BURST_PRESETS.length)} of ${BURST_PRESETS.length}…` : rows.length ? `${done} of ${BURST_PRESETS.length} sent` : 'Nothing sent yet'}</span>
          <Button variant="ghost" icon="refresh" className="ml-auto" onClick={reset} disabled={running || resetting}>{resetting ? 'Resetting…' : 'Reset burst'}</Button>
          <Button variant="primary" icon="zap" onClick={run} disabled={running || resetting}>{running ? 'Running…' : rows.length ? 'Run again' : 'Run burst scenario'}</Button>
        </footer>
      </div>
    </div>
  )
}

function RowState({ row }: { row: Row }) {
  if (row.state === 'waiting') return <span className="text-xs text-muted">Waiting</span>
  if (row.state === 'running') return <span className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-2"><Icon name="refresh" className="h-3.5 w-3.5 animate-spin" />Triaging…</span>
  if (row.state === 'error') return <span className="inline-flex items-center gap-1 text-xs font-medium text-oncall"><Icon name="alertCircle" className="h-3.5 w-3.5" />Failed</span>
  return <span className="tabular text-xs text-muted">{row.data?.latency_ms.total ?? 0} ms</span>
}
