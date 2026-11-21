import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState, type ReactNode } from 'react'
import type { AuditEvent, Message, Ticket } from './types'

type Patch = Partial<Omit<Ticket, 'id' | 'messages' | 'audit'>>

type Action =
  | { t: 'add'; ticket: Ticket }
  | { t: 'replace'; ticket: Ticket }
  | { t: 'patch'; ids: string[]; patch: Patch; audit?: Omit<AuditEvent, 'id' | 'at' | 'actor'>; actor: string }
  | { t: 'message'; id: string; message: Message; patch?: Patch }

const newId = (p: string) => `${p}-${Math.random().toString(36).slice(2, 9)}`

function reducer(state: Ticket[], a: Action): Ticket[] {
  const now = new Date().toISOString()
  switch (a.t) {
    case 'add':
      return [a.ticket, ...state]
    case 'replace':
      return state.map((t) => (t.id === a.ticket.id ? a.ticket : t))
    case 'patch':
      return state.map((t) =>
        a.ids.includes(t.id)
          ? {
              ...t,
              ...a.patch,
              updated_at: now,
              audit: a.audit ? [...t.audit, { ...a.audit, id: newId('a'), at: now, actor: a.actor }] : t.audit,
            }
          : t,
      )
    case 'message':
      return state.map((t) =>
        t.id === a.id
          ? {
              ...t,
              ...a.patch,
              updated_at: now,
              messages: [...t.messages, a.message],
              audit:
                a.message.role === 'agent' && !a.message.internal
                  ? [...t.audit, { id: newId('a'), at: now, actor: a.message.author, kind: 'reply' as const, text: 'Public reply sent' }]
                  : t.audit,
            }
          : t,
      )
  }
}

interface Store {
  tickets: Ticket[]
  get: (id: string) => Ticket | undefined
  add: (t: Ticket) => void
  replace: (t: Ticket) => void
  patch: (ids: string | string[], patch: Patch, audit?: Omit<AuditEvent, 'id' | 'at' | 'actor'>, actor?: string) => void
  message: (id: string, m: Omit<Message, 'id' | 'at'>, patch?: Patch) => void
  nextId: () => string
  /** Time of the last "Reset burst". Burst flags on tickets created before it are no longer shown as live. */
  burstClearedAt: number
  clearBurst: () => void
  /** Ids of the last 10 tickets triaged in this session, newest first (in memory only). */
  history: string[]
}

const Ctx = createContext<Store | null>(null)

export function StoreProvider({ children, seed }: { children: ReactNode; seed: () => Ticket[] }) {
  const [tickets, dispatch] = useReducer(reducer, undefined, seed)
  const counter = useRef(24880)
  const [burstClearedAt, setBurstClearedAt] = useState(0)
  const [history, setHistory] = useState<string[]>([])
  const store = useMemo<Store>(
    () => ({
      tickets,
      get: (id) => tickets.find((t) => t.id === id),
      add: (ticket) => {
        dispatch({ t: 'add', ticket })
        setHistory((h) => [ticket.id, ...h.filter((x) => x !== ticket.id)].slice(0, 10))
      },
      replace: (ticket) => dispatch({ t: 'replace', ticket }),
      patch: (ids, patch, audit, actor = 'Support team') => dispatch({ t: 'patch', ids: Array.isArray(ids) ? ids : [ids], patch, audit, actor }),
      message: (id, m, patch) => dispatch({ t: 'message', id, message: { ...m, id: newId('m'), at: new Date().toISOString() }, patch }),
      nextId: () => `SD-${String(++counter.current).padStart(5, '0')}`,
      burstClearedAt,
      clearBurst: () => setBurstClearedAt(Date.now()),
      history,
    }),
    [tickets, burstClearedAt, history],
  )
  return <Ctx.Provider value={store}>{children}</Ctx.Provider>
}

export function useStore(): Store {
  const s = useContext(Ctx)
  if (!s) throw new Error('useStore outside StoreProvider')
  return s
}

/** Re-renders every `ms` so SLA countdowns and "x min ago" stay live. */
export function useNow(ms = 30_000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), ms)
    return () => clearInterval(id)
  }, [ms])
  return now
}

// ---------------------------------------------------------------------------
// Toasts (with optional Undo, research §3 stage 6: "a few seconds of undo")
// ---------------------------------------------------------------------------
export interface Toast {
  id: string
  tone: 'info' | 'success' | 'error'
  text: string
  undo?: () => void
}
const ToastCtx = createContext<(t: Omit<Toast, 'id'>) => void>(() => {})

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const dismiss = useCallback((id: string) => setToasts((ts) => ts.filter((t) => t.id !== id)), [])
  const push = useCallback(
    (t: Omit<Toast, 'id'>) => {
      const id = newId('t')
      setToasts((ts) => [...ts.slice(-2), { ...t, id }])
      setTimeout(() => dismiss(id), t.undo ? 6000 : 4000)
    },
    [dismiss],
  )
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div aria-live="polite" role="status" className="fixed bottom-4 right-4 z-50 flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`glass-strong flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm shadow-pop ${
              t.tone === 'error'
                ? 'border-oncall/40 bg-oncall-soft text-oncall'
                : t.tone === 'success'
                  ? 'border-auto/30 bg-dialog text-ink'
                  : 'border-line bg-dialog text-ink'
            }`}
          >
            <span className="flex-1 leading-snug">{t.text}</span>
            {t.undo && (
              <button
                className="font-semibold text-accent hover:underline"
                onClick={() => {
                  t.undo?.()
                  dismiss(t.id)
                }}
              >
                Undo
              </button>
            )}
            <button aria-label="Dismiss notification" className="text-muted hover:text-ink" onClick={() => dismiss(t.id)}>
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}
export const useToast = () => useContext(ToastCtx)
