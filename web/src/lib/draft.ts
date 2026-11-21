import type { Precedent } from '../types'

/**
 * Splits a draft into statements and marks each one as:
 *  - cited:       carries at least one [TKT-xxxxx] that exists in the precedents
 *  - unverified:  cites an ID that is NOT among the retrieved precedents
 *  - courtesy:    greeting, thanks, closing or process commitment (no claim to verify)
 *  - unsupported: a factual claim with no supporting reference  → highlighted for the agent
 */
export type StatementKind = 'cited' | 'unverified' | 'courtesy' | 'unsupported'
export interface Part { text: string; cite?: string; known?: boolean }
export interface Statement { kind: StatementKind; parts: Part[]; newline?: boolean }

const CITE = /\[(?:#)?(TKT-\d{3,})\]/g

const COURTESY = [
  /^(hello|hi|dear|good (morning|afternoon)|sehr geehrte|hallo|guten tag|liebe)/i,
  /^(thank|thanks|many thanks|vielen dank|danke|we appreciate)/i,
  /^(kind|best|warm) regards|^mit freundlichen|^viele grüße|^beste grüße/i,
  /^(support team|your support team|ihr support-team)\b/i,
  /^(we will|we'll|our [\w -]+ team will|wir (werden|melden|halten)|unser [\w -]+team (wird|prüft))/i,
  /^(we are aware|we are investigating|we are looking|wir prüfen|wir untersuchen|sorry|we apologi[sz]e|es tut uns leid)/i,
  /^(please let us know|bitte melden sie sich|if you have any)/i,
  /^(referenz für|reference for)/i,
]

export function analyzeDraft(text: string, precedents: Precedent[]): Statement[][] {
  const ids = new Set(precedents.map((p) => p.ticket_id))
  return text.split(/\n{2,}/).map((para) =>
    splitSentences(para).map(({ sentence, newline }) => {
      const parts: Part[] = []
      let last = 0
      let cited = false
      let unknown = false
      for (const m of sentence.matchAll(CITE)) {
        const idx = m.index ?? 0
        if (idx > last) parts.push({ text: sentence.slice(last, idx) })
        const known = ids.has(m[1])
        parts.push({ text: m[0], cite: m[1], known })
        if (known) cited = true
        else unknown = true
        last = idx + m[0].length
      }
      if (last < sentence.length) parts.push({ text: sentence.slice(last) })
      const plain = sentence.replace(CITE, '').trim()
      const kind: StatementKind = unknown ? 'unverified' : cited ? 'cited' : isCourtesy(plain) ? 'courtesy' : 'unsupported'
      return { kind, parts, newline }
    }),
  )
}

function isCourtesy(s: string): boolean {
  if (!s) return true
  if (s.length <= 40 && !/\d/.test(s)) return true
  return COURTESY.some((r) => r.test(s))
}

function splitSentences(p: string): { sentence: string; newline: boolean }[] {
  // Keep line breaks inside a paragraph (signatures) as their own statements.
  return p
    .split(/\n/)
    .filter((line) => line.trim().length > 0)
    .flatMap((line, li) => line.split(/(?<=[.!?])\s+(?=[A-ZÄÖÜ])/).map((sentence, si) => ({ sentence, newline: li > 0 && si === 0 })))
}

export function draftStats(text: string, precedents: Precedent[]) {
  const all = analyzeDraft(text, precedents).flat()
  const cited = new Set<string>()
  all.forEach((s) => s.parts.forEach((p) => p.cite && p.known && cited.add(p.cite)))
  return {
    unsupported: all.filter((s) => s.kind === 'unsupported').length,
    unverified: all.filter((s) => s.kind === 'unverified').length,
    citedIds: [...cited],
  }
}

/** Citation markers are internal: the customer receives the text without them. */
export function stripCitations(text: string): string {
  return text.replace(/\s*\[(?:#)?TKT-\d{3,}\]/g, '').replace(/[ \t]+\n/g, '\n').trim()
}
