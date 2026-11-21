import { useState } from 'react'

export interface Series { key: string; label: string; color: string }

/**
 * Stacked vertical bars (volume over time). One y-axis, 2px surface gaps
 * between segments, rounded top, recessive grid, per-bar hover tooltip.
 */
export function StackedBars({ data, series, height = 220 }: { data: { label: string; values: Record<string, number> }[]; series: Series[]; height?: number }) {
  const [hover, setHover] = useState<number | null>(null)
  const W = 720
  const H = height
  const pad = { l: 34, r: 8, t: 10, b: 24 }
  const totals = data.map((d) => series.reduce((a, s) => a + (d.values[s.key] ?? 0), 0))
  const max = Math.max(1, ...totals)
  const nice = Math.ceil(max / 10) * 10
  const ticks = [0, nice / 2, nice]
  const bw = (W - pad.l - pad.r) / data.length
  const barW = Math.max(6, Math.min(28, bw * 0.62))
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - v / nice)

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Ticket volume per day, stacked by priority">
        {ticks.map((tk) => (
          <g key={tk}>
            <line x1={pad.l} x2={W - pad.r} y1={y(tk)} y2={y(tk)} stroke="var(--grid)" strokeWidth={1} />
            <text x={pad.l - 6} y={y(tk) + 4} textAnchor="end" fontSize={11} fill="var(--muted)" className="tabular">{tk}</text>
          </g>
        ))}
        {data.map((d, i) => {
          const cx = pad.l + bw * i + bw / 2
          let acc = 0
          const segs = series.map((s) => {
            const v = d.values[s.key] ?? 0
            const y0 = y(acc)
            acc += v
            const y1 = y(acc)
            return { s, v, y0, y1 }
          }).filter((g) => g.v > 0)
          return (
            <g key={d.label} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={cx - bw / 2} y={pad.t} width={bw} height={H - pad.t - pad.b} fill={hover === i ? 'var(--surface-3)' : 'transparent'} />
              {segs.map((g, j) => {
                const top = j === segs.length - 1
                const h = Math.max(0, g.y0 - g.y1 - (j > 0 ? 2 : 0))
                return top ? (
                  <path key={g.s.key} d={roundedTop(cx - barW / 2, g.y1, barW, h, 3)} fill={g.s.color} />
                ) : (
                  <rect key={g.s.key} x={cx - barW / 2} y={g.y1 + (j > 0 ? 0 : 0)} width={barW} height={h} fill={g.s.color} />
                )
              })}
              {(i % Math.ceil(data.length / 7) === 0 || i === data.length - 1) && (
                <text x={cx} y={H - 6} textAnchor="middle" fontSize={11} fill="var(--muted)">{d.label}</text>
              )}
            </g>
          )
        })}
        <line x1={pad.l} x2={W - pad.r} y1={y(0)} y2={y(0)} stroke="var(--axis)" strokeWidth={1} />
      </svg>
      {hover !== null && (
        <div className="pointer-events-none absolute top-2 z-10 min-w-36 rounded-2xl bg-primary px-3 py-2 text-xs text-on-primary shadow-pop"
          style={{ left: `clamp(0px, calc(${((pad.l + bw * hover + bw / 2) / W) * 100}% - 72px), calc(100% - 150px))` }}>
          <p className="mb-1 font-semibold text-on-primary">{data[hover].label}</p>
          {[...series].reverse().map((s) => (
            <p key={s.key} className="flex items-center gap-2 text-on-primary/75">
              <span className="h-2 w-2 rounded-sm" style={{ background: s.color }} />{s.label}
              <span className="tabular ml-auto font-semibold text-on-primary">{data[hover].values[s.key] ?? 0}</span>
            </p>
          ))}
          <p className="mt-1 flex border-t border-line pt-1 text-on-primary/75">Total<span className="tabular ml-auto font-semibold text-on-primary">{totals[hover]}</span></p>
        </div>
      )}
    </div>
  )
}

function roundedTop(x: number, y: number, w: number, h: number, r: number) {
  const rr = Math.min(r, h, w / 2)
  return `M${x},${y + h} V${y + rr} Q${x},${y} ${x + rr},${y} H${x + w - rr} Q${x + w},${y} ${x + w},${y + rr} V${y + h} Z`
}

/** Horizontal bars, single hue, direct value labels. */
export function HBars({ rows, color = 'var(--chart-bar)', format = (n: number) => String(n) }: { rows: { label: string; value: number; sub?: string }[]; color?: string; format?: (n: number) => string }) {
  const max = Math.max(1, ...rows.map((r) => r.value))
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.label} className="group grid grid-cols-[minmax(0,10rem)_1fr_auto] items-center gap-3 text-sm" title={`${r.label}: ${format(r.value)}${r.sub ? ` · ${r.sub}` : ''}`}>
          <span className="truncate text-ink-2">{r.label}</span>
          <span className="h-3 rounded-r-[4px] bg-surface-3">
            <span className="block h-full rounded-r-[4px] transition group-hover:brightness-110" style={{ width: `${(r.value / max) * 100}%`, background: color, minWidth: r.value ? 3 : 0 }} />
          </span>
          <span className="tabular w-12 text-right font-semibold text-ink">{format(r.value)}</span>
        </li>
      ))}
    </ul>
  )
}

export function Legend({ series }: { series: Series[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2" aria-label="Legend">
      {series.map((s) => (
        <li key={s.key} className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />{s.label}</li>
      ))}
    </ul>
  )
}

/** Vertical bars for a distribution (single sequential hue), with an optional marker between buckets. */
export function Histogram({ rows, markerAfter, markerLabel }: { rows: { bucket: string; count: number }[]; markerAfter?: number; markerLabel?: string }) {
  const [hover, setHover] = useState<number | null>(null)
  const max = Math.max(1, ...rows.map((r) => r.count))
  const total = rows.reduce((a, r) => a + r.count, 0) || 1
  return (
    <div>
      <div className="relative flex h-44 items-end gap-2 border-b border-[var(--axis)] px-1" role="img" aria-label={rows.map((r) => `${r.bucket}: ${r.count}`).join(', ')}>
        {rows.map((r, i) => (
          <div key={r.bucket} className="relative flex h-full flex-1 flex-col justify-end" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <span className="tabular mb-1 text-center text-xs text-muted">{Math.round((r.count / total) * 100)}%</span>
            <div className="rounded-t-[4px] transition-[filter] hover:brightness-110" style={{ height: `${(r.count / max) * 78}%`, background: `color-mix(in oklab, var(--chart-bar) ${45 + i * 13}%, var(--surface))` }} />
            {hover === i && (
              <div className="pointer-events-none absolute -top-2 left-1/2 z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-full bg-primary px-2.5 py-1 text-xs font-medium text-on-primary shadow-pop">
                <span className="text-ink-2">{r.bucket}</span> <span className="tabular font-semibold text-ink">{r.count.toLocaleString()}</span>
              </div>
            )}
            {markerAfter === i && <span className="absolute -right-[5px] bottom-0 top-0 w-px border-l border-dashed border-review" aria-hidden />}
          </div>
        ))}
      </div>
      <div className="mt-1.5 flex gap-2 px-1">
        {rows.map((r) => <span key={r.bucket} className="flex-1 text-center text-xs text-muted">{r.bucket}</span>)}
      </div>
      {markerLabel && <p className="mt-2 flex items-center gap-1.5 text-xs text-muted"><span className="inline-block h-3 w-0 border-l border-dashed border-review" />{markerLabel}</p>}
    </div>
  )
}
