import { useStore } from '../store'
import { Icon, routeKey, ROUTE_STYLE } from './ui'

/** Task C.6: the last 10 triage results in memory. Clicking one opens that result again. */
export function RecentResults({ activeId }: { activeId?: string }) {
  const { history, get } = useStore()
  const items = history.map(get).filter((t) => t !== undefined)
  return (
    <section aria-labelledby="recent-title" className="flex min-h-0 flex-col border-t border-line px-3 pt-3">
      <h2 id="recent-title" className="px-3 pb-1.5 text-xs font-medium uppercase tracking-wide text-muted">Recent results</h2>
      {items.length === 0 ? (
        <p className="px-3 pb-3 text-xs leading-relaxed text-muted">Tickets you triage appear here, newest first.</p>
      ) : (
        <ol className="min-h-0 flex-1 space-y-0.5 overflow-y-auto pb-3">
          {items.map((t) => {
            const esc = t.triage?.escalation
            const s = ROUTE_STYLE[routeKey(esc?.route ?? null)]
            const label = t.subject.trim() || t.body.replace(/\s+/g, ' ').trim()
            const text = label.length > 40 ? `${label.slice(0, 40)}…` : label
            return (
              <li key={t.id}>
                <a href={`#/inbox/${t.id}`} aria-current={activeId === t.id ? 'page' : undefined} title={`${esc?.badge ?? ''}: ${label}`}
                  className={`flex items-start gap-2.5 rounded-xl px-3 py-1.5 text-xs transition-colors ${activeId === t.id ? 'bg-surface-3 text-ink' : 'text-ink-2 hover:bg-surface-3/60 hover:text-ink'}`}>
                  {/* Shape + colour, never colour alone: the same icon as the decision badge. */}
                  <span aria-hidden className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full ${s.solid}`}><Icon name={s.icon} className="h-2.5 w-2.5" /></span>
                  <span className="min-w-0 flex-1">
                    <span className="sr-only">{esc?.badge ?? 'Not triaged'}: </span>
                    <span className="line-clamp-2 break-words leading-snug">{text}</span>
                    <time dateTime={t.created_at} className="tabular mt-0.5 block text-[11px] text-muted">{new Date(t.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time>
                  </span>
                </a>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}
