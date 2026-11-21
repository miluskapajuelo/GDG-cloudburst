import { useEffect, useState } from 'react'
import { Avatar, Icon, Kbd, type IconName } from './components/ui'
import { PrefsProvider } from './lib/prefs'
import { AGENT } from './lib/session'
import { isEscalated, isOpen } from './lib/ticket'
import { navigate, useRoute } from './lib/router'
import { useHealth } from './lib/useApi'
import { StoreProvider, ToastProvider, useStore } from './store'
import Analytics from './views/analytics/Analytics'
import Inbox from './views/inbox/Inbox'
import TestTicketDialog from './views/inbox/TestTicketDialog'
import TicketDetail from './views/inbox/TicketDetail'
import Settings from './views/settings/Settings'

export default function App() {
  const route = useRoute()
  useEffect(() => {
    if (!route.length) navigate('/inbox')
  }, [route.length])

  return (
    <ToastProvider>
      <PrefsProvider>
        <StoreProvider seed={() => []}>
          <Workspace route={route} />
        </StoreProvider>
      </PrefsProvider>
    </ToastProvider>
  )
}

type Section = 'inbox' | 'escalated' | 'resolved' | 'analytics' | 'settings'

function Workspace({ route }: { route: string[] }) {
  const section = (route[0] ?? 'inbox') as Section
  const ticketId = route[1]
  const [navOpen, setNavOpen] = useState(false)
  const [testOpen, setTestOpen] = useState(false)

  useEffect(() => setNavOpen(false), [section, ticketId])
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        if (section !== 'inbox' || ticketId) navigate('/inbox')
        requestAnimationFrame(() => document.getElementById('inbox-search')?.focus())
      }
    }
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  }, [section, ticketId])

  const listSection = section === 'inbox' || section === 'escalated' || section === 'resolved'

  return (
    <div className="flex h-dvh">
      <a href="#main" className="sr-only-focusable fixed left-2 top-2 z-50 rounded-full bg-accent px-4 py-2 text-on-accent">Skip to content</a>
      {navOpen && <div className="fixed inset-0 z-30 bg-scrim backdrop-blur-[2px] lg:hidden" onClick={() => setNavOpen(false)} aria-hidden />}
      <Sidebar section={section} open={navOpen} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onMenu={() => setNavOpen(true)} onTest={() => setTestOpen(true)} />
        <main id="main" className="min-h-0 flex-1 overflow-hidden">
          {listSection && ticketId ? (
            <TicketDetail key={ticketId} id={ticketId} section={section} />
          ) : listSection ? (
            <Inbox view={section as 'inbox' | 'escalated' | 'resolved'} onTest={() => setTestOpen(true)} />
          ) : section === 'analytics' ? (
            <Analytics />
          ) : (
            <Settings />
          )}
        </main>
      </div>
      {testOpen && <TestTicketDialog onClose={() => setTestOpen(false)} />}
    </div>
  )
}

function Sidebar({ section, open }: { section: Section; open: boolean }) {
  const { tickets } = useStore()
  const openCount = tickets.filter(isOpen).length
  const escalated = tickets.filter((t) => isOpen(t) && isEscalated(t)).length
  const critical = tickets.filter((t) => isOpen(t) && t.triage?.escalation.route === 'ON_CALL' && !t.acknowledged_by).length
  const items: { id: Section; label: string; icon: IconName; count?: number; alert?: boolean }[] = [
    { id: 'inbox', label: 'Inbox', icon: 'inbox', count: openCount },
    { id: 'escalated', label: 'Escalated', icon: 'siren', count: escalated, alert: critical > 0 },
    { id: 'resolved', label: 'Resolved', icon: 'checkCircle' },
    { id: 'analytics', label: 'Analytics', icon: 'chart' },
    { id: 'settings', label: 'Settings', icon: 'settings' },
  ]
  return (
    <aside
      aria-label="Main navigation"
      className={`fixed inset-y-0 left-0 z-40 glass-strong flex w-60 flex-col border-r border-line bg-chrome transition-transform lg:static lg:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}
    >
      <a href="#/inbox" className="flex h-16 items-center gap-2.5 px-5">
        <img src="/favicon.svg" alt="" className="h-6 w-6" />
        <span className="text-[16px] font-semibold tracking-[-0.015em] text-brand">SentinelDesk</span>
      </a>
      <nav className="flex-1 space-y-0.5 px-3 pb-3 pt-2">
        {items.map((it) => (
          <a
            key={it.id}
            href={`#/${it.id}`}
            aria-current={section === it.id ? 'page' : undefined}
            className={`group flex h-9 items-center gap-3 rounded-full px-3 text-sm transition-colors ${section === it.id ? 'bg-surface-3 font-medium text-ink' : 'text-ink-2 hover:bg-surface-3/60 hover:text-ink'}`}
          >
            <Icon name={it.icon} className={`h-4 w-4 ${section === it.id ? 'text-ink' : 'text-muted group-hover:text-ink-2'}`} />
            <span className="flex-1">{it.label}</span>
            {it.count !== undefined && (
              <span
                className={`tabular min-w-6 rounded-full px-1.5 py-px text-center text-xs font-medium ${it.alert ? 'bg-oncall text-on-route' : section === it.id ? 'text-ink-2' : 'text-muted'}`}
                title={it.alert ? 'Includes an unacknowledged critical incident' : undefined}
              >
                {it.count}
                {it.alert && <span className="sr-only">, includes an unacknowledged critical incident</span>}
              </span>
            )}
          </a>
        ))}
      </nav>
      <div className="border-t border-line p-3">
        <a href="#/settings" className="flex items-center gap-3 rounded-full py-1.5 pl-1.5 pr-3 transition-colors hover:bg-surface-3">
          <Avatar name={AGENT.name} size="md" />
          <span className="min-w-0 flex-1 leading-tight">
            <span className="block truncate text-sm font-medium text-ink">{AGENT.name}</span>
            <span className="block truncate text-xs text-muted">{AGENT.role}</span>
          </span>
        </a>
      </div>
    </aside>
  )
}

function TopBar({ onMenu, onTest }: { onMenu: () => void; onTest: () => void }) {
  return (
    <header className="glass-strong relative z-20 flex h-16 shrink-0 items-center gap-3 border-b border-line bg-chrome px-3 sm:px-6">
      <button className="rounded-full p-2 text-ink-2 hover:bg-surface-3 lg:hidden" aria-label="Open navigation" onClick={onMenu}>
        <Icon name="layers" className="h-5 w-5" />
      </button>
      <Greeting />
      <button
        onClick={() => { navigate('/inbox'); requestAnimationFrame(() => document.getElementById('inbox-search')?.focus()) }}
        className="flex h-10 min-w-0 flex-1 items-center gap-2.5 rounded-full border border-line bg-surface-2 px-4 text-sm text-muted transition-colors hover:border-line-strong hover:text-ink-2 sm:max-w-sm lg:ml-auto"
      >
        <Icon name="search" className="h-4 w-4" />
        <span className="truncate">Search tickets, customers, IDs</span>
        <Kbd className="ml-auto hidden sm:inline">⌘K</Kbd>
      </button>
      <div className="ml-auto flex items-center gap-2 sm:gap-3 lg:ml-0">
        <HealthDot />
        <Bell />
        <button onClick={onTest} className="inline-flex h-10 items-center gap-2 rounded-full bg-primary px-4 text-sm font-medium text-on-primary transition-colors hover:bg-primary-hover">
          <Icon name="plus" className="h-4 w-4" />
          <span className="hidden sm:inline">Test a ticket</span>
        </button>
      </div>
    </header>
  )
}

export function HealthDot() {
  const h = useHealth()
  const [dot, text, title] =
    h.state === 'online'
      ? ['bg-auto', h.health.mock ? 'Live (mock)' : 'Live', `Model ${h.health.llm_model}, ${h.health.index_size.toLocaleString()} past tickets indexed`]
      : h.state === 'checking'
        ? ['bg-review', 'Connecting', 'Checking the triage service']
        : ['bg-oncall', 'API offline', 'The triage API is not reachable. Start it with: uvicorn api.main:app --port 8000']
  return (
    <span className="hidden items-center gap-2 text-xs font-medium text-muted sm:inline-flex" title={title} role="status">
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden />
      {text}
    </span>
  )
}

/** "Good evening, Lucía" with today's date: a calm anchor for a busy shift. */
function Greeting() {
  const now = new Date()
  const h = now.getHours()
  const part = h < 5 ? 'Good night' : h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
  return (
    <div className="hidden min-w-0 items-center gap-3 lg:flex">
      <Avatar name={AGENT.name} size="md" />
      <div className="min-w-0 leading-tight">
        <p className="truncate text-sm font-medium text-ink">{part}, {AGENT.name.split(' ')[0]}</p>
        <p className="truncate text-xs text-muted">{now.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })}</p>
      </div>
    </div>
  )
}

/** Round bell with a coral dot while an on-call incident is unacknowledged. */
function Bell() {
  const { tickets } = useStore()
  const pending = tickets.filter((t) => isOpen(t) && t.triage?.escalation.route === 'ON_CALL' && !t.acknowledged_by).length
  return (
    <a href="#/escalated" className="relative inline-flex h-10 w-10 items-center justify-center rounded-full border border-line bg-surface-2 text-ink-2 transition-colors hover:text-ink"
      aria-label={pending ? `${pending} unacknowledged critical incident${pending > 1 ? 's' : ''}` : 'No unacknowledged incidents'}>
      <Icon name="bell" className="h-4 w-4" />
      {pending > 0 && <span aria-hidden className="absolute right-2 top-2 h-2 w-2 rounded-full bg-oncall ring-2 ring-surface-2" />}
    </a>
  )
}
