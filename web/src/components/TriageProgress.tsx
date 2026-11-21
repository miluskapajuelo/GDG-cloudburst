import { useEffect, useState } from 'react'
import { Icon } from './ui'

const PROGRESS = ['Masking personal data', 'Detecting language', 'Classifying type, queue, priority', 'Searching past resolutions', 'Running safety gate', 'Drafting a grounded reply']
/** Step-by-step progress: explains latency and reduces anxiety (research §7). */
export function TriageProgress() {
  const [step, setStep] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setStep((s) => Math.min(s + 1, PROGRESS.length - 1)), 450)
    return () => clearInterval(id)
  }, [])
  return (
    <ol className="space-y-1.5" aria-live="polite">
      {PROGRESS.map((label, i) => (
        <li key={label} className={`flex items-center gap-2 text-sm ${i < step ? 'text-ink-2' : i === step ? 'font-medium text-ink' : 'text-muted'}`}>
          {i < step ? (
            <Icon name="check" className="h-4 w-4 text-auto" />
          ) : i === step ? (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" aria-hidden />
          ) : (
            <span className="h-4 w-4 rounded-full border-2 border-line-strong" aria-hidden />
          )}
          {label}
        </li>
      ))}
    </ol>
  )
}
