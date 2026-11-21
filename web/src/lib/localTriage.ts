import type { Pred, PiiKey, Precedent, Reason, TriageResponse } from '../types'
import { KB } from './kb'

/**
 * In-browser fallback triage used ONLY when the API is unreachable or
 * VITE_OFFLINE=1. It follows docs/escalation-policy.md so that the UI
 * states (ON_CALL, HUMAN_REVIEW, AUTO_DRAFT, no draft) look right, but it is
 * a keyword heuristic, not the trained model. Results carry mock: true.
 */

const T = { T_HIGH_PRIORITY_P: 0.35, T_INCIDENT_P: 0.4, T_CONF_TYPE: 0.45, T_CONF_PRIORITY: 0.45, T_CONF_QUEUE: 0.25, T_SIM: 0.3, TOP_K: 3 }

const INJECTION = [
  /ignore (all |any |the )?(previous|prior|above|earlier) (instructions|rules|prompts?)/i,
  /disregard (all |any |the )?(previous|prior|above) (instructions|rules)/i,
  /(reveal|print|show) (your|the) (system )?prompt/i,
  /you are now|act as (an? )?(admin|system|developer)|developer mode|jailbreak/i,
  /<\/?(system|ticket|precedents?|instructions?)>/i,
  /ignorier(e|en)? (alle |die )?(vorherigen|obigen|bisherigen) (anweisungen|regeln)/i,
  /vergiss (alle |deine )?(anweisungen|regeln)/i,
]

const SENSITIVE: Record<string, string[]> = {
  REFUND_COMPENSATION: ['refund', 'reimburse', 'compensation', 'money back', 'chargeback', 'credit note', 'rückerstattung', 'erstatten', 'entschädigung', 'geld zurück', 'gutschrift'],
  PRICING_DISCOUNT: ['price', 'pricing', 'quote', 'discount', 'license fee', 'cost per', 'preis', 'rabatt', 'lizenzgebühr', 'kostenvoranschlag'],
  LEGAL_CONTRACT: ['lawsuit', 'legal action', 'liability', 'lawyer', 'terminate contract', 'gdpr', 'delete all my data', 'klage', 'rechtliche schritte', 'haftung', 'anwalt', 'vertrag kündigen', 'dsgvo', 'datenlöschung'],
  SLA_GUARANTEE: ['sla', 'guarantee', 'uptime commitment', 'service credit', 'penalty', 'garantie', 'verfügbarkeitszusage', 'vertragsstrafe'],
  SECURITY_OVERRIDE: ['disable mfa', 'bypass', 'share password', 'give me admin', 'root access', 'mfa deaktivieren', 'passwort mitteilen', 'adminrechte geben', 'umgehen'],
}

const PII: Record<PiiKey, RegExp> = {
  EMAIL: /[\w.+-]+@[\w-]+\.[\w.-]+/g,
  IP: /\b(?:\d{1,3}\.){3}\d{1,3}\b/g,
  IBAN: /\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}\b/g,
  CARD: /\b(?:\d[ -]?){13,16}\b/g,
  PHONE: /\+?\d[\d ()/-]{7,}\d/g,
  ACCOUNT: /\b(?:account|konto)(?: no\.?| number|nummer)?[:#]? ?\d{5,}\b/gi,
}

const has = (t: string, words: string[]) => words.filter((w) => t.includes(w)).length

function softmax(scores: Record<string, number>): Record<string, number> {
  const entries = Object.entries(scores)
  const exps = entries.map(([k, v]) => [k, Math.exp(v)] as const)
  const sum = exps.reduce((a, [, v]) => a + v, 0)
  const out: Record<string, number> = {}
  for (const [k, v] of exps) out[k] = Math.round((v / sum) * 100) / 100
  return out
}

function pred(scores: Record<string, number>): Pred {
  const probs = softmax(scores)
  const [label, confidence] = Object.entries(probs).sort((a, b) => b[1] - a[1])[0]
  return { label, confidence, probs }
}

function tokens(s: string): Set<string> {
  return new Set(s.toLowerCase().normalize('NFC').split(/[^\p{L}\p{N}]+/u).filter((w) => w.length > 2))
}

export function detectLanguage(text: string): { code: string; confidence: number } {
  const t = ` ${text.toLowerCase()} `
  const de = has(t, [' der ', ' die ', ' und ', ' nicht ', ' ich ', ' sie ', ' wir ', ' ist ', ' bitte ', ' mit ', ' seit ', 'ä', 'ö', 'ü', 'ß'])
  const en = has(t, [' the ', ' and ', ' not ', ' is ', ' we ', ' please ', ' with ', ' since ', ' our ', ' you '])
  if (de + en === 0) return { code: 'en', confidence: 0.5 }
  const code = de > en ? 'de' : 'en'
  return { code, confidence: Math.round((0.55 + (0.44 * Math.max(de, en)) / (de + en + 1)) * 100) / 100 }
}

export function triageSync(subject: string | null, body: string): TriageResponse {
  const raw = [subject ?? '', body].filter(Boolean).join('\n\n').trim()
  const counts = { EMAIL: 0, PHONE: 0, IP: 0, IBAN: 0, CARD: 0, ACCOUNT: 0 } as Record<PiiKey, number>
  let masked = raw
  for (const key of ['EMAIL', 'IBAN', 'IP', 'CARD', 'ACCOUNT', 'PHONE'] as PiiKey[]) {
    masked = masked.replace(PII[key], () => {
      counts[key]++
      return `[${key}]`
    })
  }
  const t = masked.toLowerCase()
  const lang = detectLanguage(masked)

  const urgent = has(t, ['urgent', 'dringend', 'asap', 'sofort', 'critical', 'kritisch', 'all users', 'alle ', 'whole office', 'ganze', 'down', 'ausfall', 'ausgefallen', 'outage', 'hospital', 'klinik'])
  const incident = has(t, ['down', 'outage', 'ausfall', 'error', 'fehler', 'not working', 'funktioniert nicht', 'fails', 'failing', 'timeout', 'bricht ab', 'crash', '502', 'unreachable', 'nicht erreichbar', 'blank', 'leere'])
  const request = has(t, ['please', 'bitte', 'request', 'could you', 'können sie', 'how do i', 'wie kann', 'reset', 'access', 'zugang', 'question', 'frage'])
  const change = has(t, ['change', 'ändern', 'permission', 'berechtigung', 'upgrade', 'migrate', 'add user'])
  const problem = has(t, ['again', 'erneut', 'recurring', 'wiederholt', 'intermittent', 'since the last', 'charged twice', 'doppelt'])

  const type = pred({ Incident: incident * 0.9, Request: request * 0.7, Change: change * 0.9, Problem: problem * 0.9 })
  const priority = pred({ high: urgent * 0.8 + (type.label === 'Incident' ? 0.4 : 0), medium: 0.9, low: change * 0.5 + (urgent ? 0 : 0.4) })

  const q = (words: string[], w = 0.8) => has(t, words) * w
  const queue = pred({
    'Technical Support': q(['vpn', 'error', 'fehler', 'server', 'dashboard', '502', 'api']),
    'IT Support': q(['password', 'passwort', 'printer', 'drucker', 'laptop', 'permission', 'berechtigung', 'account', 'konto', 'locked', 'gesperrt']),
    'Billing and Payments': q(['invoice', 'rechnung', 'charged', 'payment', 'zahlung', 'refund', 'rückerstattung', 'billing']),
    'Product Support': q(['feature', 'app', 'sync', 'synchron', 'integration']),
    'Customer Service': q(['complaint', 'beschwerde', 'gdpr', 'dsgvo', 'data', 'daten'], 0.5),
    'Sales and Pre-Sales': q(['pricing', 'price', 'preis', 'quote', 'demo', 'license']),
    'Service Outages and Maintenance': q(['outage', 'ausfall', 'maintenance', 'wartung', 'whole office', 'all users']),
    'Returns and Exchanges': q(['return', 'rücksendung', 'damaged', 'beschädigt', 'exchange']),
    'Human Resources': q(['payroll', 'gehalt', 'vacation', 'urlaub']),
    'General Inquiry': 0.3,
  })

  // Retrieval: token-overlap similarity against the demo KB.
  const qt = tokens(masked)
  const precedents: Precedent[] = KB.map((row) => {
    const rt = tokens(`${row.subject} ${row.body} ${row.tags.join(' ')}`)
    let inter = 0
    for (const w of qt) if (rt.has(w)) inter++
    const sim = inter === 0 ? 0 : Math.min(0.95, 0.25 + inter / Math.sqrt(qt.size * rt.size + 1) * 1.6)
    return {
      ticket_id: row.ticket_id, similarity: Math.round(sim * 1000) / 1000, language: row.language, subject: row.subject,
      body_snippet: row.body.slice(0, 300), answer_snippet: row.answer.slice(0, 400), answer: row.answer,
      type: row.type, queue: row.queue, priority: row.priority, tags: row.tags,
    }
  })
    .filter((p) => p.similarity > 0.2)
    .sort((a, b) => b.similarity - a.similarity)
    .slice(0, T.TOP_K)

  // Gate (docs/escalation-policy.md §1).
  const reasons: Reason[] = []
  const injection = INJECTION.some((r) => r.test(masked))
  if (injection) reasons.push({ code: 'PROMPT_INJECTION_SUSPECTED', message: 'Ticket text contains an instruction-override pattern; it was treated as data and no draft was generated.' })
  const pHigh = priority.probs.high ?? 0
  const pInc = type.probs.Incident ?? 0
  const onCall = pHigh >= T.T_HIGH_PRIORITY_P && pInc >= T.T_INCIDENT_P && priority.label === 'high'
  if (onCall) reasons.unshift({ code: 'HIGH_PRIORITY_INCIDENT', message: `Predicted high priority (p=${pHigh.toFixed(2)}) and Incident (p=${pInc.toFixed(2)}).` })
  const low: string[] = []
  if (type.confidence < T.T_CONF_TYPE) low.push(`type ${type.confidence.toFixed(2)} < ${T.T_CONF_TYPE}`)
  if (priority.confidence < T.T_CONF_PRIORITY) low.push(`priority ${priority.confidence.toFixed(2)} < ${T.T_CONF_PRIORITY}`)
  if (queue.confidence < T.T_CONF_QUEUE) low.push(`queue ${queue.confidence.toFixed(2)} < ${T.T_CONF_QUEUE}`)
  if (low.length) reasons.push({ code: 'LOW_CLASSIFIER_CONFIDENCE', message: `Classifier is unsure: ${low.join(', ')}.` })
  const noPrec = precedents.length === 0 || precedents[0].similarity < T.T_SIM
  if (noPrec) reasons.push({ code: 'NO_PRECEDENT', message: precedents.length ? `Best precedent similarity ${precedents[0].similarity.toFixed(2)} < ${T.T_SIM}.` : 'No similar past tickets found.' })
  for (const [cat, words] of Object.entries(SENSITIVE)) {
    const hit = words.find((w) => t.includes(w))
    if (hit && !precedents.some((p) => words.some((w) => p.answer.toLowerCase().includes(w)))) {
      reasons.push({ code: 'UNSUPPORTED_REQUEST', message: `Ticket requests ${cat} ("${hit}"); no retrieved precedent resolves this.` })
      break
    }
  }

  const route = onCall ? 'ON_CALL' : reasons.length ? 'HUMAN_REVIEW' : null
  const status = reasons.length ? 'ESCALATE' : 'AUTO_DRAFT'
  const badge = route === 'ON_CALL' ? 'Escalate to On-Call Engineer' : route === 'HUMAN_REVIEW' ? 'Human Review Required' : 'Auto-Draft Ready'
  const replyLang = lang.code === 'de' ? 'de' : 'en'
  const allowDraft = !injection && !noPrec
  const cited = precedents.slice(0, 2)
  const holding = reasons.some((r) => r.code === 'UNSUPPORTED_REQUEST')

  let text = ''
  if (allowDraft) {
    if (replyLang === 'de') {
      text = `Sehr geehrte Damen und Herren,\n\nvielen Dank für Ihre Nachricht.${onCall ? ' Wir haben Ihr Anliegen mit höchster Priorität an unseren Bereitschaftsdienst weitergeleitet.' : ''}\n\n` +
        (holding ? `Ihre Anfrage zu diesem Punkt prüft ein Mitarbeiter persönlich; wir melden uns zeitnah bei Ihnen.` :
          cited.map((p) => `${firstSentence(p.answer)} [${p.ticket_id}]`).join('\n\n')) +
        `\n\nMit freundlichen Grüßen\nIhr Support-Team`
    } else {
      text = `Hello,\n\nthank you for contacting us.${onCall ? ' We have routed your report to our on-call engineer with the highest priority.' : ''}\n\n` +
        (holding ? `A member of our team will review this part of your request personally and get back to you shortly.` :
          cited.map((p) => `${firstSentence(p.answer)} [${p.ticket_id}]`).join('\n\n')) +
        `\n\nKind regards,\nSupport Team`
    }
  }

  return {
    request_id: crypto.randomUUID(),
    mock: true,
    input: { subject: subject || null, body_chars: body.length, truncated: body.length > 8000 },
    language: { code: lang.code, confidence: lang.confidence, reply_language: replyLang },
    pii: { masked: Object.values(counts).some((n) => n > 0), counts },
    predictions: { type, queue, priority },
    escalation: { status, route, badge, reasons },
    precedents,
    draft: allowDraft
      ? { status: holding ? 'INSUFFICIENT_EVIDENCE' : 'OK', text, cited_ids: holding ? [] : cited.map((p) => p.ticket_id), language: replyLang, for_human_review: status === 'ESCALATE', model: 'offline-template' }
      : null,
    burst: { active: false, cluster_size: 1, window_minutes: 15, label: null, request_ids: [] },
    latency_ms: { pii: 1, language: 1, classify: 2, retrieve: 3, gate: 1, generate: allowDraft ? 4 : 0, total: allowDraft ? 12 : 8 },
  }
}

function firstSentence(s: string): string {
  const m = s.match(/^.*?[.!?](\s|$)/)
  return (m ? m[0] : s).trim()
}

export async function localTriage(subject: string | null, body: string): Promise<TriageResponse> {
  await new Promise((r) => setTimeout(r, 900)) // lets the staged progress UI be seen
  return triageSync(subject, body)
}
