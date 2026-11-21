import type { ReactNode } from 'react'
import type { Burst } from '../types'
import { Button, Icon } from './ui'

/**
 * Task C.5: full-width red banner shown whenever `burst.active` is true.
 * Text carries the meaning (cluster_size, window_minutes, label); red is only reinforcement.
 */
export function BurstBanner({ burst, onReset, resetting, children }: { burst: Burst; onReset?: () => void; resetting?: boolean; children?: ReactNode }) {
  if (!burst.active) return null
  return (
    <div role="alert" className="flex w-full flex-wrap items-center gap-x-4 gap-y-3 rounded-2xl bg-oncall px-4 py-3.5 text-on-route sm:px-5">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-on-route/15"><Icon name="zap" className="h-5 w-5" /></span>
      <div className="min-w-0 flex-1">
        <p className="text-[15px] font-semibold">
          Possible major incident: <span className="tabular">{burst.cluster_size}</span> similar tickets in <span className="tabular">{burst.window_minutes}</span> minutes
        </p>
        <p className="mt-0.5 text-[13px] opacity-90">{burst.label ? `“${burst.label}”` : 'Similar reports are arriving together'}. Treat these as one incident, not separate tickets.</p>
      </div>
      {children}
      {onReset && (
        <Button size="sm" icon="refresh" onClick={onReset} disabled={resetting} className="border-on-route/40 bg-transparent text-on-route hover:bg-on-route/10">
          {resetting ? 'Resetting…' : 'Reset burst'}
        </Button>
      )}
    </div>
  )
}
