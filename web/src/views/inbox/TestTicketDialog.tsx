import { useEffect, useRef, useState } from 'react'
import * as api from '../../api'
import { TriageProgress } from '../../components/TriageProgress'
import { Button, Icon } from '../../components/ui'
import { DEMO_TICKETS } from '../../data/demoTickets'
import { navigate } from '../../lib/router'
import { useStore, useToast } from '../../store'
import type { Priority, Queue, Ticket, TicketType } from '../../types'

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
      const now = new Date().toISOString()
      const ticket: Ticket = {
        id, subject: subject.trim(), body,
        requester: { name: 'Test customer', email: 'test@sentineldesk.local', org: 'Live test' },
        channel: 'email', created_at: now, updated_at: now, status: 'new', assignee: null, tags: [],
        type: data.predictions.type.label as TicketType, queue: data.predictions.queue.label as Queue, priority: data.predictions.priority.label as Priority,
        triage: data, acknowledged_by: null, linked_incidents: [],
        messages: [{ id: crypto.randomUUID(), author: 'Test customer', role: 'customer', internal: false, body, at: now }],
        audit: [
          { id: crypto.randomUUID(), at: now, actor: 'System', kind: 'status', text: 'Received via "Test a ticket"' },
          { id: crypto.randomUUID(), at: now, actor: 'SentinelDesk', kind: 'ai', text: `Classified as ${data.predictions.type.label} · ${data.predictions.queue.label} · ${data.predictions.priority.label} in ${data.latency_ms.total} ms. ${data.escalation.badge}.${fallback ? ' (offline fallback)' : ''}` },
        ],
      }
      store.add(ticket)
      if (fallback) toast({ tone: 'info', text: 'The triage service is offline. Showing a local fallback result.' })
      onClose()
      navigate(`/inbox/${id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong. Please try again.')
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-scrim backdrop-blur-sm sm:items-center sm:p-6" onClick={() => !busy && onClose()}>
      <div role="dialog" aria-modal="true" aria-labelledby="test-title" onClick={(e) => e.stopPropagation()} className="flex max-h-[92dvh] w-full max-w-xl flex-col glass-strong overflow-hidden rounded-t-2xl border border-line bg-dialog shadow-pop sm:rounded-2xl">
        <header className="flex items-start gap-3 border-b border-line px-5 py-4">
          <div className="flex-1">
            <h2 id="test-title" className="font-display text-xl font-semibold text-ink">Test a ticket</h2>
            <p className="mt-0.5 text-sm text-muted">Paste any English or German ticket. It is classified, checked and added to the inbox. Nothing is sent to anyone.</p>
          </div>
          <button aria-label="Close" onClick={onClose} disabled={busy} className="rounded-md p-1 text-muted hover:bg-surface-3 hover:text-ink"><Icon name="x" /></button>
        </header>
        {busy ? (
          <div className="px-5 py-8"><TriageProgress /></div>
        ) : (
          <form className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4" onSubmit={(e) => { e.preventDefault(); run() }}>
            <label className="block text-sm font-medium text-ink-2">Start from an example
              <select value={preset} onChange={(e) => { const d = DEMO_TICKETS.find((x) => x.id === e.target.value); setPreset(e.target.value); if (d) { setSubject(d.subject); setBody(d.body) } }}
                className="mt-1.5 h-9 w-full rounded-md border border-line-strong bg-surface px-2 text-sm text-ink">
                <option value="">Choose an example…</option>
                {DEMO_TICKETS.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
              </select>
            </label>
            {info && <p className="-mt-2 text-xs text-muted">{info.purpose}</p>}
            <label className="block text-sm font-medium text-ink-2">Subject <span className="font-normal text-muted">(optional)</span>
              <input value={subject} onChange={(e) => setSubject(e.target.value)} className="mt-1.5 h-9 w-full rounded-md border border-line-strong bg-surface px-3 text-sm text-ink" />
            </label>
            <label className="block text-sm font-medium text-ink-2">Message
              <textarea ref={bodyRef} value={body} onChange={(e) => setBody(e.target.value)} rows={9}
                onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); run() } }}
                className="mt-1.5 block w-full resize-y rounded-md border border-line-strong bg-surface px-3 py-2 text-sm leading-relaxed text-ink" />
            </label>
            <p className={`text-xs ${body.length > 8000 ? 'text-review' : 'text-muted'}`}>{body.length.toLocaleString()} characters{body.length > 8000 ? ' · only the first 8,000 are analysed' : ''}</p>
            {error && <p role="alert" className="rounded-md bg-oncall-soft px-3 py-2 text-sm text-oncall">{error}</p>}
          </form>
        )}
        <footer className="flex items-center gap-2 border-t border-line px-5 py-3">
          <span className="text-xs text-muted">⌘/Ctrl + Enter</span>
          <Button variant="ghost" className="ml-auto" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button variant="primary" icon="sparkle" onClick={run} disabled={!body.trim() || busy}>{busy ? 'Analysing…' : 'Analyse ticket'}</Button>
        </footer>
      </div>
    </div>
  )
}
