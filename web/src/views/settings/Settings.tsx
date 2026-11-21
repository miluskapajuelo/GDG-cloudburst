import type { ReactNode } from 'react'
import { Segmented } from '../../components/ui'
import { usePrefs } from '../../lib/prefs'
import { AGENT } from '../../lib/session'
import { DEFAULT_THRESHOLDS, EXPLAIN } from '../../lib/thresholds'
import { useConfig } from '../../lib/useApi'

export default function Settings() {
  const { prefs, set } = usePrefs()
  const live = useConfig()
  const thresholds = live ?? DEFAULT_THRESHOLDS
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-8 px-4 pb-12 pt-8 sm:px-8">
        <div>
          <h1 className="text-[40px] leading-[1.1] text-ink">Settings</h1>
          <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-muted">Your workspace preferences and how the safety check decides.</p>
        </div>

        <Group title="Profile">
          <Row label="Name" hint="Shown to customers on sent responses">{AGENT.name}</Row>
          <Row label="Languages" hint="Tickets in other languages show a translation">English, German</Row>
        </Group>

        <Group title="Appearance">
          <Row label="Theme" hint="Dark is the default. Use light in bright rooms or on a washed-out projector.">
            <Segmented label="Theme" value={prefs.theme} onChange={(v) => set({ theme: v })} options={[['dark', 'Dark'], ['light', 'Light'], ['system', 'System']] as const} />
          </Row>
        </Group>

        <Group title="Workspace">
          <Toggle label="Show English translation by default" hint="For tickets that are not in English" checked={prefs.showTranslation} onChange={(v) => set({ showTranslation: v })} />
          <Toggle label="Always confirm before sending" hint="Ask for an explicit confirmation on every response, not only flagged ones" checked={prefs.confirmBeforeSend} onChange={(v) => set({ confirmBeforeSend: v })} />
          <Toggle label="Notify me only about critical incidents" hint="Skip notifications for routine tickets" checked={prefs.pageOnlyCritical} onChange={(v) => set({ pageOnlyCritical: v })} />
        </Group>

        <Group title="Safety check" description={live ? 'Live values from the triage service.' : 'Default values. The live configuration is shown when the triage service is online.'}>
          {Object.entries(thresholds).map(([k, v]) => (
            <Row key={k} label={EXPLAIN[k] ?? k} hint={k}><span className="tabular font-medium">{v}</span></Row>
          ))}
          <p className="px-5 py-3.5 text-[13px] leading-relaxed text-muted">When in doubt, tickets are escalated. A false escalation costs a few minutes; a missed incident can cost far more. Thresholds are tuned on a validation set, never on the test data.</p>
        </Group>

        <Group title="Keyboard shortcuts">
          {[['J / K', 'Next / previous ticket'], ['Enter', 'Open ticket'], ['/', 'Search'], ['⌘K', 'Search from anywhere'], ['Esc', 'Back to list'], ['⌘ Enter', 'Review and send']].map(([k, d]) => (
            <Row key={k} label={d}><kbd className="rounded-md bg-surface-3 px-2 py-0.5 font-mono text-xs text-ink-2">{k}</kbd></Row>
          ))}
        </Group>
      </div>
    </div>
  )
}

function Group({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
      {description && <p className="mt-1 text-[13px] text-muted">{description}</p>}
      <div className="mt-3 divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface shadow-soft">{children}</div>
    </section>
  )
}

function Row({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex items-center gap-4 px-5 py-3.5">
      <div className="min-w-0 flex-1">
        <p className="text-sm text-ink">{label}</p>
        {hint && <p className={`mt-0.5 text-xs text-muted ${/^[A-Z0-9_]+$/.test(hint) ? 'font-mono' : ''}`}>{hint}</p>}
      </div>
      <div className="shrink-0 text-sm text-ink-2">{children}</div>
    </div>
  )
}

function Toggle({ label, hint, checked, onChange }: { label: string; hint: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center gap-4 px-5 py-3.5 transition-colors hover:bg-surface-2">
      <div className="min-w-0 flex-1">
        <p className="text-sm text-ink">{label}</p>
        <p className="mt-0.5 text-[13px] text-muted">{hint}</p>
      </div>
      <input type="checkbox" role="switch" checked={checked} onChange={(e) => onChange(e.target.checked)} className="peer sr-only" />
      <span aria-hidden className="relative h-5 w-9 shrink-0 rounded-full bg-line-strong transition-colors peer-checked:bg-accent peer-focus-visible:ring-2 peer-focus-visible:ring-accent peer-focus-visible:ring-offset-2 after:absolute after:left-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-surface after:shadow after:transition-transform peer-checked:after:translate-x-4" />
    </label>
  )
}
