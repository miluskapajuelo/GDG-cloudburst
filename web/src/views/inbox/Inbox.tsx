import { useEffect, useMemo, useRef, useState } from 'react'
import { Avatar, Button, EmptyState, Icon, Kbd, LangChip, PriorityBadge, type IconName } from '../../components/ui'
import { band, duration, PRIORITY_LABEL, pct, sla, STATUS_LABEL } from '../../lib/format'
import { isTyping } from '../../lib/router'
import { decision, DECISION_COPY, DECISION_ORDER, isEscalated, isOpen, minConfidence, riskSort, waitingMs, type Decision } from '../../lib/ticket'
import { useNow, useStore } from '../../store'
import { PRIORITIES, QUEUES, type Ticket, type WorkflowStatus } from '../../types'

type View = 'inbox' | 'escalated' | 'resolved'

const VIEW_COPY: Record<View, { title: string; description: string }> = {
  inbox: { title: 'Inbox', description: 'Every open ticket, ordered by risk. Critical incidents always come first.' },
  escalated: { title: 'Escalated', description: 'Tickets the safety check routed to an engineer or to human review, with the reason why.' },
  resolved: { title: 'Resolved', description: 'Closed conversations and how they were answered.' },
}

const DECISION_ICON: Record<Decision, IconName> = { critical: 'siren', review: 'eye', ready: 'shieldCheck', pending: 'circleDashed' }
const DECISION_CLS: Record<Decision, string> = { critical: 'text-oncall', review: 'text-review', ready: 'text-auto', pending: 'text-muted' }

export default function Inbox({ view, onTest }: { view: View; onTest: () => void }) {
  const { tickets } = useStore()
  const now = useNow()
  const [q, setQ] = useState('')
  const [prio, setPrio] = useState('all')
  const [queue, setQueue] = useState('all')
  const [lang, setLang] = useState('all')
  const [status, setStatus] = useState('all')
  const listRef = useRef<HTMLDivElement>(null)

  const scoped = useMemo(
    () => tickets.filter((t) => (view === 'resolved' ? !isOpen(t) : view === 'escalated' ? isOpen(t) && isEscalated(t) : isOpen(t))),
    [tickets, view],
  )
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return scoped
      .filter((t) => prio === 'all' || t.priority === prio)
      .filter((t) => queue === 'all' || t.queue === queue)
      .filter((t) => lang === 'all' || t.triage?.language.code === lang)
      .filter((t) => status === 'all' || t.status === status)
      .filter((t) => !needle || [t.id, t.subject, t.body, t.requester.name, t.requester.org, t.queue, t.type].join(' ').toLowerCase().includes(needle))
      .sort(view === 'resolved' ? (a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at) : riskSort(now))
  }, [scoped, q, prio, queue, lang, status, view, now])

  const groups = view === 'resolved'
    ? [{ key: 'all', items: filtered }]
    : DECISION_ORDER.map((d) => ({ key: d, items: filtered.filter((t) => decision(t) === d) })).filter((g) => g.items.length)

  const filtersOn = q || prio !== 'all' || queue !== 'all' || lang !== 'all' || status !== 'all'
  const clear = () => { setQ(''); setPrio('all'); setQueue('all'); setLang('all'); setStatus('all') }

  // J/K moves focus through rows, Enter opens, / focuses search.
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (isTyping(e) || e.metaKey || e.ctrlKey || e.altKey) return
      const rows = [...(listRef.current?.querySelectorAll<HTMLAnchorElement>('a[data-row]') ?? [])]
      const i = rows.indexOf(document.activeElement as HTMLAnchorElement)
      if (e.key === 'j' || e.key === 'k') {
        e.preventDefault()
        const next = rows[e.key === 'j' ? Math.min(i + 1, rows.length - 1) : Math.max(i - 1, 0)] ?? rows[0]
        next?.focus()
      } else if (e.key === '/') {
        e.preventDefault()
        document.getElementById('inbox-search')?.focus()
      }
    }
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  }, [])

  const open = tickets.filter(isOpen)
  const unackCritical = open.filter((t) => t.triage?.escalation.route === 'ON_CALL' && !t.acknowledged_by)
  const burst = open.find((t) => t.triage?.burst.active)?.triage?.burst
  const burstTickets = burst ? open.filter((t) => t.triage?.burst.active && t.triage.burst.label === burst.label) : []
  const longest = Math.max(0, ...open.map((t) => waitingMs(t, now)))

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-[1400px] px-4 py-6 sm:px-8">
        <div className="flex flex-wrap items-end gap-4">
          <div className="min-w-0">
            <h1 className="text-[30px] leading-tight font-semibold text-ink">{VIEW_COPY[view].title}</h1>
            <p className="mt-1 text-sm text-muted">{VIEW_COPY[view].description}</p>
          </div>
          <div className="ml-auto hidden items-center gap-3 text-xs text-muted md:flex">
            <span><Kbd>J</Kbd><Kbd>K</Kbd> move</span>
            <span><Kbd>↵</Kbd> open</span>
            <span><Kbd>/</Kbd> search</span>
          </div>
        </div>

        {/* Attention: what must not get buried */}
        {view !== 'resolved' && (unackCritical.length > 0 || burst) && (
          <div className="mt-5 space-y-2">
            {unackCritical.map((t) => (
              <a key={t.id} href={`#/${view}/${t.id}`} className="group flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-oncall/30 bg-oncall-soft px-4 py-3 transition-colors hover:border-oncall/60">
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-oncall text-on-route"><Icon name="siren" /></span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-oncall">Critical incident · not yet acknowledged</p>
                  <p className="truncate text-sm text-ink">{t.translation?.subject ?? t.subject} <span className="text-muted">· {t.requester.org} · waiting {duration(waitingMs(t, now))}</span></p>
                </div>
                <span className="inline-flex items-center gap-1 text-sm font-medium text-oncall group-hover:underline">Open incident <Icon name="chevronRight" /></span>
              </a>
            ))}
            {burst && (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-line bg-surface px-4 py-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-md bg-review-soft text-review"><Icon name="zap" /></span>
                <div className="min-w-0 flex-1 text-sm">
                  <p className="font-semibold text-ink">Possible major incident: {burst.cluster_size} similar reports in {burst.window_minutes} minutes</p>
                  <p className="text-muted">“{burst.label}” · {burstTickets.map((t) => t.requester.org).join(', ')}</p>
                </div>
                <Button size="sm" onClick={() => setQ('VPN')}>Show related tickets</Button>
              </div>
            )}
          </div>
        )}

        {/* Summary */}
        {view === 'inbox' && (
          <dl className="glass mt-5 grid grid-cols-2 overflow-hidden rounded-2xl border border-line bg-surface shadow-soft sm:grid-cols-3 lg:grid-cols-5">
            <Stat label="Open tickets" value={open.length} />
            <Stat label="Critical incidents" value={open.filter((t) => decision(t) === 'critical').length} tone="oncall" icon="siren" />
            <Stat label="Need human review" value={open.filter((t) => decision(t) === 'review').length} tone="review" icon="eye" />
            <Stat label="Ready to respond" value={open.filter((t) => decision(t) === 'ready').length} tone="auto" icon="shieldCheck" />
            <Stat label="Longest wait" value={duration(longest)} icon="clock" />
          </dl>
        )}

        {/* Toolbar */}
        <div className="mt-5 flex flex-wrap items-center gap-2">
          <label className="relative min-w-0 flex-1 sm:max-w-xs">
            <span className="sr-only">Search tickets</span>
            <Icon name="search" className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted" />
            <input id="inbox-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" className="h-9 w-full rounded-md border border-line-strong bg-surface pl-8 pr-3 text-sm placeholder:text-muted" />
          </label>
          <Filter label="Priority" value={prio} onChange={setPrio} options={PRIORITIES.map((p) => [p, PRIORITY_LABEL[p]])} />
          <Filter label="Queue" value={queue} onChange={setQueue} options={QUEUES.map((x) => [x, x])} />
          <Filter label="Language" value={lang} onChange={setLang} options={[['en', 'English'], ['de', 'German']]} />
          <Filter label="Status" value={status} onChange={setStatus} options={(Object.keys(STATUS_LABEL) as WorkflowStatus[]).filter((s) => (view === 'resolved') === (s === 'resolved' || s === 'closed')).map((s) => [s, STATUS_LABEL[s]])} />
          {filtersOn && <button onClick={clear} className="h-9 rounded-md px-2.5 text-sm text-muted hover:bg-surface-3 hover:text-ink">Clear</button>}
          <span className="ml-auto text-xs text-muted">{filtered.length} of {scoped.length}</span>
        </div>

        {/* List */}
        <div ref={listRef} className="glass mt-4 overflow-hidden rounded-2xl border border-line bg-surface shadow-soft">
          <div className="hidden grid-cols-[96px_minmax(0,1fr)_96px_150px_52px_112px_124px_40px_80px] gap-x-4 border-b border-line bg-surface-2 px-4 py-2 text-[11px] font-medium uppercase tracking-wider text-muted xl:grid" aria-hidden>
            <span>Priority</span><span>Ticket</span><span>Type</span><span>Queue</span><span>Lang</span><span>Confidence</span><span>Decision</span><span /><span className="text-right">Waiting</span>
          </div>
          {filtered.length === 0 ? (
            filtersOn ? (
              <EmptyState icon="search" title="No tickets match these filters"><button className="text-accent hover:underline" onClick={clear}>Clear filters</button></EmptyState>
            ) : (
              <EmptyState icon="checkCircle" title={view === 'resolved' ? 'Nothing resolved yet' : 'All caught up'}>
                {view === 'resolved' ? 'Resolved tickets will appear here.' : 'No open tickets need your attention right now.'}
                {view !== 'resolved' && <div className="mt-3"><Button size="sm" icon="sparkle" onClick={onTest}>Test a ticket</Button></div>}
              </EmptyState>
            )
          ) : (
            groups.map((g) => (
              <section key={g.key} aria-label={g.key === 'all' ? 'Tickets' : DECISION_COPY[g.key as Decision].group}>
                {g.key !== 'all' && (
                  <header className="flex items-baseline gap-2 border-b border-line bg-surface-2/60 px-4 py-2">
                    <Icon name={DECISION_ICON[g.key as Decision]} className={`h-3.5 w-3.5 self-center ${DECISION_CLS[g.key as Decision]}`} />
                    <h2 className="text-xs font-semibold text-ink">{DECISION_COPY[g.key as Decision].group}</h2>
                    <span className="tabular text-xs text-muted">{g.items.length}</span>
                    <span className="hidden truncate text-xs text-muted sm:inline">· {DECISION_COPY[g.key as Decision].hint}</span>
                  </header>
                )}
                <ul>{g.items.map((t) => <Row key={t.id} t={t} view={view} now={now} />)}</ul>
              </section>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value, tone, icon }: { label: string; value: number | string; tone?: 'oncall' | 'review' | 'auto'; icon?: IconName }) {
  const color = tone === 'oncall' ? 'text-oncall' : tone === 'review' ? 'text-review' : tone === 'auto' ? 'text-auto' : 'text-muted'
  return (
    <div className="border-b border-r border-line px-4 py-3 last:border-r-0 lg:border-b-0">
      <dt className="flex items-center gap-1.5 text-xs text-muted">{icon && <Icon name={icon} className={`h-3.5 w-3.5 ${color}`} />}{label}</dt>
      <dd className="tabular mt-1 text-xl font-semibold text-ink">{value}</dd>
    </div>
  )
}

function Filter({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  const active = value !== 'all'
  return (
    <label className={`relative inline-flex h-9 items-center rounded-md border text-sm ${active ? 'border-accent/40 bg-accent-soft text-accent' : 'border-line-strong bg-surface text-ink-2'}`}>
      <span className="sr-only">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="h-full max-w-[11rem] cursor-pointer appearance-none truncate bg-transparent pl-3 pr-7 font-medium focus:outline-none">
        <option value="all">{label}: All</option>
        {options.map(([v, l]) => <option key={v} value={v}>{label}: {l}</option>)}
      </select>
      <Icon name="chevronDown" className="pointer-events-none absolute right-2 h-3.5 w-3.5 opacity-70" />
    </label>
  )
}

function Row({ t, view, now }: { t: Ticket; view: View; now: number }) {
  const d = decision(t)
  const conf = minConfidence(t)
  const wait = waitingMs(t, now)
  const s = sla(t, now)
  const waitCls = !isOpen(t) ? 'text-muted' : s.state === 'breached' ? 'text-oncall font-semibold' : s.state === 'at_risk' ? 'text-review font-semibold' : 'text-ink-2'
  const unassignedCritical = d === 'critical' && !t.acknowledged_by && isOpen(t)
  const subject = t.subject || t.body.slice(0, 80)
  return (
    <li className="border-b border-line last:border-b-0">
      <a
        data-row
        href={`#/${view}/${t.id}`}
        className={`relative grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1.5 px-4 py-3 transition-colors hover:bg-surface-2 focus-visible:bg-accent-soft focus-visible:outline-none xl:grid-cols-[96px_minmax(0,1fr)_96px_150px_52px_112px_124px_40px_80px] xl:items-center xl:py-2.5 ${d === 'critical' && isOpen(t) ? 'before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:bg-oncall' : ''}`}
      >
        <span className="order-1 xl:order-none"><PriorityBadge priority={t.priority} /></span>
        <span className="order-3 col-span-2 min-w-0 xl:order-none xl:col-span-1">
          <span className={`block truncate text-sm ${t.status === 'new' ? 'font-semibold text-ink' : 'font-medium text-ink'}`}>
            {subject}
          </span>
          <span className="block truncate text-xs text-muted">
            {t.requester.name} · {t.requester.org} <span className="font-mono">· {t.id}</span>
            {t.translation && <span className="ml-1 hidden text-muted sm:inline">· “{t.translation.subject}”</span>}
          </span>
        </span>
        <span className="hidden text-xs text-ink-2 xl:block">{t.type}</span>
        <span className="hidden truncate text-xs text-ink-2 xl:block" title={t.queue}>{t.queue}</span>
        <span className="hidden xl:block">{t.triage && <LangChip code={t.triage.language.code} />}</span>
        <span className="hidden xl:block">
          {conf !== null && (
            <span className="tabular text-xs" title="Lowest confidence across type, queue and priority">
              <span className={`font-medium ${band(conf) === 'Low' ? 'text-review' : 'text-ink-2'}`}>{band(conf)}</span> <span className="text-muted">{pct(conf)}</span>
            </span>
          )}
        </span>
        <span className="order-2 flex items-center justify-end gap-2 xl:order-none xl:block">
          <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${DECISION_CLS[d]}`}>
            <Icon name={DECISION_ICON[d]} className="h-3.5 w-3.5" />{DECISION_COPY[d].short}
          </span>
          <span className="block text-[11px] text-muted xl:mt-0.5">{d === 'critical' && t.acknowledged_by ? 'Acknowledged' : STATUS_LABEL[t.status]}</span>
        </span>
        <span className="hidden xl:block" title={t.assignee ?? 'Unassigned'}>
          {t.assignee ? <Avatar name={t.assignee} /> : unassignedCritical ? <Icon name="alertCircle" className="h-5 w-5 text-oncall" label="Unassigned critical ticket" /> : <span className="inline-block h-6 w-6 rounded-full border border-dashed border-line-strong" aria-label="Unassigned" />}
        </span>
        <span className={`tabular order-4 col-span-2 text-xs xl:order-none xl:col-span-1 xl:text-right ${waitCls}`}>
          <span className="xl:hidden text-muted">{t.assignee ? `${t.assignee} · ` : unassignedCritical ? 'Unassigned · ' : ''}</span>
          {!isOpen(t) ? STATUS_LABEL[t.status] : wait === 0 ? 'Replied' : duration(wait)}
          {isOpen(t) && s.state === 'breached' && <span className="sr-only"> SLA breached</span>}
        </span>
      </a>
    </li>
  )
}
