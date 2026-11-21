import { useEffect, useMemo, useRef, useState } from 'react'
import { BurstBanner } from '../../components/BurstBanner'
import { MetricsStrip } from '../../components/MetricsStrip'
import { Avatar, Button, EmptyState, Icon, Kbd, LangChip, PriorityBadge, type IconName } from '../../components/ui'
import { band, duration, PRIORITY_LABEL, pct, sla, STATUS_LABEL } from '../../lib/format'
import { isTyping } from '../../lib/router'
import { useBurstReset } from '../../lib/useBurstReset'
import { decision, DECISION_COPY, DECISION_ORDER, isEscalated, isOpen, minConfidence, riskSort, waitingMs, type Decision } from '../../lib/ticket'
import { useNow, useStore } from '../../store'
import { PRIORITIES, QUEUES, type Ticket, type WorkflowStatus } from '../../types'
import BurstScenarioDialog from './BurstScenarioDialog'

type View = 'inbox' | 'escalated' | 'resolved'

const VIEW_COPY: Record<View, { title: string; description: string }> = {
  inbox: { title: 'Inbox', description: 'Every open ticket, ordered by risk. Critical incidents always come first.' },
  escalated: { title: 'Escalated', description: 'Tickets the safety check routed to an engineer or to human review, with the reason why.' },
  resolved: { title: 'Resolved', description: 'Closed conversations and how they were answered.' },
}

const DECISION_ICON: Record<Decision, IconName> = { critical: 'siren', review: 'eye', ready: 'shieldCheck', pending: 'circleDashed' }
const DECISION_CLS: Record<Decision, string> = { critical: 'text-oncall', review: 'text-review', ready: 'text-auto', pending: 'text-muted' }

export default function Inbox({ view, onTest }: { view: View; onTest: () => void }) {
  const { tickets, burstClearedAt } = useStore()
  const now = useNow()
  const resetBurst = useBurstReset()
  const [resetting, setResetting] = useState(false)
  const [burstOpen, setBurstOpen] = useState(false)
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
  // Live burst = the newest active burst flag raised since the last "Reset burst".
  const burst = open
    .filter((t) => t.triage?.burst.active && Date.parse(t.created_at) > burstClearedAt)
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0]?.triage?.burst
  const burstTickets = burst ? open.filter((t) => t.triage?.burst.active && t.triage.burst.label === burst.label && Date.parse(t.created_at) > burstClearedAt) : []
  // One incident card per burst: keep the oldest unacknowledged member, fold the rest into the banner.
  const burstIds = new Set(burstTickets.map((t) => t.id))
  const unackBurst = unackCritical.filter((t) => burstIds.has(t.id)).sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at))
  const criticalCards = unackCritical.filter((t) => !burstIds.has(t.id) || t === unackBurst[0])
  const folded = Math.max(0, unackBurst.length - 1)
  const onResetBurst = async () => { setResetting(true); await resetBurst(); setResetting(false) }
  const longest = Math.max(0, ...open.map((t) => waitingMs(t, now)))
  const escalatedCritical = scoped.filter((t) => decision(t) === 'critical').length
  const escalatedReview = scoped.filter((t) => decision(t) === 'review').length

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-[1400px] px-4 pb-12 pt-8 sm:px-8">
        {/* Page header */}
        <header className="flex flex-wrap items-end gap-x-6 gap-y-3">
          <div className="min-w-0">
            <h1 className="text-[40px] leading-[1.1] text-ink">{VIEW_COPY[view].title}</h1>
            <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-muted">{VIEW_COPY[view].description}</p>
            {view === 'escalated' && (
              <p className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm">
                <span className="inline-flex items-center gap-1.5 font-medium text-oncall"><Icon name="siren" className="h-4 w-4" /><span className="tabular">{escalatedCritical}</span> with on-call</span>
                <span className="inline-flex items-center gap-1.5 font-medium text-review"><Icon name="eye" className="h-4 w-4" /><span className="tabular">{escalatedReview}</span> awaiting human review</span>
              </p>
            )}
          </div>
          <div className="ml-auto flex items-center gap-4 pb-1">
          {view !== 'resolved' && <Button size="sm" icon="zap" onClick={() => setBurstOpen(true)}>Run burst scenario</Button>}
          <div className="hidden items-center gap-4 text-xs text-muted md:flex">
            <span className="inline-flex items-center gap-1"><Kbd>J</Kbd><Kbd>K</Kbd><span className="ml-1">move</span></span>
            <span className="inline-flex items-center gap-1"><Kbd>↵</Kbd><span className="ml-1">open</span></span>
            <span className="inline-flex items-center gap-1"><Kbd>/</Kbd><span className="ml-1">search</span></span>
          </div>
          </div>
        </header>

        {/* Attention: what must not get buried */}
        {view !== 'resolved' && (unackCritical.length > 0 || burst) && (
          <div className="mt-8 space-y-3">
            {burst && (
              <BurstBanner burst={burst} onReset={onResetBurst} resetting={resetting}>
                {folded > 0 && <span className="text-[13px] font-medium">+{folded} more not acknowledged</span>}
                <Button size="sm" onClick={() => setQ('VPN')} className="border-transparent bg-on-route text-oncall hover:opacity-90">Show related tickets</Button>
              </BurstBanner>
            )}
            {criticalCards.map((t) => (
              <a key={t.id} href={`#/${view}/${t.id}`}
                className="group flex flex-wrap items-center gap-x-4 gap-y-3 rounded-2xl border border-oncall/25 bg-oncall-soft px-4 py-4 transition-colors hover:border-oncall/45 sm:px-5">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-oncall text-on-route"><Icon name="siren" className="h-5 w-5" /></span>
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-x-2 text-[13px] font-semibold text-oncall">
                    Critical incident
                    <span className="rounded-full bg-oncall px-2 py-px text-xs font-semibold text-on-route">Not acknowledged</span>
                  </p>
                  <p className="mt-0.5 truncate text-[15px] font-medium text-ink" title={t.translation?.subject ?? (t.subject || t.body)}>{t.translation?.subject ?? (t.subject || `${t.body.slice(0, 60)}…`)}</p>
                  <p className="mt-0.5 flex flex-wrap gap-x-4 text-[13px] text-ink-2">
                    <span>{t.requester.org}</span>
                    <span className="tabular">Waiting {duration(waitingMs(t, now))}</span>
                    <span className="font-mono text-xs text-muted">{t.id}</span>
                  </p>
                </div>
                <span className="inline-flex h-10 items-center gap-1.5 rounded-full bg-primary px-4 text-sm font-medium text-on-primary transition-colors group-hover:bg-primary-hover">
                  Open incident <Icon name="chevronRight" className="h-4 w-4" />
                </span>
              </a>
            ))}
          </div>
        )}

        {/* Holdout metrics (C.6): the offline evaluation, separate from this session's tickets */}
        {view === 'inbox' && <div className="mt-8"><MetricsStrip /></div>}

        {/* Summary */}
        {view === 'inbox' && (
          <dl className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <Stat label="Open tickets" value={open.length} icon="inbox" />
            <Stat label="Critical incidents" value={open.filter((t) => decision(t) === 'critical').length} tone="oncall" icon="siren" />
            <Stat label="Need human review" value={open.filter((t) => decision(t) === 'review').length} tone="review" icon="eye" />
            <Stat label="Ready to respond" value={open.filter((t) => decision(t) === 'ready').length} tone="auto" icon="shieldCheck" />
            <Stat label="Longest wait" value={duration(longest)} icon="clock" />
          </dl>
        )}

        {/* Toolbar */}
        <div className="mt-8 flex flex-wrap items-center gap-2">
          <label className="relative min-w-0 flex-1 sm:max-w-xs">
            <span className="sr-only">Search tickets</span>
            <Icon name="search" className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input id="inbox-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search tickets"
              className="h-9 w-full rounded-full border border-line bg-surface-2 pl-10 pr-4 text-sm text-ink transition-colors hover:border-ink-2/30 focus:border-accent focus:outline-none focus-visible:outline-none focus:ring-3 focus:ring-accent/15" />
          </label>
          <Filter label="Priority" value={prio} onChange={setPrio} options={PRIORITIES.map((p) => [p, PRIORITY_LABEL[p]])} />
          <Filter label="Queue" value={queue} onChange={setQueue} options={QUEUES.map((x) => [x, x])} />
          <Filter label="Language" value={lang} onChange={setLang} options={[['en', 'English'], ['de', 'German']]} />
          <Filter label="Status" value={status} onChange={setStatus} options={(Object.keys(STATUS_LABEL) as WorkflowStatus[]).filter((s) => (view === 'resolved') === (s === 'resolved' || s === 'closed')).map((s) => [s, STATUS_LABEL[s]])} />
          {filtersOn && <button onClick={clear} className="h-9 rounded-full px-3.5 text-sm font-medium text-accent hover:bg-accent-soft">Clear filters</button>}
          <span className="tabular ml-auto text-[13px] text-muted">{filtered.length} of {scoped.length} tickets</span>
        </div>

        {/* List */}
        <div ref={listRef} className="mt-4 overflow-hidden rounded-2xl border border-line bg-surface shadow-soft">
          <div className={`hidden ${COLS} gap-x-4 border-b border-line px-5 py-2.5 text-xs font-medium text-muted xl:grid`} aria-hidden>
            <span>Priority</span><span>Ticket</span><span>Type</span><span>Queue</span><span>Lang</span><span>Confidence</span><span>Decision</span><span /><span className="text-right">Waiting</span>
          </div>
          {filtered.length === 0 ? (
            filtersOn ? (
              <EmptyState icon="search" title="No tickets match these filters"><button className="font-medium text-accent hover:underline" onClick={clear}>Clear filters</button></EmptyState>
            ) : (
              <EmptyState icon="checkCircle" title={view === 'resolved' ? 'Nothing resolved yet' : 'All caught up'}>
                {view === 'resolved' ? 'Resolved tickets will appear here.' : 'No open tickets need your attention right now.'}
                {view !== 'resolved' && <div className="mt-4"><Button size="sm" icon="plus" onClick={onTest}>Test a ticket</Button></div>}
              </EmptyState>
            )
          ) : (
            groups.map((g) => (
              <section key={g.key} aria-label={g.key === 'all' ? 'Tickets' : DECISION_COPY[g.key as Decision].group}>
                {g.key !== 'all' && (
                  <header className="flex items-center gap-2.5 border-b border-line bg-surface-2 px-5 py-2.5">
                    <Icon name={DECISION_ICON[g.key as Decision]} className={`h-4 w-4 ${DECISION_CLS[g.key as Decision]}`} />
                    <h2 className="text-[13px] font-semibold text-ink">{DECISION_COPY[g.key as Decision].group}</h2>
                    <span className="tabular rounded-full bg-surface-3 px-2 py-px text-xs font-medium text-ink-2">{g.items.length}</span>
                    <span className="hidden min-w-0 truncate text-[13px] text-muted md:inline">{DECISION_COPY[g.key as Decision].hint}</span>
                  </header>
                )}
                <ul>{g.items.map((t) => <Row key={t.id} t={t} view={view} now={now} />)}</ul>
              </section>
            ))
          )}
        </div>
      </div>
      {burstOpen && <BurstScenarioDialog onClose={() => setBurstOpen(false)} />}
    </div>
  )
}

const COLS = 'xl:grid-cols-[100px_minmax(0,1fr)_84px_156px_56px_112px_128px_32px_76px]'

function Stat({ label, value, tone, icon }: { label: string; value: number | string; tone?: 'oncall' | 'review' | 'auto'; icon: IconName }) {
  const color = tone === 'oncall' ? 'text-oncall' : tone === 'review' ? 'text-review' : tone === 'auto' ? 'text-auto' : 'text-ink-2'
  return (
    <div className="min-w-0 rounded-2xl border border-line bg-surface p-4 shadow-soft">
      <dt className="flex items-center gap-2.5 text-[13px] text-ink-2">
        <span className={`inline-flex h-7 w-7 items-center justify-center rounded-full bg-surface-3 ${color}`}><Icon name={icon} className="h-3.5 w-3.5" /></span>
        {label}
      </dt>
      <dd className="numeral mt-4 text-[40px] text-ink">{value}</dd>
    </div>
  )
}

function Filter({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  const active = value !== 'all'
  const current = options.find(([v]) => v === value)?.[1]
  return (
    <label className={`relative inline-flex h-9 items-center rounded-full border text-sm transition-colors ${active ? 'border-transparent bg-primary' : 'border-line bg-surface-2 hover:border-line-strong'}`}>
      <span className="pointer-events-none flex items-center gap-1.5 pl-3 pr-8">
        <span className={active ? 'text-on-primary/70' : 'text-muted'}>{label}</span>
        <span className={active ? 'font-medium text-on-primary' : 'font-medium text-ink'}>{current ?? 'All'}</span>
      </span>
      <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={label} className="absolute inset-0 cursor-pointer appearance-none opacity-0">
        <option value="all">{label}: All</option>
        {options.map(([v, l]) => <option key={v} value={v}>{label}: {l}</option>)}
      </select>
      <Icon name="chevronDown" className={`pointer-events-none absolute right-3 h-4 w-4 ${active ? 'text-on-primary' : 'text-muted'}`} />
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
  const confBand = conf !== null ? band(conf) : null
  return (
    <li className="border-b border-line last:border-b-0">
      <a
        data-row
        href={`#/${view}/${t.id}`}
        className={`relative grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-2 px-5 py-3.5 transition-colors hover:bg-surface-2 focus-visible:bg-accent-soft focus-visible:outline-none ${COLS} xl:items-center ${unassignedCritical ? 'before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:bg-oncall' : ''}`}
      >
        <span className="order-1 xl:order-none"><PriorityBadge priority={t.priority} /></span>
        <span className="order-3 col-span-2 min-w-0 xl:order-none xl:col-span-1">
          <span className={`block text-[15px] leading-snug text-ink line-clamp-2 xl:line-clamp-1 ${t.status === 'new' ? 'font-semibold' : 'font-medium'}`} title={subject}>
            {subject}
          </span>
          <span className="mt-1 flex min-w-0 items-center gap-x-3 text-[13px] text-muted">
            <span className="truncate">{t.requester.name}, {t.requester.org}</span>
            <span className="shrink-0 font-mono text-xs">{t.id}</span>
            {t.translation && <span className="hidden min-w-0 truncate 2xl:inline" title={t.translation.subject}>“{t.translation.subject}”</span>}
          </span>
        </span>
        <span className="hidden text-[13px] text-ink-2 xl:block">{t.type}</span>
        <span className="hidden truncate text-[13px] text-ink-2 xl:block" title={t.queue}>{t.queue}</span>
        <span className="hidden xl:block">{t.triage && <LangChip code={t.triage.language.code} />}</span>
        <span className="hidden xl:block">
          {conf !== null && confBand && (
            <span className="block" title="Lowest confidence across type, queue and priority">
              <span className="flex items-baseline justify-between gap-2 text-[13px]">
                <span className={confBand === 'Low' ? 'font-medium text-review' : 'text-ink-2'}>{confBand}</span>
                <span className="tabular font-mono text-xs text-muted">{pct(conf)}</span>
              </span>
              <span className="mt-1 block h-1 overflow-hidden rounded-full bg-surface-3">
                <span className={`block h-full rounded-full ${confBand === 'Low' ? 'bg-review' : 'bg-ink-2/40'}`} style={{ width: pct(conf) }} />
              </span>
            </span>
          )}
        </span>
        <span className="order-2 flex items-center justify-end gap-2 xl:order-none xl:block">
          <span className={`inline-flex items-center gap-1.5 text-[13px] font-medium ${DECISION_CLS[d]}`}>
            <Icon name={DECISION_ICON[d]} className="h-4 w-4" />{DECISION_COPY[d].short}
          </span>
          <span className={`block text-xs xl:mt-0.5 ${d === 'critical' && t.acknowledged_by ? 'text-auto' : 'text-muted'}`}>
            {d === 'critical' && t.acknowledged_by ? 'Acknowledged' : unassignedCritical ? 'Not acknowledged' : STATUS_LABEL[t.status]}
          </span>
        </span>
        <span className="hidden xl:flex xl:justify-center" title={t.assignee ?? 'Unassigned'}>
          {t.assignee ? <Avatar name={t.assignee} /> : unassignedCritical ? <Icon name="alertCircle" className="h-5 w-5 text-oncall" label="Unassigned critical ticket" /> : <span className="inline-block h-6 w-6 rounded-full border border-dashed border-line-strong" aria-label="Unassigned" />}
        </span>
        <span className={`tabular order-4 col-span-2 font-mono text-[13px] xl:order-none xl:col-span-1 xl:text-right ${waitCls}`}>
          <span className="font-sans text-muted xl:hidden">{t.assignee ? `${t.assignee}, ` : unassignedCritical ? 'Unassigned, ' : ''}{isOpen(t) && wait > 0 ? 'waiting ' : ''}</span>
          {!isOpen(t) ? <span className="font-sans">{STATUS_LABEL[t.status]}</span> : wait === 0 ? <span className="font-sans">Replied</span> : duration(wait)}
          {isOpen(t) && s.state === 'breached' && <span className="sr-only"> SLA breached</span>}
        </span>
      </a>
    </li>
  )
}
