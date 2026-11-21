import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { LatencyBar, SignalChips } from '../../components/results'
import { Avatar, Button, EmptyState, Icon, Kbd, LangChip, PanelHeader, PriorityBadge, RouteBadge, type IconName } from '../../components/ui'
import { AGENT } from '../../lib/session'
import { ago, band, dateTime, duration, LANG_LABEL, pct, PRIORITY_LABEL, REASON_COPY, STATUS_LABEL } from '../../lib/format'
import { usePrefs } from '../../lib/prefs'
import { isTyping, navigate } from '../../lib/router'
import { decision, DECISION_COPY, isEscalated, isOpen, riskSort, waitingMs } from '../../lib/ticket'
import { useNow, useStore, useToast } from '../../store'
import { PRIORITIES, QUEUES, TYPES, type Pred, type Precedent, type Priority, type Queue, type Ticket, type TicketType } from '../../types'
import ResponseWorkspace from './ResponseWorkspace'

type Section = 'inbox' | 'escalated' | 'resolved'

export default function TicketDetail({ id, section }: { id: string; section: Section }) {
  const store = useStore()
  const toast = useToast()
  const now = useNow()
  const t = store.get(id)
  const [highlight, setHighlight] = useState<{ id: string; n: number } | null>(null)

  const siblings = useMemo(() => {
    const scoped = store.tickets.filter((x) => (section === 'resolved' ? !isOpen(x) : section === 'escalated' ? isOpen(x) && isEscalated(x) : isOpen(x)))
    return scoped.sort(riskSort(now)).map((x) => x.id)
  }, [store.tickets, section, now])
  const idx = siblings.indexOf(id)
  const prev = idx > 0 ? siblings[idx - 1] : null
  const next = idx >= 0 && idx < siblings.length - 1 ? siblings[idx + 1] : null

  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (isTyping(e) || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'j' && next) navigate(`/${section}/${next}`)
      else if (e.key === 'k' && prev) navigate(`/${section}/${prev}`)
      else if (e.key === 'Escape') navigate(`/${section}`)
    }
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  }, [next, prev, section])

  // Publish the scroll area's height as --ws-h so the sticky history column can cap itself to it.
  const scrollRef = useCallback((node: HTMLDivElement | null) => {
    if (!node) return
    const ro = new ResizeObserver(() => node.style.setProperty('--ws-h', `${node.clientHeight}px`))
    ro.observe(node)
    return () => ro.disconnect()
  }, [])

  if (!t) {
    return <div className="flex h-full items-center justify-center"><EmptyState icon="inbox" title="Ticket not found"><a className="text-accent hover:underline" href={`#/${section}`}>Back to {section}</a></EmptyState></div>
  }

  const d = decision(t)
  const cite = (cid: string) => setHighlight((h) => ({ id: cid, n: (h?.n ?? 0) + 1 }))
  const assignMe = () => {
    store.patch(t.id, { assignee: AGENT.name, status: t.status === 'new' ? 'open' : t.status }, { kind: 'assignee', text: `Assigned to ${AGENT.name}` }, AGENT.name)
    toast({ tone: 'success', text: 'Assigned to you' })
  }
  const acknowledge = () => {
    store.patch(t.id, { acknowledged_by: AGENT.name, assignee: t.assignee ?? AGENT.name, status: t.status === 'new' ? 'open' : t.status }, { kind: 'escalation', text: `Incident acknowledged by ${AGENT.name}. Team notified.` }, AGENT.name)
    toast({ tone: 'success', text: 'Incident acknowledged. The team can see you own it.' })
  }
  const escalate = () => {
    if (!t.triage) return
    const before = t
    store.replace({
      ...t,
      triage: { ...t.triage, escalation: { status: 'ESCALATE', route: 'ON_CALL', badge: 'Escalate to On-Call Engineer', reasons: [{ code: 'MANUAL_ESCALATION', message: `Escalated to engineering by ${AGENT.name}.` }, ...t.triage.escalation.reasons] } },
      audit: [...t.audit, { id: crypto.randomUUID(), at: new Date().toISOString(), actor: AGENT.name, kind: 'escalation', text: 'Escalated to engineering manually' }],
    })
    toast({ tone: 'info', text: 'Escalated to engineering. On-call has been notified.', undo: () => store.replace(before) })
  }
  const resolve = () => {
    const before = t
    store.patch(t.id, { status: 'resolved' }, { kind: 'status', text: `Status: ${STATUS_LABEL[t.status]} → Resolved` }, AGENT.name)
    toast({ tone: 'success', text: 'Ticket resolved', undo: () => store.replace(before) })
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <header className="shrink-0 border-b border-line bg-surface px-4 pb-4 pt-3 sm:px-6">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <a href={`#/${section}`} className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
            <Icon name="arrowLeft" /> <span className="capitalize">{section}</span>
          </a>
          <span aria-hidden className="text-muted">/</span>
          <span className="tabular font-mono text-xs text-muted">{t.id}</span>
          <div className="ml-auto flex items-center gap-1">
            <span className="tabular mr-1 hidden text-xs text-muted md:inline">{idx + 1} of {siblings.length}</span>
            <button aria-label="Previous ticket (K)" disabled={!prev} onClick={() => prev && navigate(`/${section}/${prev}`)} className="rounded-lg p-1.5 text-ink-2 hover:bg-surface-3 disabled:opacity-30"><Icon name="chevronDown" className="h-4 w-4 rotate-180" /></button>
            <button aria-label="Next ticket (J)" disabled={!next} onClick={() => next && navigate(`/${section}/${next}`)} className="rounded-lg p-1.5 text-ink-2 hover:bg-surface-3 disabled:opacity-30"><Icon name="chevronDown" className="h-4 w-4" /></button>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-start gap-x-6 gap-y-3">
          <div className="min-w-0 flex-1">
            <h1 className="font-sans text-[20px] font-semibold leading-snug tracking-[-0.01em] text-ink sm:text-[22px]">{t.subject || <span className="text-muted">(no subject)</span>}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 text-[13px] text-muted">
              <PriorityBadge priority={t.priority} />
              <DecisionPill t={t} />
              <span>{STATUS_LABEL[t.status]}</span>
              <span>{t.assignee ? <>Assigned to <span className="text-ink-2">{t.assignee === AGENT.name ? 'you' : t.assignee}</span></> : <span className={d === 'critical' ? 'font-medium text-oncall' : ''}>Unassigned</span>}</span>
              {isOpen(t) && waitingMs(t, now) > 0 && <span className="tabular">Waiting {duration(waitingMs(t, now))}</span>}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {d === 'critical' && !t.acknowledged_by && isOpen(t) && <Button variant="danger" icon="siren" onClick={acknowledge}>Acknowledge incident</Button>}
            {t.assignee !== AGENT.name && isOpen(t) && <Button onClick={assignMe} icon="user">Assign to me</Button>}
            {d !== 'critical' && isOpen(t) && t.triage && <Button onClick={escalate} icon="siren">Escalate to engineering</Button>}
            {isOpen(t) && <Button variant="ghost" onClick={resolve} icon="checkCircle">Resolve</Button>}
          </div>
        </div>
      </header>

      {/* 3-column workspace: one scroll for the page; columns hug their content; side columns stay in view and scroll on their own. */}
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto xl:grid xl:grid-cols-[minmax(250px,30fr)_minmax(360px,42fr)_minmax(240px,28fr)] xl:items-start xl:gap-6 xl:p-6">
        <section aria-label="Customer ticket" className="border-b border-line bg-surface-2 xl:sticky xl:top-0 xl:max-h-[calc(var(--ws-h,100dvh)-3rem)] xl:overflow-y-auto xl:rounded-2xl xl:border">
          <CustomerColumn t={t} now={now} />
        </section>
        <section aria-label="Decision and response" className="space-y-5 p-4 sm:p-6 xl:p-0">
          <DecisionCard t={t} now={now} />
          <Classification t={t} />
          {t.triage && <LatencyBar latency={t.triage.latency_ms} />}
          <ResponseWorkspace key={`${t.id}-${t.triage?.request_id}`} t={t} onCite={cite} />
          <p className="flex items-center justify-center gap-3 pb-2 text-xs text-muted">
            <span><Kbd>J</Kbd><Kbd>K</Kbd> next / previous</span><span><Kbd>Esc</Kbd> back</span><span><Kbd>⌘</Kbd><Kbd>↵</Kbd> send</span>
          </p>
        </section>
        <section aria-label="Supporting history" className="border-t border-line bg-surface-2 xl:sticky xl:top-0 xl:max-h-[calc(var(--ws-h,100dvh)-3rem)] xl:overflow-y-auto xl:rounded-2xl xl:border">
          <HistoryColumn t={t} highlight={highlight} />
        </section>
      </div>
    </div>
  )
}

function DecisionPill({ t }: { t: Ticket }) {
  const d = decision(t)
  const map: Record<string, [IconName, string]> = { critical: ['siren', 'bg-oncall-soft text-oncall'], review: ['eye', 'bg-review-soft text-review'], ready: ['shieldCheck', 'bg-auto-soft text-auto'], pending: ['circleDashed', 'bg-surface-3 text-muted'] }
  const [icon, cls] = map[d]
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}><Icon name={icon} className="h-3.5 w-3.5" />{DECISION_COPY[d].label}</span>
}

// ---------------------------------------------------------------------------
// Left: what the customer wrote
// ---------------------------------------------------------------------------
function CustomerColumn({ t, now }: { t: Ticket; now: number }) {
  const store = useStore()
  const { prefs } = usePrefs()
  const [showTr, setShowTr] = useState(prefs.showTranslation)
  const [note, setNote] = useState('')
  const lang = t.triage?.language.code ?? 'en'
  const first = t.messages[0]
  const rest = t.messages.slice(1)
  const others = store.tickets.filter((x) => x.requester.email === t.requester.email && x.id !== t.id)

  return (
    <div className="space-y-5 p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <Avatar name={t.requester.name} size="md" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-ink">{t.requester.name}</p>
          <p className="truncate text-xs text-muted">{t.requester.org}</p>
          <p className="truncate text-xs text-muted">{t.requester.email}</p>
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-2 rounded-2xl border border-line bg-surface p-4 text-xs">
        <dt className="text-muted">Received</dt><dd className="text-right text-ink-2" title={dateTime(t.created_at)}>{ago(t.created_at, now)}</dd>
        <dt className="text-muted">Channel</dt><dd className="text-right capitalize text-ink-2">{t.channel}</dd>
        <dt className="text-muted">Original language</dt><dd className="text-right text-ink-2">{LANG_LABEL[lang] ?? lang.toUpperCase()}{t.triage && <span className="text-muted"> ({pct(t.triage.language.confidence)})</span>}</dd>
        {t.linked_incidents.length > 0 && <><dt className="text-muted">Linked incident</dt><dd className="text-right font-mono text-ink-2">{t.linked_incidents.join(', ')}</dd></>}
      </dl>

      {/* Original message */}
      <article className="overflow-hidden rounded-2xl border border-line bg-surface">
        <header className="flex items-center gap-2 border-b border-line px-3 py-2">
          <LangChip code={lang} />
          <span className="text-xs font-medium text-ink-2">Original message</span>
          <time className="ml-auto text-xs text-muted" dateTime={first?.at}>{first && dateTime(first.at)}</time>
        </header>
        <div className="px-3 py-3">
          <p className="mb-2 text-sm font-medium text-ink">{t.subject}</p>
          <p className="whitespace-pre-wrap break-words text-[14px] leading-relaxed text-ink">{t.body}</p>
        </div>
        {lang !== 'en' && (
          <div className="border-t border-line">
            <button onClick={() => setShowTr((s) => !s)} aria-expanded={showTr} className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-accent hover:bg-surface-2">
              <Icon name="languages" className="h-3.5 w-3.5" /> {showTr ? 'Hide' : 'Show'} English translation
              <Icon name="chevronDown" className={`ml-auto h-3.5 w-3.5 transition ${showTr ? 'rotate-180' : ''}`} />
            </button>
            {showTr && (
              t.translation ? (
                <div className="border-t border-dashed border-line bg-surface-2 px-3 py-3">
                  <p className="mb-2 text-sm font-medium text-ink-2">{t.translation.subject}</p>
                  <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-ink-2">{t.translation.body}</p>
                  <p className="mt-2 text-xs text-muted">Machine translation for reference. Reply in {LANG_LABEL[lang]}.</p>
                </div>
              ) : (
                <p className="border-t border-dashed border-line px-3 py-3 text-xs text-muted">Translation is not available for this ticket yet.</p>
              )
            )}
          </div>
        )}
      </article>

      {rest.length > 0 && (
        <section aria-label="Conversation">
          <h3 className="mb-2 text-[13px] font-semibold text-ink-2">Conversation</h3>
          <ol className="space-y-2.5">
            {rest.map((m) => (
              <li key={m.id} className={`rounded-lg border px-3 py-2.5 ${m.internal ? 'border-note-line bg-note' : m.role === 'customer' ? 'border-line' : 'border-line bg-surface-2'}`}>
                <p className="mb-1 flex items-center gap-1.5 text-xs">
                  <span className="font-medium text-ink">{m.author}</span>
                  <span className="text-muted">{m.internal ? 'Internal note' : m.role === 'agent' ? 'Sent to customer' : 'Customer'}</span>
                  {m.internal && <Icon name="lock" className="h-3 w-3 text-review" />}
                  <time className="ml-auto text-muted" dateTime={m.at} title={dateTime(m.at)}>{ago(m.at, now)}</time>
                </p>
                <p className="whitespace-pre-wrap break-words text-[13px] leading-relaxed text-ink">{m.body}</p>
              </li>
            ))}
          </ol>
        </section>
      )}

      <form onSubmit={(e) => { e.preventDefault(); if (note.trim()) { store.message(t.id, { author: AGENT.name, role: 'agent', internal: true, body: note.trim() }); setNote('') } }}>
        <label htmlFor="note" className="mb-1.5 flex items-center gap-1.5 text-[13px] font-semibold text-ink-2"><Icon name="lock" className="h-3 w-3" />Internal note</label>
        <div className="flex gap-2">
          <input id="note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Visible to your team only" className="h-9 min-w-0 flex-1 rounded-full border border-line bg-surface-2 px-4 text-sm placeholder:text-muted" />
          <Button type="submit" disabled={!note.trim()}>Add</Button>
        </div>
      </form>

      <TicketHistory t={t} />

      {others.length > 0 && (
        <section>
          <h3 className="mb-2 text-[13px] font-semibold text-ink-2">Other tickets from {t.requester.name.split(' ')[0]}</h3>
          <ul className="space-y-1">{others.map((o) => <li key={o.id}><a href={`#/inbox/${o.id}`} className="block truncate rounded px-2 py-1 text-sm text-ink-2 hover:bg-surface-3">{o.subject}</a></li>)}</ul>
        </section>
      )}
    </div>
  )
}

function TicketHistory({ t }: { t: Ticket }) {
  const [open, setOpen] = useState(false)
  const events = [...t.audit].reverse()
  const shown = open ? events : events.slice(0, 3)
  return (
    <section>
      <h3 className="mb-2 text-[13px] font-semibold text-ink-2">Ticket history</h3>
      <ol className="relative space-y-3 border-l border-line pl-4">
        {shown.map((e) => (
          <li key={e.id} className="relative text-xs">
            <span className={`absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full border-2 border-surface ${e.kind === 'escalation' ? 'bg-oncall' : e.kind === 'ai' ? 'bg-accent' : e.kind === 'reply' ? 'bg-auto' : 'bg-line-strong'}`} aria-hidden />
            <p className="text-ink-2">{e.text}</p>
            <p className="text-muted">{e.actor}, {dateTime(e.at)}</p>
          </li>
        ))}
      </ol>
      {events.length > 3 && <button onClick={() => setOpen((o) => !o)} aria-expanded={open} className="mt-2 text-xs font-medium text-accent hover:underline">{open ? 'Show less' : `Show all ${events.length} events`}</button>}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Center: the safety decision, always explicit
// ---------------------------------------------------------------------------
function DecisionCard({ t, now }: { t: Ticket; now: number }) {
  const store = useStore()
  const d = decision(t)
  const tri = t.triage
  if (!tri) return null
  const cited = tri.draft?.cited_ids.length ?? 0
  const related = tri.burst.active ? store.tickets.filter((x) => x.id !== t.id && x.triage?.burst.active && x.triage.burst.label === tri.burst.label) : []

  const cfg = {
    critical: { cls: 'border-oncall/30', head: '', icon: 'siren' as const, title: 'Escalated: critical service impact detected', sub: 'Routed to the on-call engineer. Nothing is sent to the customer automatically.' },
    review: { cls: 'border-review/30', head: '', icon: 'eye' as const, title: 'Human review required', sub: 'Read the reason below before you respond. You decide what is sent.' },
    ready: { cls: 'border-auto/25', head: '', icon: 'shieldCheck' as const, title: 'Safe for AI draft', sub: `No risk signals found. The suggested response is based on ${cited} historical resolution${cited === 1 ? '' : 's'}. Review it before sending.` },
    pending: { cls: 'border-line', head: '', icon: 'circleDashed' as const, title: 'Classification pending', sub: '' },
  }[d]

  return (
    <section aria-label="Safety decision" className={`overflow-hidden rounded-2xl border bg-surface shadow-soft ${cfg.cls}`}>
      <div className={`space-y-4 px-5 pb-5 pt-5 ${cfg.head}`}>
        <h2 className="sr-only">Escalation decision</h2>
        <RouteBadge route={tri.escalation.route} label={tri.escalation.badge} size="lg" />
        <p className="text-sm text-ink-2">{cfg.sub}</p>
        <SignalChips tri={tri} />
      </div>
      {tri.escalation.reasons.length > 0 && (
        <div className="border-t border-line">
          <h3 className="px-5 pt-4 text-sm font-medium text-ink-2">Why this decision</h3>
          <ul className="divide-y divide-line">
            {tri.escalation.reasons.map((r, i) => (
              <li key={i} className="px-5 py-3 text-sm">
                <p className="text-ink"><code className="rounded-md bg-surface-3 px-1.5 py-px font-mono text-xs font-medium">{r.code}</code> {r.message}</p>
                {REASON_COPY[r.code] && <p className="mt-1 text-xs text-muted">What to do: {REASON_COPY[r.code].hint}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}
      {d === 'critical' && (
        <div className="grid gap-3 border-t border-line px-5 py-4 text-sm sm:grid-cols-2">
          <div>
            <p className="text-xs text-muted">Owner</p>
            <p className="font-medium text-ink">{t.acknowledged_by ? <span className="inline-flex items-center gap-1.5"><Icon name="check" className="h-4 w-4 text-auto" />{t.acknowledged_by}</span> : <span className="text-oncall">Not yet acknowledged</span>}</p>
          </div>
          <div>
            <p className="text-xs text-muted">Impact</p>
            <p className="text-ink">{t.requester.org}{tri.burst.active ? ` + ${tri.burst.cluster_size - 1} other customers` : ''}</p>
          </div>
        </div>
      )}
      {related.length > 0 && (
        <div className="border-t border-line px-4 py-3">
          <p className="flex items-center gap-1.5 text-xs font-semibold text-ink"><Icon name="zap" className="h-3.5 w-3.5 text-review" />{tri.burst.cluster_size} similar reports in {tri.burst.window_minutes} min: “{tri.burst.label}”</p>
          <ul className="mt-2 space-y-1">
            {related.map((r) => (
              <li key={r.id}>
                <a href={`#/inbox/${r.id}`} className="flex items-center gap-2 rounded px-1.5 py-1 text-sm hover:bg-surface-3">
                  <PriorityBadge priority={r.priority} compact />
                  <span className="min-w-0 flex-1 truncate text-ink-2">{r.subject}</span>
                  <span className="shrink-0 text-xs text-muted">{r.requester.org}, {ago(r.created_at, now)}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Center: editable classification with honest confidence
// ---------------------------------------------------------------------------
function Classification({ t }: { t: Ticket }) {
  const store = useStore()
  const p = t.triage?.predictions
  return (
    <section aria-label="Classification" className="rounded-2xl border border-line bg-surface shadow-soft">
      <PanelHeader icon="layers" tone="ai" title="Predictions" sub="Suggested by the classifier. Edit if wrong."
        actions={<span className="rounded-full bg-ai-soft px-2.5 py-0.5 text-xs font-medium text-ai">AI</span>} />
      <div className="divide-y divide-line">
        <Field label="Type" value={t.type} options={TYPES} pred={p?.type}
          onChange={(v) => store.patch(t.id, { type: v as TicketType }, { kind: 'reclassify', text: `Type corrected: ${t.type} → ${v}` }, AGENT.name)} />
        <Field label="Queue" value={t.queue} options={QUEUES} pred={p?.queue}
          onChange={(v) => store.patch(t.id, { queue: v as Queue }, { kind: 'reclassify', text: `Queue corrected: ${t.queue} → ${v}` }, AGENT.name)} />
        <Field label="Priority" value={t.priority} options={PRIORITIES} pred={p?.priority} format={(v) => PRIORITY_LABEL[v as Priority]}
          onChange={(v) => store.patch(t.id, { priority: v as Priority }, { kind: 'priority', text: `Priority corrected: ${t.priority} → ${v}` }, AGENT.name)} />
      </div>
    </section>
  )
}

function Field({ label, value, options, pred, onChange, format = (v) => v }: { label: string; value: string; options: readonly string[]; pred?: Pred; onChange: (v: string) => void; format?: (v: string) => string }) {
  const id = `cls-${label}`
  const corrected = pred && pred.label !== value
  const b = pred ? band(pred.confidence) : null
  const bar = b === 'High' ? 'bg-auto' : b === 'Medium' ? 'bg-review' : 'bg-oncall'
  const ranked = pred ? Object.entries(pred.probs).sort((a, z) => z[1] - a[1]) : []
  const alts = ranked.slice(1, 3)
  const top3 = ranked.slice(0, 3)
  return (
    <div className="grid gap-x-4 gap-y-1 px-5 py-3 sm:grid-cols-[88px_minmax(0,1fr)_minmax(0,1.1fr)] sm:items-start">
      <label htmlFor={id} className="pt-1.5 text-[13px] font-medium text-muted">{label}</label>
      <div className="relative">
        <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className="w-full cursor-pointer appearance-none truncate rounded-md border border-transparent bg-transparent py-1 pr-6 text-sm font-semibold text-ink hover:border-line-strong focus:border-line-strong">
          {options.map((o) => <option key={o} value={o}>{format(o)}</option>)}
        </select>
        <Icon name="chevronDown" className="pointer-events-none absolute right-1 top-2 h-3.5 w-3.5 text-muted" />
      </div>
      {pred && (corrected ? (
        <p className="flex items-center gap-1 pt-1.5 text-xs text-accent"><Icon name="pencil" className="h-3 w-3" />Corrected by you (suggested {format(pred.label)})</p>
      ) : (
        <div className="pt-1">
          <div className="flex items-center justify-between text-xs">
            <span className={b === 'Low' ? 'font-medium text-review' : 'text-ink-2'}>Confidence: {b}</span>
            <span className="tabular font-mono font-semibold text-ink">{pct(pred.confidence)}</span>
          </div>
          <div className="mt-1 h-1 overflow-hidden rounded-full bg-surface-3" role="meter" aria-label={`${label} confidence`} aria-valuenow={Math.round(pred.confidence * 100)} aria-valuemin={0} aria-valuemax={100}>
            <div className={`h-full rounded-full ${bar}`} style={{ width: pct(pred.confidence) }} />
          </div>
          {b === 'Low' && alts[0] && <p className="mt-1 text-xs text-muted">Next most likely: {format(alts[0][0])} ({pct(alts[0][1])})</p>}
          {top3.length > 1 && (
            <details className="group mt-1.5 text-xs">
              <summary className="cursor-pointer list-none font-medium text-accent hover:underline">Top {top3.length} probabilities</summary>
              <ul className="mt-1.5 space-y-1">
                {top3.map(([k, v]) => (
                  <li key={k} className="flex items-center gap-2">
                    <span className="min-w-0 flex-1 truncate text-ink-2">{format(k)}</span>
                    <span className="h-1 w-14 overflow-hidden rounded-full bg-surface-3"><span className="block h-full rounded-full bg-accent" style={{ width: pct(v) }} /></span>
                    <span className="tabular w-10 text-right font-mono text-muted">{pct(v)}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Right: historical resolutions the response is based on
// ---------------------------------------------------------------------------
function HistoryColumn({ t, highlight }: { t: Ticket; highlight: { id: string; n: number } | null }) {
  const store = useStore()
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  const precedents = (t.triage?.precedents ?? []).filter((p) => !hidden.has(p.ticket_id))
  const cited = new Set(t.triage?.draft?.cited_ids ?? [])
  const lang = t.triage?.language.code ?? 'en'
  return (
    <div className="p-4 sm:p-5">
      <h2 className="text-sm font-semibold text-ink">Supporting history</h2>
      <p className="mt-0.5 text-xs text-muted">
        {precedents.length ? `${precedents.length} similar resolved ticket${precedents.length === 1 ? '' : 's'}, most similar first.` : 'No similar resolutions found.'}
      </p>
      {precedents.length === 0 ? (
        <div className="mt-4 rounded-lg border border-dashed border-line-strong p-4 text-sm text-muted">
          <p className="font-medium text-ink">No similar resolutions found</p>
          <p className="mt-1">Nothing in the history is close enough to rely on. Treat this as a new case.</p>
        </div>
      ) : (
        <ul className="mt-4 space-y-3">
          {precedents.map((p) => (
            <PrecedentCard key={p.ticket_id} p={p} cited={cited.has(p.ticket_id)} cross={p.language !== lang} highlight={highlight?.id === p.ticket_id ? highlight.n : 0}
              onHide={() => { setHidden((s) => new Set(s).add(p.ticket_id)); store.patch(t.id, {}, { kind: 'feedback', text: `${p.ticket_id} marked not relevant` }, AGENT.name) }} />
          ))}
        </ul>
      )}
      {hidden.size > 0 && <button onClick={() => setHidden(new Set())} className="mt-3 text-xs font-medium text-accent hover:underline">Show {hidden.size} hidden</button>}
    </div>
  )
}

function PrecedentCard({ p, cited, cross, highlight, onHide }: { p: Precedent; cited: boolean; cross: boolean; highlight: number; onHide: () => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLLIElement>(null)
  useEffect(() => {
    if (!highlight) return
    setOpen(true)
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    ref.current?.classList.remove('flash')
    void ref.current?.offsetWidth
    ref.current?.classList.add('flash')
  }, [highlight])
  return (
    <li ref={ref} id={`prec-${p.ticket_id}`} className={`rounded-2xl border bg-surface transition-colors ${highlight ? 'border-accent ring-2 ring-accent/25' : 'border-line'}`}>
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open} className="block w-full px-3.5 py-3 text-left">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-medium text-accent">{p.ticket_id}</span>
          {cited && <span className="rounded-full bg-ai-soft px-2 py-px text-xs font-medium text-ai">Cited</span>}
          <span className="ml-auto flex items-center gap-1.5" title={`Cosine similarity ${p.similarity.toFixed(3)}`}>
            <span className="h-1.5 w-12 overflow-hidden rounded-full bg-surface-3"><span className="block h-full rounded-full bg-accent" style={{ width: pct(Math.max(0, Math.min(1, p.similarity))) }} /></span>
            <span className="tabular font-mono text-xs font-semibold text-ink-2">{p.similarity.toFixed(2)}</span>
          </span>
        </div>
        <p className="mt-1.5 text-sm font-medium leading-snug text-ink">{p.subject || '(no subject)'}</p>
        <p className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-muted">
          <LangChip code={p.language} />
          {cross && <span className="rounded-full bg-accent-soft px-2 py-px text-xs font-medium text-accent" title="Retrieved across languages: this past ticket is in a different language than the new one">Cross-lingual</span>}
        </p>
        {(p.type || p.queue || p.priority) && (
          <p className="mt-1 text-xs text-muted">{[p.type, p.queue, p.priority && `${PRIORITY_LABEL[p.priority as Priority] ?? p.priority} priority`].filter(Boolean).join(', ')}</p>
        )}
        <p className={`mt-2 text-[13px] leading-relaxed text-ink-2 ${open ? '' : 'line-clamp-3'}`}><span className="font-medium text-ink">Resolution: </span>{open ? p.answer : p.answer_snippet}</p>
        <span className="mt-1.5 inline-block text-xs font-medium text-accent">{open ? 'Show less' : 'Show full answer'}</span>
      </button>
      {open && (
        <div className="space-y-2 border-t border-line px-3.5 py-3 text-xs">
          <p className="text-muted"><span className="font-medium text-ink-2">Original issue: </span>{p.body_snippet}</p>
          {p.tags.length > 0 && <p className="text-muted">Tags: {p.tags.join(', ')}</p>}
          <button onClick={onHide} className="font-medium text-muted hover:text-ink hover:underline">Not relevant to this ticket</button>
        </div>
      )}
    </li>
  )
}
