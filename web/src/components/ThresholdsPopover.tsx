import { useEffect, useId, useRef, useState } from 'react'
import { DEFAULT_THRESHOLDS, EXPLAIN } from '../lib/thresholds'
import { useConfig } from '../lib/useApi'
import { Icon } from './ui'

/** Task C.6: "What is your threshold?" answered in one click, from GET /config. */
export function ThresholdsPopover() {
  const [open, setOpen] = useState(false)
  const live = useConfig()
  const values = live ?? DEFAULT_THRESHOLDS
  const ref = useRef<HTMLDivElement>(null)
  const panelId = useId()

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    const onDown = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    window.addEventListener('keydown', onKey)
    window.addEventListener('mousedown', onDown)
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('mousedown', onDown) }
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-controls={panelId}
        className="inline-flex h-10 items-center gap-2 rounded-full border border-line bg-surface-2 px-3 text-xs font-medium text-ink-2 transition-colors hover:text-ink">
        <Icon name="sliders" className="h-4 w-4" />
        <span className="hidden md:inline">Thresholds</span>
        <span className="sr-only md:hidden">Thresholds</span>
      </button>
      {open && (
        <div id={panelId} role="dialog" aria-label="Safety check thresholds"
          className="absolute right-0 top-12 z-50 w-[min(26rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-line bg-dialog shadow-pop glass-strong">
          <div className="border-b border-line px-4 py-3">
            <p className="text-sm font-semibold text-ink">Safety check thresholds</p>
            <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted">
              <span className={`h-1.5 w-1.5 rounded-full ${live ? 'bg-auto' : 'bg-review'}`} aria-hidden />
              {live ? 'Live values from GET /config' : 'API offline: showing the default values from agent/config.py'}
            </p>
          </div>
          <dl className="max-h-[60dvh] divide-y divide-line overflow-y-auto">
            {Object.entries(values).map(([k, v]) => (
              <div key={k} className="flex items-start gap-4 px-4 py-2.5">
                <div className="min-w-0 flex-1">
                  <dt className="font-mono text-xs font-medium text-ink">{k}</dt>
                  {EXPLAIN[k] && <dd className="mt-0.5 text-xs leading-snug text-muted">{EXPLAIN[k]}</dd>}
                </div>
                <dd className="tabular font-mono text-sm font-semibold text-ink">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="border-t border-line px-4 py-2.5 text-xs text-muted">Tuned on the validation slice of the knowledge base, never on the test set.</p>
        </div>
      )}
    </div>
  )
}
