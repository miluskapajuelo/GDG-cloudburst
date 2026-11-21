import { useEffect, useState } from 'react'
import { Avatar, Icon, Kbd, type IconName } from './components/ui'
import { buildTickets } from './data/mockBackend'
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
        <StoreProvider seed={buildTickets}>
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
      <a href="#/inbox" className="flex h-14 items-center gap-2.5 px-5">
        <img src="/favicon.svg" alt="" className="h-6 w-6" />
        <span className="font-display text-[18px] font-semibold tracking-[-0.01em] text-brand">SentinelDesk</span>
      </a>
      <nav className="flex-1 space-y-0.5 px-3 pb-3 pt-2">
        {items.map((it) => (
          <a
            key={it.id}
            href={`#/${it.id}`}
            aria-current={section === it.id ? 'page' : undefined}
            className={`group flex h-9 items-center gap-3 rounded-lg px-2.5 text-sm transition-colors ${section === it.id ? 'bg-accent-soft font-medium text-ink' : 'text-ink-2 hover:bg-surface-3 hover:text-ink'}`}
          >
            <Icon name={it.icon} className={`h-4 w-4 ${section === it.id ? 'text-accent' : 'text-muted group-hover:text-ink-2'}`} />
            <span className="flex-1">{it.label}</span>
            {it.count !== undefined && (
              <span
                className={`tabular min-w-6 rounded-md px-1.5 py-px text-center font-mono text-xs font-medium ${it.alert ? 'bg-oncall text-on-route' : section === it.id ? 'text-ink-2' : 'text-muted'}`}
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
        <a href="#/settings" className="flex items-center gap-3 rounded-lg px-2.5 py-2 transition-colors hover:bg-surface-3">
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
    <header className="glass-strong relative z-20 flex h-14 shrink-0 items-center gap-3 border-b border-line bg-chrome px-3 sm:px-6">
      <button className="rounded-lg p-2 text-ink-2 hover:bg-surface-3 lg:hidden" aria-label="Open navigation" onClick={onMenu}>
        <Icon name="layers" className="h-5 w-5" />
      </button>
      <button
        onClick={() => { navigate('/inbox'); requestAnimationFrame(() => document.getElementById('inbox-search')?.focus()) }}
        className="flex h-9 min-w-0 flex-1 items-center gap-2.5 rounded-lg border border-line bg-surface-2 px-3 text-sm text-muted transition-colors hover:border-line-strong hover:text-ink-2 sm:max-w-md"
      >
        <Icon name="search" className="h-4 w-4" />
        <span className="truncate">Search tickets, customers, IDs</span>
        <Kbd className="ml-auto hidden sm:inline">⌘K</Kbd>
      </button>
      <div className="ml-auto flex items-center gap-3 sm:gap-4">
        <HealthDot />
        <button onClick={onTest} className="inline-flex h-9 items-center gap-2 rounded-lg bg-accent px-3.5 text-sm font-medium text-on-accent transition-colors hover:bg-accent-strong">
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
        : ['bg-oncall', 'API offline', 'The triage API is not reachable. You are viewing demo data, and new tickets use a local fallback marked as mock.']
  return (
    <span className="hidden items-center gap-2 text-xs font-medium text-muted sm:inline-flex" title={title} role="status">
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden />
      {text}
    </span>
  )
}
