import * as L from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { band, duration, initials, pct, PRIORITY_LABEL, sla, STATUS_LABEL } from '../lib/format'
import type { Priority, Route, Ticket, WorkflowStatus } from '../types'

// ---------------------------------------------------------------------------
// Icons (inline SVG, 1.75 stroke, decorative by default)
// ---------------------------------------------------------------------------
const ICONS = {
  inbox: L.Inbox, user: L.User, users: L.Users, clock: L.Clock, timer: L.Timer, check: L.Check, checkCircle: L.CircleCheck,
  alert: L.TriangleAlert, alertCircle: L.CircleAlert, siren: L.Siren, eye: L.Eye, search: L.Search, chart: L.ChartColumn,
  plus: L.Plus, send: L.Send, note: L.NotebookPen, paperclip: L.Paperclip, chevronDown: L.ChevronDown, chevronRight: L.ChevronRight,
  globe: L.Globe, languages: L.Languages, shield: L.Shield, shieldCheck: L.ShieldCheck, lock: L.Lock, copy: L.Copy,
  thumbUp: L.ThumbsUp, thumbDown: L.ThumbsDown, zap: L.Zap, history: L.History, link: L.Link2, x: L.X, arrowLeft: L.ArrowLeft,
  refresh: L.RefreshCw, upload: L.Upload, star: L.Star, layers: L.Layers, keyboard: L.Keyboard, sparkle: L.Sparkles,
  settings: L.Settings, file: L.FileText, info: L.Info, pencil: L.Pencil, sliders: L.SlidersHorizontal, filter: L.ListFilter,
  external: L.ExternalLink, undo: L.Undo2, bell: L.Bell, flame: L.Flame, quote: L.Quote, circleDashed: L.CircleDashed,
} as const
export type IconName = keyof typeof ICONS

export function Icon({ name, className = 'h-4 w-4', label }: { name: IconName; className?: string; label?: string }) {
  const C = ICONS[name]
  return <C className={`shrink-0 ${className}`} strokeWidth={1.75} aria-hidden={label ? undefined : true} aria-label={label} role={label ? 'img' : undefined} />
}

// ---------------------------------------------------------------------------
// Buttons
// ---------------------------------------------------------------------------
type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'success'
const VARIANT: Record<Variant, string> = {
  primary: 'bg-primary text-on-primary hover:bg-primary-hover border-transparent',
  secondary: 'bg-surface-3 text-ink border-line hover:border-line-strong',
  ghost: 'bg-transparent text-ink-2 border-transparent hover:bg-surface-3 hover:text-ink',
  danger: 'bg-oncall text-on-route border-transparent hover:opacity-90',
  success: 'bg-auto text-on-route border-transparent hover:opacity-90',
}
export function Button({
  variant = 'secondary',
  size = 'md',
  icon,
  kbd,
  children,
  className = '',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md' | 'lg'; icon?: IconName; kbd?: string }) {
  const sz = size === 'sm' ? 'h-8 px-3.5 text-[13px]' : size === 'lg' ? 'h-11 px-6 text-[15px]' : 'h-9 px-4 text-sm'
  return (
    <button
      {...rest}
      className={`inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-full border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${sz} ${VARIANT[variant]} ${className}`}
    >
      {icon && <Icon name={icon} />}
      {children}
      {kbd && <Kbd className={variant === 'primary' || variant === 'danger' || variant === 'success' ? 'border-current/30 bg-current/10 text-current' : ''}>{kbd}</Kbd>}
    </button>
  )
}

export function Kbd({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <kbd className={`ml-1 inline-flex h-5 min-w-5 items-center justify-center rounded border border-line-strong bg-surface-2 px-1 font-mono text-[11px] font-medium text-muted ${className}`}>{children}</kbd>
  )
}

// ---------------------------------------------------------------------------
// Badges: colour + icon + text, never colour alone.
// ---------------------------------------------------------------------------
const PRIO_STYLE: Record<Priority, { cls: string; icon: IconName; bars: number }> = {
  high: { cls: 'bg-p-high-soft text-p-high border-transparent', icon: 'alert', bars: 3 },
  medium: { cls: 'bg-p-medium-soft text-p-medium border-transparent', icon: 'chevronDown', bars: 2 },
  low: { cls: 'bg-p-low-soft text-p-low border-transparent', icon: 'chevronDown', bars: 1 },
}
export function PriorityBadge({ priority, compact }: { priority: Priority; compact?: boolean }) {
  const s = PRIO_STYLE[priority]
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${s.cls}`} title={`Priority: ${PRIORITY_LABEL[priority]}`}>
      <span aria-hidden className="flex items-end gap-[2px]">
        {[1, 2, 3].map((i) => (
          <span key={i} className={`w-[3px] rounded-sm ${i <= s.bars ? 'bg-current' : 'bg-current opacity-20'}`} style={{ height: 4 + i * 2 }} />
        ))}
      </span>
      {!compact && PRIORITY_LABEL[priority]}
      {compact && <span className="sr-only">{PRIORITY_LABEL[priority]} priority</span>}
    </span>
  )
}

export const ROUTE_STYLE: Record<'AUTO' | 'HUMAN_REVIEW' | 'ON_CALL', { cls: string; solid: string; icon: IconName; short: string }> = {
  AUTO: { cls: 'bg-auto-soft text-auto', solid: 'bg-auto text-on-route', icon: 'checkCircle', short: 'Draft ready' },
  HUMAN_REVIEW: { cls: 'bg-review-soft text-review', solid: 'bg-review text-on-route', icon: 'eye', short: 'Human review' },
  ON_CALL: { cls: 'bg-oncall-soft text-oncall', solid: 'bg-oncall text-on-route', icon: 'siren', short: 'On-call' },
}
export const routeKey = (r: Route) => (r ?? 'AUTO') as 'AUTO' | 'HUMAN_REVIEW' | 'ON_CALL'

export function RouteBadge({ route, label, size = 'sm' }: { route: Route; label?: string; size?: 'sm' | 'lg' }) {
  const s = ROUTE_STYLE[routeKey(route)]
  if (size === 'lg') {
    return (
      <div className={`inline-flex items-center gap-3 rounded-full py-1.5 pl-1.5 pr-5 text-[17px] font-medium tracking-[-0.01em] ${s.cls}`} role="status">
        <span className={`flex h-9 w-9 items-center justify-center rounded-full ${s.solid}`}><Icon name={s.icon} className="h-[18px] w-[18px]" /></span>
        {label ?? s.short}
      </div>
    )
  }
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${s.cls}`}>
      <Icon name={s.icon} className="h-3.5 w-3.5" />
      {label ?? s.short}
    </span>
  )
}

const STATUS_STYLE: Record<WorkflowStatus, string> = {
  new: 'bg-accent-soft text-accent border-transparent',
  open: 'bg-surface-3 text-ink-2 border-transparent',
  awaiting_customer: 'bg-review-soft text-review border-transparent',
  resolved: 'bg-auto-soft text-auto border-transparent',
  closed: 'bg-surface-3 text-muted border-transparent',
}
export function StatusBadge({ status }: { status: WorkflowStatus }) {
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[status]}`}>{STATUS_LABEL[status]}</span>
}

export function SlaTimer({ ticket, now }: { ticket: Ticket; now: number }) {
  const s = sla(ticket, now)
  const label = s.kind === 'first_response' ? 'First response' : 'Resolution'
  if (s.state === 'met') return <span className="inline-flex items-center gap-1 text-xs text-auto"><Icon name="check" className="h-3.5 w-3.5" />SLA met</span>
  if (s.state === 'paused') return <span className="inline-flex items-center gap-1 text-xs text-muted" title={`${label} SLA paused while waiting for the customer`}><Icon name="clock" className="h-3.5 w-3.5" />Paused</span>
  const cls = s.state === 'breached' ? 'text-oncall font-semibold' : s.state === 'at_risk' ? 'text-review font-semibold' : 'text-ink-2'
  return (
    <span className={`tabular inline-flex items-center gap-1 text-xs ${cls}`} title={`${label} SLA ${s.state === 'breached' ? 'breached' : 'due'} ${new Date(s.dueAt).toLocaleString()}`}>
      <Icon name={s.state === 'ok' ? 'clock' : 'alert'} className="h-3.5 w-3.5" />
      {s.state === 'breached' ? `Overdue ${duration(s.remainingMs)}` : duration(s.remainingMs)}
      <span className="sr-only">{label} SLA {s.state.replace('_', ' ')}</span>
    </span>
  )
}

export function LangChip({ code, confidence }: { code: string; confidence?: number }) {
  return (
    <span className="tabular inline-flex items-center gap-1 rounded-md bg-surface-3 px-1.5 py-px font-mono text-xs font-medium uppercase text-ink-2" title={confidence ? `Detected language ${code.toUpperCase()} (${pct(confidence)})` : `Language ${code.toUpperCase()}`}>
      <Icon name="globe" className="h-3 w-3 text-muted" />
      {code}
      {confidence !== undefined && <span className="font-normal text-muted">{pct(confidence)}</span>}
    </span>
  )
}

/** Confidence in bands + %, with the band word visible (not colour alone). */
export function ConfidenceMeter({ value, showBand = true }: { value: number; showBand?: boolean }) {
  const b = band(value)
  const color = b === 'High' ? 'bg-auto' : b === 'Medium' ? 'bg-review' : 'bg-oncall'
  return (
    <div className="flex items-center gap-2" title={`Model confidence ${pct(value)} (${b}). High ≥ 75%, Medium ≥ 45%, Low below 45% (triggers human review).`}>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-3" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value * 100)} aria-label="Confidence">
        <div className={`h-full rounded-full ${color}`} style={{ width: pct(value) }} />
      </div>
      <span className="tabular text-xs text-ink-2">
        {showBand && <span className="font-semibold">{b}</span>} {pct(value)}
      </span>
    </div>
  )
}

export function Avatar({ name, size = 'sm' }: { name: string; size?: 'sm' | 'md' }) {
  const hue = [...name].reduce((a, c) => a + c.charCodeAt(0), 0) % 360
  return (
    <span
      aria-hidden
      className={`inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white ring-1 ring-line ${size === 'sm' ? 'h-6 w-6 text-[11px]' : 'h-8 w-8 text-xs'}`}
      style={{ background: `oklch(0.46 0.08 ${215 + (hue % 50)})` }}
    >
      {initials(name)}
    </span>
  )
}

export function EmptyState({ icon, title, children }: { icon: IconName; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
      <IconChip icon={icon} size="lg" />
      <p className="text-[15px] font-semibold text-ink">{title}</p>
      {children && <div className="max-w-sm text-sm text-muted">{children}</div>}
    </div>
  )
}

export function Card({ title, actions, children, className = '' }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-line bg-surface shadow-soft ${className}`}>
      {title && <PanelHeader title={title} actions={actions} />}
      {children}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Panel anatomy: round icon chip + quiet label + optional action on the right
// ---------------------------------------------------------------------------
type Tone = 'neutral' | 'oncall' | 'review' | 'auto' | 'ai' | 'accent'
const TONE_TEXT: Record<Tone, string> = { neutral: 'text-ink-2', oncall: 'text-oncall', review: 'text-review', auto: 'text-auto', ai: 'text-ai', accent: 'text-accent' }

export function IconChip({ icon, tone = 'neutral', size = 'md' }: { icon: IconName; tone?: Tone; size?: 'md' | 'lg' }) {
  return (
    <span aria-hidden className={`inline-flex shrink-0 items-center justify-center rounded-full bg-surface-3 ${TONE_TEXT[tone]} ${size === 'lg' ? 'mb-1 h-12 w-12' : 'h-8 w-8'}`}>
      <Icon name={icon} className={size === 'lg' ? 'h-5 w-5' : 'h-4 w-4'} />
    </span>
  )
}

export function PanelHeader({ title, icon, tone, actions, sub }: { title: ReactNode; icon?: IconName; tone?: Tone; actions?: ReactNode; sub?: ReactNode }) {
  return (
    <header className="flex items-center gap-3 px-5 pt-4 pb-3">
      {icon && <IconChip icon={icon} tone={tone} />}
      <div className="min-w-0 flex-1">
        <h3 className="truncate text-sm font-medium text-ink-2">{title}</h3>
        {sub && <p className="truncate text-xs text-muted">{sub}</p>}
      </div>
      {actions}
    </header>
  )
}

/** Pill segmented control: the selected option is a solid white (or ink) pill. */
export function Segmented<T extends string>({ value, options, onChange, label, size = 'md' }: { value: T; options: readonly (readonly [T, string])[]; onChange: (v: T) => void; label: string; size?: 'sm' | 'md' }) {
  return (
    <div role="group" aria-label={label} className={`inline-flex items-center rounded-full border border-line bg-surface-2 p-1 ${size === 'sm' ? 'text-xs' : 'text-[13px]'}`}>
      {options.map(([v, l]) => (
        <button key={v} type="button" aria-pressed={value === v} onClick={() => onChange(v)}
          className={`rounded-full font-medium transition-colors ${size === 'sm' ? 'h-6 px-2.5' : 'h-7 px-4'} ${value === v ? 'bg-primary text-on-primary' : 'text-muted hover:text-ink'}`}>
          {l}
        </button>
      ))}
    </div>
  )
}
