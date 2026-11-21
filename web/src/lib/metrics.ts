import type { HoldoutMetrics } from '../types'

/** The handful of holdout numbers the console shows, read defensively from eval/results/metrics.json (A2.6 shape). */
export interface HoldoutSummary {
  f1: { type: number | null; queue: number | null; priority: number | null }
  hpiRecall: number | null
  hpiSupport: number | null
  p50: number | null
  p50Label: string
  nTest: number | null
  generatedAt: string | null
}

const num = (x: unknown): number | null => (typeof x === 'number' && Number.isFinite(x) ? x : null)
const obj = (x: unknown): Record<string, unknown> => (x && typeof x === 'object' ? (x as Record<string, unknown>) : {})

export function summarizeMetrics(m: HoldoutMetrics): HoldoutSummary {
  const clf = obj(m.classifier)
  const hpi = obj(m.high_priority_incident)
  const lat = obj(m.latency_ms)
  const withLlm = obj(lat.with_llm)
  const skip = obj(lat.skip_llm)
  // Prefer the full pipeline (with the LLM draft) when the eval measured it.
  const useLlm = num(withLlm.p50) !== null && (num(withLlm.n) ?? 0) > 0
  return {
    f1: { type: num(obj(clf.type).macro_f1), queue: num(obj(clf.queue).macro_f1), priority: num(obj(clf.priority).macro_f1) },
    hpiRecall: num(hpi.escalation_recall),
    hpiSupport: num(hpi.support),
    p50: useLlm ? num(withLlm.p50) : num(skip.p50),
    p50Label: useLlm ? 'with LLM draft' : 'without LLM draft',
    nTest: num(m.n_test),
    generatedAt: typeof m.generated_at === 'string' ? m.generated_at : null,
  }
}
