import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Info, RefreshCw, Send, Sparkles } from 'lucide-react'
import { api } from '../lib/api'
import type { ParentMessage } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { AppShell, TopBar } from '../components/layout/AppShell'
import { rovingKeyDown } from '../lib/a11y'
import { Button } from '../components/ui/Button'
import { SubjectChip } from '../components/ui/Chip'
import { ErrorState, Loading } from '../components/ui/States'

export default function ParentUpdate() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const detail = useAsync(() => api.submission(id), [id])
  const [msg, setMsg] = useState<ParentMessage | null>(null)
  const [lang, setLang] = useState<'en' | 'fil'>('en')
  const [text, setText] = useState<{ en: string; fil: string }>({ en: '', fil: '' })
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [drafting, setDrafting] = useState(false)

  // Opening the page only loads the saved draft. The AI is called when the teacher asks for a draft.
  const load = () => {
    setError(null)
    setMsg(null)
    api
      .savedParentMessage(id)
      .then((m) => {
        setMsg(m)
        setText({ en: m.en, fil: m.fil })
      })
      .catch((e: Error) => setError(e.message))
  }
  useEffect(load, [id])

  async function generate() {
    setDrafting(true)
    setError(null)
    try {
      const m = await api.parentMessage(id)
      setMsg(m)
      setText({ en: m.en, fil: m.fil })
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setDrafting(false)
    }
  }

  async function send() {
    setSending(true)
    try {
      const r = await api.approveParentMessage(id, lang, text[lang])
      setSent(r.note)
      setEditing(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSending(false)
    }
  }

  return (
    <AppShell
      topbar={
        <TopBar
          title={
            <span className="flex min-w-0 items-center gap-3">
              <span className="truncate">Parent update: {detail.data ? detail.data.student_name ?? detail.data.student_id ?? 'Not identified' : '…'}</span>{' '}{detail.data && <span className="hidden sm:inline-flex"><SubjectChip subject={detail.data.activity.subject} size="sm" /></span>}
            </span>
          }
        />
      }
    >
      <div className="mx-auto max-w-[736px]">
        <div role="tablist" aria-label="Language" className="mx-auto flex w-fit gap-1 rounded-full border border-line bg-white p-1 shadow-card" onKeyDown={(e) => rovingKeyDown(e, 'tab')}>
          {(
            [
              ['en', 'English'],
              ['fil', 'Filipino'],
            ] as const
          ).map(([k, l]) => (
            <button key={k} type="button" role="tab" id={`lang-${k}`} aria-selected={lang === k} aria-controls="msg-panel" tabIndex={lang === k ? 0 : -1} onClick={() => setLang(k)} className={`h-9 rounded-full px-5 text-[14px] transition-colors sm:px-6 ${lang === k ? 'bg-brand-strong font-semibold text-white' : 'text-muted hover:bg-soft'}`}>
              {l}
            </button>
          ))}
        </div>

        <section id="msg-panel" role="tabpanel" aria-labelledby={`lang-${lang}`} className="card mt-6 overflow-hidden shadow-pop sm:mt-8">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-soft px-4 py-3 sm:py-4">
            <p className="label-caps">Message preview</p>
            <span className="rounded border border-warn-border bg-warn-bg px-2 py-1 text-[11px] font-semibold text-warn-text">{sent ? 'Approved by you' : 'Draft, needs teacher approval'}</span>
          </div>
          <div className="px-4 py-5 sm:px-8 sm:py-8">
            {error ? (
              <ErrorState message={error} onRetry={msg ? generate : load} />
            ) : drafting ? (
              <Loading label="Drafting a short, kind update…" />
            ) : !msg ? (
              <Loading label="Loading…" />
            ) : !msg.drafted ? (
              <div className="flex flex-col items-center gap-4 py-6 text-center">
                <p className="text-[15px] text-muted">No message drafted yet for this paper.</p>
                <Button onClick={generate} icon={<Sparkles className="h-4 w-4" aria-hidden />}>
                  Draft a message with AI
                </Button>
              </div>
            ) : (
              <>
                <label htmlFor="msg" className="sr-only">
                  Message in {lang === 'en' ? 'English' : 'Filipino'}
                </label>
                <textarea
                  id="msg"
                  rows={6}
                  readOnly={!editing}
                  value={text[lang]}
                  onChange={(e) => setText((t) => ({ ...t, [lang]: e.target.value }))}
                  className={`w-full resize-y rounded-[10px] border border-line px-4 py-4 text-[15px] leading-relaxed sm:px-6 sm:py-6 sm:text-[16px] ${editing ? 'bg-white focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20' : 'bg-soft/60'}`}
                />
                <p className="mt-5 flex items-center gap-3 rounded-[10px] border border-warn-border bg-warn-bg px-4 py-3 text-[13px] text-warn-text">
                  <Info className="h-4 w-4 shrink-0" aria-hidden />
                  Machine-drafted message. Please review before sending.
                </p>
              </>
            )}
          </div>
        </section>

        {sent && (
          <p role="status" className="notice notice-ok animate-fade mt-6">
            Approved. {sent}
          </p>
        )}
        <div className="mt-6 flex flex-col-reverse gap-3 sm:mt-8 sm:flex-row sm:gap-4">
          <Button size="lg" className="w-full sm:flex-1" iconRight={<Send className="h-4 w-4" aria-hidden />} onClick={send} loading={sending} disabled={!msg?.drafted || !!sent || !text[lang].trim()}>
            Approve and send message
          </Button>
          <Button size="lg" variant="secondary" className="w-full sm:w-28" onClick={() => (sent ? navigate(-1) : setEditing((e) => !e))} disabled={!msg?.drafted}>
            {sent ? 'Back' : editing ? 'Done' : 'Edit'}
          </Button>
        </div>
        {msg?.drafted && !sent && (
          <div className="mt-4 text-center">
            <Button variant="link" onClick={generate} disabled={drafting} icon={<RefreshCw className="h-3.5 w-3.5" aria-hidden />}>
              Draft a new version with AI
            </Button>
          </div>
        )}
        <p className="mt-8 text-center text-[13px] text-muted sm:mt-10">Parents will receive this via the TsekMate Parent App or SMS.</p>
      </div>
    </AppShell>
  )
}
