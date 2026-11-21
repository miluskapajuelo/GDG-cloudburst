import { useEffect, useMemo, useRef, useState } from 'react'
import { AGENT } from '../../lib/session'
import { Button, Icon } from '../../components/ui'
import { analyzeDraft, draftStats, stripCitations, type Statement } from '../../lib/draft'
import { LANG_LABEL, STATUS_LABEL } from '../../lib/format'
import { usePrefs } from '../../lib/prefs'
import { decision } from '../../lib/ticket'
import { useStore, useToast } from '../../store'
import type { Precedent, Ticket, WorkflowStatus } from '../../types'

const ACK: Record<'en' | 'de', string> = {
  en: 'Hello,\n\nthank you for your report. We have escalated it to our on-call engineering team with the highest priority, and they are already working on it.\n\nWe will update you as soon as we have more information.\n\nKind regards,\nSupport Team',
  de: 'Sehr geehrte Damen und Herren,\n\nvielen Dank für Ihre Meldung. Wir haben sie mit höchster Priorität an unseren technischen Bereitschaftsdienst weitergeleitet, der bereits daran arbeitet.\n\nWir melden uns, sobald wir weitere Informationen haben.\n\nMit freundlichen Grüßen\nIhr Support-Team',
}
const FEEDBACK = ['Missing step', 'Wrong tone', 'Wrong precedent', 'Unsupported statement', 'Wrong language']
const UNDO_MS = 5000

export default function ResponseWorkspace({ t, onCite }: { t: Ticket; onCite: (id: string) => void }) {
  const tri = t.triage
  const d = decision(t)
  const replyLang = (tri?.language.reply_language ?? 'en') as 'en' | 'de'
  const answered = t.messages.some((m) => m.role === 'agent' && !m.internal)

  if (!tri) {
    return <Composer t={t} replyLang={replyLang} initial="" mode="manual" onCite={onCite} intro={<Notice tone="neutral" icon="info" title="Classification unavailable">The triage service could not process this ticket. Classify it manually and write the response yourself.</Notice>} />
  }
  if (d === 'critical') {
    return (
      <div className="space-y-4">
        <Notice tone="oncall" icon="lock" title="No customer response is generated for critical incidents">
          Engineering owns the technical answer. You can send the customer a short, human acknowledgement so they know the incident is being handled.
        </Notice>
        {tri.draft && <EngineerReference t={t} onCite={onCite} />}
        {!answered && <Composer t={t} replyLang={replyLang} initial={ACK[replyLang]} mode="acknowledgement" onCite={onCite} />}
        {answered && <SentNote t={t} />}
      </div>
    )
  }
  if (answered && t.status !== 'new' && t.status !== 'open') return <SentNote t={t} />
  if (!tri.draft) {
    const codes = tri.escalation.reasons.map((r) => r.code)
    const why = tri.escalation.reasons.find((r) => r.code === 'PROMPT_INJECTION_SUSPECTED')
      ? 'This ticket contains instructions aimed at the assistant, so no response was suggested. Treat it with care and write the reply yourself.'
      : tri.escalation.reasons.find((r) => r.code === 'LLM_UNAVAILABLE')
        ? 'The drafting service was unavailable. Classification still worked; write the reply yourself or try again later.'
        : 'No sufficiently similar historical resolutions found, so nothing could be grounded. Write the reply yourself, or ask the customer for details.'
    return (
      <Composer t={t} replyLang={replyLang} initial="" mode="manual" onCite={onCite}
        intro={<Notice tone="neutral" icon="search" title="No draft generated">
          {why}
          {codes.length > 0 && <span className="mt-2 flex flex-wrap gap-1.5">{codes.map((c) => <code key={c} className="rounded border border-line bg-surface-2 px-1.5 py-px font-mono text-xs font-semibold text-ink-2">{c}</code>)}</span>}
        </Notice>} />
    )
  }
  return <Composer t={t} replyLang={replyLang} initial={tri.draft.text} mode="suggested" onCite={onCite} />
}

// ---------------------------------------------------------------------------
type Mode = 'suggested' | 'manual' | 'acknowledgement'

function Composer({ t, replyLang, initial, mode, onCite, intro }: { t: Ticket; replyLang: 'en' | 'de'; initial: string; mode: Mode; onCite: (id: string) => void; intro?: React.ReactNode }) {
  const store = useStore()
  const toast = useToast()
  const { prefs } = usePrefs()
  const precedents = useMemo(() => t.triage?.precedents ?? [], [t.triage])
  const [text, setText] = useState(initial)
  const [editing, setEditing] = useState(mode !== 'suggested')
  const [view, setView] = useState<'reply' | 'translation'>('reply')
  const [confirm, setConfirm] = useState(false)
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(t.feedback?.rating ?? null)
  const area = useRef<HTMLTextAreaElement>(null)
  const edited = text.trim() !== initial.trim()
  const stats = useMemo(() => draftStats(text, precedents), [text, precedents])
  const translation = mode === 'suggested' && !edited ? t.translation?.draft : undefined
  const draft = t.triage?.draft
  const escalated = t.triage?.escalation.status === 'ESCALATE'
  const otherLang = replyLang === 'de' ? 'English' : 'German'

  useEffect(() => {
    if (editing && mode === 'suggested') area.current?.focus()
  }, [editing, mode])

  const send = (after: WorkflowStatus) => {
    setConfirm(false)
    const body = stripCitations(text)
    const unedited = mode === 'suggested' && !edited
    const timer = setTimeout(() => {
      store.message(t.id, { author: AGENT.name, role: 'agent', internal: false, body }, { status: after, assignee: t.assignee ?? AGENT.name, draft_sent_unedited: mode === 'suggested' ? unedited : undefined })
      store.patch(t.id, {}, { kind: 'reply', text: `${mode === 'acknowledgement' ? 'Acknowledgement' : 'Response'} approved and sent by ${AGENT.name}${mode === 'suggested' ? (unedited ? ' (suggested response, unedited)' : ' (suggested response, edited)') : ''}. Status → ${STATUS_LABEL[after]}` }, AGENT.name)
    }, UNDO_MS)
    toast({ tone: 'success', text: `Sending to ${t.requester.name} in 5 s`, undo: () => clearTimeout(timer) })
  }

  const title = mode === 'acknowledgement' ? 'Customer acknowledgement' : mode === 'suggested' ? 'Suggested response' : 'Your response'

  return (
    <section aria-label={title} className="overflow-hidden rounded-2xl border border-line bg-surface shadow-soft">
      {mode === 'suggested' && draft?.for_human_review && (
        <div role="note" className="flex items-center gap-2 border-b border-review/35 bg-review-soft px-5 py-2 text-sm font-semibold text-review">
          <Icon name="eye" className="h-4 w-4" />
          For human review: do not send
          <span className="font-normal text-ink-2">A person must read and approve this draft first.</span>
        </div>
      )}
      {intro && <div className="border-b border-line p-4">{intro}</div>}
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line px-4 py-3">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        {mode === 'suggested' && <span className="rounded-full bg-ai-soft px-2.5 py-0.5 text-xs font-medium text-ai" title="Written by the language model from the cited past tickets">AI draft</span>}
        <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-3 px-2.5 py-0.5 text-xs text-ink-2">
          <Icon name="languages" className="h-3.5 w-3.5" /> Reply in {LANG_LABEL[replyLang]}
        </span>
        {mode === 'suggested' && t.translation?.draft && (
          <div role="group" aria-label="Response language view" className="ml-auto flex rounded-full border border-line bg-surface-2 p-1 text-xs">
            <button aria-pressed={view === 'reply'} onClick={() => setView('reply')} className={`rounded-full px-3 py-1 font-medium ${view === 'reply' ? 'bg-primary text-on-primary' : 'text-muted hover:text-ink'}`}>{LANG_LABEL[replyLang]}</button>
            <button aria-pressed={view === 'translation'} onClick={() => setView('translation')} className={`rounded-full px-3 py-1 font-medium ${view === 'translation' ? 'bg-primary text-on-primary' : 'text-muted hover:text-ink'}`}>{otherLang}</button>
          </div>
        )}
      </header>

      {mode === 'suggested' && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line bg-surface-2 px-4 py-2 text-xs">
          <span className="inline-flex items-center gap-1.5 text-ink-2"><Icon name="quote" className="h-3.5 w-3.5 text-ai" />Based on {stats.citedIds.length} historical resolution{stats.citedIds.length === 1 ? '' : 's'}</span>
          {stats.unsupported > 0 ? (
            <span className="inline-flex items-center gap-1.5 font-medium text-review"><Icon name="alert" className="h-3.5 w-3.5" />{stats.unsupported} statement{stats.unsupported > 1 ? 's have' : ' has'} no supporting reference</span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-auto"><Icon name="check" className="h-3.5 w-3.5" />Every statement is referenced</span>
          )}
          {stats.unverified > 0 && <span className="inline-flex items-center gap-1.5 font-medium text-oncall"><Icon name="alertCircle" className="h-3.5 w-3.5" />{stats.unverified} reference not in the supporting history</span>}
          {draft?.status === 'INSUFFICIENT_EVIDENCE' && <span className="inline-flex items-center gap-1.5 rounded-full bg-review-soft px-2.5 py-0.5 font-semibold text-review"><Icon name="info" className="h-3.5 w-3.5" />Insufficient evidence: holding reply</span>}
          {edited && <span className="text-muted">Edited by you</span>}
        </div>
      )}

      <div className="p-4">
        {view === 'translation' && translation ? (
          <div>
            <p className="mb-2 text-xs text-muted">Translation for your reference. The customer receives the {LANG_LABEL[replyLang]} version.</p>
            <StatementView statements={analyzeDraft(translation, [])} onCite={onCite} precedents={precedents} muted />
          </div>
        ) : view === 'translation' ? (
          <p className="text-sm text-muted">Translation is only available for the unedited suggestion.</p>
        ) : editing ? (
          <>
            <label htmlFor="response-editor" className="sr-only">{title}</label>
            <textarea
              id="response-editor"
              ref={area}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && text.trim()) { e.preventDefault(); setConfirm(true) } }}
              rows={Math.min(18, Math.max(8, text.split('\n').length + 2))}
              placeholder={mode === 'manual' ? `Write your response in ${LANG_LABEL[replyLang]}…` : ''}
              className="block w-full resize-y rounded-xl border border-line bg-surface-2 px-4 py-3 text-[14px] leading-relaxed text-ink placeholder:text-muted"
            />
            {mode !== 'manual' && <p className="mt-2 text-xs text-muted">Keep references like [TKT-…] next to the statements they support. They are removed before sending.</p>}
          </>
        ) : (
          <StatementView statements={analyzeDraft(text, precedents)} onCite={onCite} precedents={precedents} />
        )}
      </div>

      <footer className="flex flex-wrap items-center gap-2 border-t border-line px-4 py-3">
        {mode === 'suggested' && view === 'reply' && (
          editing ? (
            <Button size="sm" variant="ghost" icon="eye" onClick={() => setEditing(false)}>Preview with references</Button>
          ) : (
            <Button size="sm" icon="pencil" onClick={() => setEditing(true)}>Edit response</Button>
          )
        )}
        {mode === 'suggested' && edited && <Button size="sm" variant="ghost" icon="undo" onClick={() => setText(initial)}>Restore suggestion</Button>}
        {text.trim() && <CopyButton text={text} />}
        {mode === 'suggested' && (
          <div className="flex items-center gap-0.5" role="group" aria-label="Rate the suggested response">
            <button aria-pressed={feedback === 'up'} aria-label="Helpful" onClick={() => { setFeedback('up'); store.patch(t.id, { feedback: { rating: 'up' } }, { kind: 'feedback', text: 'Suggested response rated helpful' }, AGENT.name) }}
              className={`rounded-full p-2 ${feedback === 'up' ? 'bg-auto-soft text-auto' : 'text-muted hover:bg-surface-3 hover:text-ink'}`}><Icon name="thumbUp" /></button>
            <button aria-pressed={feedback === 'down'} aria-label="Not helpful" onClick={() => setFeedback('down')}
              className={`rounded-full p-2 ${feedback === 'down' ? 'bg-oncall-soft text-oncall' : 'text-muted hover:bg-surface-3 hover:text-ink'}`}><Icon name="thumbDown" /></button>
          </div>
        )}
        {mode === 'suggested' && draft?.model && <span className="font-mono text-xs text-ai" title="Model that wrote this draft">{draft.model}</span>}
        <Button variant="primary" className="ml-auto" icon="send" disabled={!text.trim()} onClick={() => setConfirm(true)}>
          {mode === 'acknowledgement' ? 'Review and send acknowledgement' : 'Review and send'}
        </Button>
      </footer>

      {feedback === 'down' && !t.feedback?.reason && (
        <div className="flex flex-wrap items-center gap-1.5 border-t border-line px-4 py-3">
          <span className="mr-1 text-xs text-ink-2">What should be better?</span>
          {FEEDBACK.map((r) => (
            <button key={r} onClick={() => { store.patch(t.id, { feedback: { rating: 'down', reason: r } }, { kind: 'feedback', text: `Suggested response rated not helpful: ${r}` }, AGENT.name); toast({ tone: 'success', text: 'Thanks. Your feedback improves future suggestions.' }) }}
              className="rounded-full border border-line-strong px-2.5 py-1 text-xs text-ink-2 hover:bg-surface-3 hover:text-ink">{r}</button>
          ))}
        </div>
      )}

      {confirm && (
        <ApprovalDialog
          t={t} text={text} lang={replyLang} mode={mode} edited={edited} unsupported={mode === 'suggested' ? stats.unsupported : 0} escalated={escalated}
          requireConfirm={prefs.confirmBeforeSend}
          onCancel={() => setConfirm(false)} onEdit={() => { setConfirm(false); setEditing(true) }} onSend={send}
        />
      )}
    </section>
  )
}

function StatementView({ statements, onCite, precedents, muted }: { statements: Statement[][]; onCite: (id: string) => void; precedents: Precedent[]; muted?: boolean }) {
  return (
    <div className={`space-y-3 text-[14px] leading-relaxed ${muted ? 'text-ink-2' : 'text-ink'}`}>
      {statements.map((para, i) => (
        <p key={i}>
          {para.map((st, j) => (
            <span key={j}>
              {st.newline && <br />}
              <span
                className={st.kind === 'unsupported' && !muted ? 'rounded-sm bg-review-soft decoration-review decoration-dotted underline-offset-4 [text-decoration-line:underline]' : ''}
                title={st.kind === 'unsupported' && !muted ? 'This statement has no supporting reference' : undefined}
              >
                {st.parts.map((p, k) => {
                  const prev = st.parts[k - 1]
                  if (p.cite) {
                    const punct = st.parts[k + 1]?.text.match(/^[.,;:!?]+/)?.[0] ?? ''
                    return (
                      <span key={k} className="whitespace-nowrap">
                        <CitationChip id={p.cite} known={!!p.known} precedent={precedents.find((x) => x.ticket_id === p.cite)} onClick={() => onCite(p.cite!)} />
                        {punct}
                      </span>
                    )
                  }
                  const text = prev?.cite ? p.text.replace(/^[.,;:!?]+/, '') : p.text
                  return <span key={k}>{text}</span>
                })}
              </span>
              {st.kind === 'unsupported' && !muted && (
                <span className="ml-1 inline-flex items-center gap-0.5 align-middle text-xs font-medium text-review"><Icon name="alert" className="h-3 w-3" />No reference</span>
              )}
              {j < para.length - 1 && !para[j + 1].newline && ' '}
            </span>
          ))}
        </p>
      ))}
    </div>
  )
}

function CitationChip({ id, known, precedent, onClick }: { id: string; known: boolean; precedent?: Precedent; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={known ? `View supporting ticket ${id}: ${precedent?.subject ?? ''}` : `${id} is not in the supporting history`}
      className={`mx-0.5 inline-flex translate-y-[-1px] items-center rounded-full px-2 py-px align-middle font-mono text-xs font-medium transition-colors ${known ? 'bg-accent-soft text-accent hover:bg-accent hover:text-on-accent' : 'bg-oncall-soft text-oncall'}`}
    >
      {id.replace('TKT-', '#')}
      <span className="sr-only">{known ? ` — view supporting ticket ${id}` : ` — unverified reference`}</span>
    </button>
  )
}

function EngineerReference({ t, onCite }: { t: Ticket; onCite: (id: string) => void }) {
  const [view, setView] = useState<'reply' | 'translation'>('reply')
  const draft = t.triage!.draft!
  const showTr = view === 'translation' && t.translation?.draft
  return (
    <details className="group overflow-hidden rounded-2xl border border-line bg-surface shadow-soft" open>
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3">
        <Icon name="file" className="h-4 w-4 text-muted" />
        <span className="text-sm font-semibold text-ink">Technical context for the engineer</span>
        <span className="rounded-full bg-ai-soft px-2.5 py-0.5 text-xs font-medium text-ai">AI draft</span>
        <span className="rounded bg-surface-3 px-1.5 py-0.5 text-xs font-medium text-muted">Internal, not sent</span>
        <Icon name="chevronDown" className="ml-auto h-4 w-4 text-muted transition group-open:rotate-180" />
      </summary>
      <div className="border-t border-line p-4">
        {t.translation?.draft && (
          <div role="group" aria-label="Language" className="mb-3 inline-flex rounded-full border border-line bg-surface-2 p-1 text-xs">
            <button aria-pressed={view === 'reply'} onClick={() => setView('reply')} className={`rounded-full px-3 py-1 font-medium ${view === 'reply' ? 'bg-primary text-on-primary' : 'text-muted hover:text-ink'}`}>{LANG_LABEL[draft.language]}</button>
            <button aria-pressed={view === 'translation'} onClick={() => setView('translation')} className={`rounded-full px-3 py-1 font-medium ${view === 'translation' ? 'bg-primary text-on-primary' : 'text-muted hover:text-ink'}`}>English</button>
          </div>
        )}
        <StatementView statements={analyzeDraft(showTr ? t.translation!.draft! : draft.text, t.triage!.precedents)} precedents={t.triage!.precedents} onCite={onCite} />
        <div className="mt-4 flex items-center gap-3">
          <CopyButton text={draft.text} />
          {draft.model && <span className="font-mono text-xs text-ai">{draft.model}</span>}
          {draft.status === 'INSUFFICIENT_EVIDENCE' && <span className="inline-flex items-center gap-1.5 rounded-full bg-review-soft px-2.5 py-0.5 text-xs font-semibold text-review"><Icon name="info" className="h-3.5 w-3.5" />Insufficient evidence: holding reply</span>}
        </div>
      </div>
    </details>
  )
}

function SentNote({ t }: { t: Ticket }) {
  const last = [...t.messages].reverse().find((m) => m.role === 'agent' && !m.internal)
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-auto/25 bg-auto-soft p-4">
      <Icon name="checkCircle" className="mt-0.5 h-5 w-5 text-auto" />
      <div className="text-sm">
        <p className="font-semibold text-ink">Response sent{last ? ` by ${last.author}` : ''}</p>
        <p className="text-ink-2">
          {t.draft_sent_unedited === true ? 'The suggested response was approved without edits.' : t.draft_sent_unedited === false ? 'The suggested response was edited before approval.' : 'Written and approved by a person.'} Status: {STATUS_LABEL[t.status]}.
        </p>
      </div>
    </div>
  )
}

function Notice({ tone, icon, title, children }: { tone: 'oncall' | 'neutral'; icon: 'lock' | 'info' | 'search'; title: string; children: React.ReactNode }) {
  return (
    <div className={`flex gap-3 rounded-2xl ${tone === 'oncall' ? 'border border-oncall/25 bg-oncall-soft p-4' : ''}`}>
      <Icon name={icon} className={`mt-0.5 h-4 w-4 ${tone === 'oncall' ? 'text-oncall' : 'text-muted'}`} />
      <div className="text-sm">
        <p className="font-semibold text-ink">{title}</p>
        <div className="mt-0.5 text-ink-2">{children}</div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Human approval: nothing reaches the customer without it.
// ---------------------------------------------------------------------------
function ApprovalDialog({ t, text, lang, mode, edited, unsupported, escalated, requireConfirm, onCancel, onEdit, onSend }: {
  t: Ticket; text: string; lang: 'en' | 'de'; mode: Mode; edited: boolean; unsupported: number; escalated: boolean; requireConfirm: boolean
  onCancel: () => void; onEdit: () => void; onSend: (after: WorkflowStatus) => void
}) {
  const [after, setAfter] = useState<WorkflowStatus>(mode === 'acknowledgement' ? 'open' : 'awaiting_customer')
  const [ack, setAck] = useState(!requireConfirm)
  const dialog = useRef<HTMLDivElement>(null)
  const finalText = stripCitations(text)
  const needsAck = unsupported > 0 || (escalated && mode === 'suggested')

  useEffect(() => {
    dialog.current?.querySelector<HTMLElement>('[data-autofocus]')?.focus()
    const on = (e: KeyboardEvent) => e.key === 'Escape' && onCancel()
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  }, [onCancel])

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-scrim backdrop-blur-sm p-0 sm:items-center sm:p-6" onClick={onCancel}>
      <div ref={dialog} role="dialog" aria-modal="true" aria-labelledby="approve-title" onClick={(e) => e.stopPropagation()}
        className="flex max-h-[92dvh] w-full max-w-2xl flex-col glass-strong overflow-hidden rounded-t-3xl border border-line bg-dialog shadow-pop sm:rounded-3xl">
        <header className="border-b border-line px-5 py-4">
          <h2 id="approve-title" className="text-xl font-medium tracking-[-0.015em] text-ink">Approve and send</h2>
          <p className="mt-0.5 text-sm text-muted">To {t.requester.name} &lt;{t.requester.email}&gt;, in {LANG_LABEL[lang]}</p>
        </header>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          <ul className="space-y-1.5 text-sm">
            <Check ok>Reference markers are removed; the customer sees plain text.</Check>
            {mode === 'suggested' && <Check ok={!edited ? true : undefined}>{edited ? 'You edited the suggested response.' : 'Suggested response, unedited.'}</Check>}
            {unsupported > 0 && <Check warn>{unsupported} statement{unsupported > 1 ? 's have' : ' has'} no supporting reference. Remove {unsupported > 1 ? 'them' : 'it'} or confirm {unsupported > 1 ? 'they are' : 'it is'} accurate.</Check>}
            {escalated && mode === 'suggested' && <Check warn>This ticket was flagged for human review: {t.triage?.escalation.reasons.map((r) => r.code.replaceAll('_', ' ').toLowerCase()).join(', ')}.</Check>}
          </ul>
          <div className="rounded-2xl border border-line bg-surface-2 p-4">
            <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-ink">{finalText}</p>
          </div>
          <label className="flex items-center gap-2 text-sm text-ink-2">
            After sending, set status to
            <select value={after} onChange={(e) => setAfter(e.target.value as WorkflowStatus)} className="h-9 rounded-full border border-line bg-surface-2 px-3 text-sm text-ink">
              <option value="awaiting_customer">Awaiting customer</option>
              <option value="resolved">Resolved</option>
              <option value="open">Open</option>
            </select>
          </label>
          {(needsAck || requireConfirm) && (
            <label className="flex items-start gap-2.5 rounded-2xl border border-line p-4 text-sm text-ink">
              <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-0.5 h-4 w-4 accent-[var(--accent)]" data-autofocus />
              I have read this response and confirm it is accurate and contains no promises we cannot keep.
            </label>
          )}
        </div>
        <footer className="flex flex-wrap items-center gap-2 border-t border-line px-5 py-3">
          <Button variant="ghost" onClick={onEdit} icon="pencil">Back to editing</Button>
          <Button variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button variant="primary" className="ml-auto" icon="send" disabled={!ack} onClick={() => onSend(after)}>Approve and send</Button>
        </footer>
      </div>
    </div>
  )
}

function Check({ ok, warn, children }: { ok?: boolean; warn?: boolean; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      <Icon name={warn ? 'alert' : ok ? 'check' : 'pencil'} className={`mt-0.5 h-4 w-4 ${warn ? 'text-review' : ok ? 'text-auto' : 'text-muted'}`} />
      <span className={warn ? 'text-ink' : 'text-ink-2'}>{children}</span>
    </li>
  )
}

function CopyButton({ text }: { text: string }) {
  const toast = useToast()
  const [done, setDone] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setDone(true)
      setTimeout(() => setDone(false), 1500)
    } catch {
      toast({ tone: 'error', text: 'Could not copy. Select the text and copy it manually.' })
    }
  }
  return <Button size="sm" variant="ghost" icon={done ? 'check' : 'copy'} onClick={copy} aria-live="polite">{done ? 'Copied' : 'Copy'}</Button>
}
