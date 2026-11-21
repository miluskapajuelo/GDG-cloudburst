import { useEffect, useRef, useState } from 'react'
import * as api from '../../api'
import { ResultSkeleton } from '../../components/results'
import { TriageProgress } from '../../components/TriageProgress'
import { Button, Icon } from '../../components/ui'
import { DEMO_TICKETS } from '../../data/demoTickets'
import { ticketFromTriage } from '../../lib/liveTicket'
import { navigate } from '../../lib/router'
import { useStore, useToast } from '../../store'

/**
 * Paste any ticket and run it through the real pipeline (POST /triage).
 * Falls back to a local heuristic, clearly labelled, when the service is offline.
 */
export default function TestTicketDialog({ onClose }: { onClose: () => void }) {
  const store = useStore()
  const toast = useToast()
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [preset, setPreset] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const bodyRef = useRef<HTMLTextAreaElement>(null)
  const info = DEMO_TICKETS.find((d) => d.id === preset)

  useEffect(() => {
    bodyRef.current?.focus()
    const on = (e: KeyboardEvent) => e.key === 'Escape' && !busy && onClose()
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  }, [busy, onClose])

  const run = async () => {
    if (!body.trim() || busy) return
    setBusy(true)
    setError('')
    try {
      const { data, fallback } = await api.triage(subject.trim() || null, body)
      const id = store.nextId()
      const ticket = ticketFromTriage(id, subject.trim(), body, data, { fallback, source: '"Test a ticket"' })
      store.add(ticket)
      if (fallback) toast({ tone: 'info', text: 'The triage service is offline. Showing a local fallback result.' })
      onClose()
      navigate(`/inbox/${id}`)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Something went wrong. Please try again.'
      setError(msg)
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-scrim backdrop-blur-sm sm:items-center sm:p-6" onClick={() => !busy && onClose()}>
      <div role="dialog" aria-modal="true" aria-labelledby="test-title" onClick={(e) => e.stopPropagation()} className="flex max-h-[92dvh] w-full max-w-xl flex-col glass-strong overflow-hidden rounded-t-3xl border border-line bg-dialog shadow-pop sm:rounded-3xl">
        <header className="flex items-start gap-3 border-b border-line px-5 py-4">
          <div className="flex-1">
            <h2 id="test-title" className="text-xl font-medium tracking-[-0.015em] text-ink">Test a ticket</h2>
            <p className="mt-0.5 text-sm text-muted">Paste any English or German ticket. It is classified, checked and added to the inbox. Nothing is sent to anyone.</p>
          </div>
          <button aria-label="Close" onClick={onClose} disabled={busy} className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-line bg-surface-2 text-muted hover:text-ink"><Icon name="x" /></button>
        </header>
        {busy ? (
          <div className="grid min-h-0 flex-1 gap-6 overflow-y-auto px-5 py-6 sm:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]" role="status" aria-label="Triaging the ticket">
            <TriageProgress />
            <ResultSkeleton />
          </div>
        ) : (
          <form className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4" onSubmit={(e) => { e.preventDefault(); run() }}
            onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); run() } }}>
            <label className="block text-sm font-medium text-ink-2">Presets
              <select value={preset} onChange={(e) => { const d = DEMO_TICKETS.find((x) => x.id === e.target.value); setPreset(e.target.value); if (d) { setSubject(d.subject); setBody(d.body) } }}
                className="mt-1.5 h-10 w-full rounded-xl border border-line bg-surface-2 px-3 text-sm text-ink">
                <option value="">Choose a demo or red-team ticket</option>
                {DEMO_TICKETS.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
              </select>
            </label>
            {info && (
              <div className="-mt-1 rounded-xl border border-line bg-surface-2 px-3.5 py-2.5" aria-live="polite">
                <p className="text-sm font-semibold text-ink">{info.title}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-muted">{info.purpose}</p>
              </div>
            )}
            <label className="block text-sm font-medium text-ink-2">Subject <span className="font-normal text-muted">(optional)</span>
              <input value={subject} onChange={(e) => setSubject(e.target.value)} aria-describedby="subject-hint"
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.metaKey && !e.ctrlKey) { e.preventDefault(); bodyRef.current?.focus() } }}
                className="mt-1.5 h-10 w-full rounded-xl border border-line bg-surface-2 px-3 text-sm text-ink" />
            </label>
            {!subject.trim() && <p id="subject-hint" className="-mt-2 text-xs text-muted">Subject empty: fine. Many real tickets have none, so triage uses the message alone.</p>}
            <label className="block text-sm font-medium text-ink-2">Message <span className="font-normal text-muted">(required)</span>
              <textarea ref={bodyRef} value={body} onChange={(e) => setBody(e.target.value)} rows={9} required aria-describedby="body-count"
                className="mt-1.5 block w-full resize-y rounded-xl border border-line bg-surface-2 px-3 py-2.5 text-sm leading-relaxed text-ink" />
            </label>
            <p id="body-count" aria-live="polite" className={`tabular -mt-2 text-right text-xs ${body.length > 8000 ? 'font-semibold text-review' : 'text-muted'}`}>
              {body.length.toLocaleString()} characters{body.length > 8000 ? ' (only the first 8,000 are analysed)' : ''}
            </p>
          </form>
        )}
        {error && !busy && (
          <p role="alert" className="flex items-start gap-2 border-t border-oncall/30 bg-oncall-soft px-5 py-3 text-sm font-medium text-oncall">
            <Icon name="alertCircle" className="mt-0.5 h-4 w-4" />{error}
          </p>
        )}
        <footer className="flex items-center gap-2 border-t border-line px-5 py-3">
          <span className="text-xs text-muted">Ctrl or ⌘ + Enter to triage</span>
          <Button variant="ghost" className="ml-auto" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button variant="primary" icon="send" onClick={run} disabled={!body.trim() || busy} title={!body.trim() ? 'Write a message first' : undefined}>{busy ? 'Triaging…' : 'Triage'}</Button>
        </footer>
      </div>
    </div>
  )
}
