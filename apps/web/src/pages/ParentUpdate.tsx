import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Info, Send } from 'lucide-react'
import { api } from '../lib/api'
import type { ParentMessage } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { AppShell, TopBar } from '../components/layout/AppShell'
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

  const generate = () => {
    setError(null)
    setMsg(null)
    api
      .parentMessage(id)
      .then((m) => {
        setMsg(m)
        setText({ en: m.en, fil: m.fil })
      })
      .catch((e: Error) => setError(e.message))
  }
  useEffect(generate, [id])

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
            <span className="flex items-center gap-3">
              Parent update: {detail.data ? detail.data.student_name ?? detail.data.student_id ?? 'Not identified' : '…'} {detail.data && <SubjectChip subject={detail.data.activity.subject} size="sm" />}
            </span>
          }
        />
      }
    >
      <div className="mx-auto max-w-[736px]">
        <div role="tablist" aria-label="Language" className="mx-auto flex w-fit gap-1 rounded-[10px] border border-line bg-white p-1 shadow-card">
          {(
            [
              ['en', 'English'],
              ['fil', 'Filipino'],
            ] as const
          ).map(([k, l]) => (
            <button key={k} role="tab" aria-selected={lang === k} onClick={() => setLang(k)} className={`h-9 rounded-ctl px-6 text-[15px] ${lang === k ? 'bg-brand font-semibold text-white' : 'text-gray-600 hover:bg-gray-50'}`}>
              {l}
            </button>
          ))}
        </div>

        <section className="card mt-8 overflow-hidden shadow-pop" aria-label="Message preview">
          <div className="flex items-center justify-between border-b border-line bg-[#F9F7F5] px-4 py-4">
            <p className="label-caps">Message preview</p>
            <span className="rounded border border-warn-border bg-warn-bg px-2 py-1 text-[11px] font-semibold text-warn-text">{sent ? 'Approved by you' : 'Draft, needs teacher approval'}</span>
          </div>
          <div className="px-8 py-8">
            {error ? (
              <ErrorState message={error} onRetry={generate} />
            ) : !msg ? (
              <Loading label="Drafting a short, kind update…" />
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
                  className={`w-full resize-y rounded-[10px] border border-line px-6 py-6 text-[16px] leading-relaxed ${editing ? 'bg-white focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20' : 'bg-[#FCFBFA]'}`}
                />
                <p className="mt-7 flex items-center gap-3 rounded-[10px] border border-warn-border/60 bg-[#FEFBF0] px-4 py-4 text-[13px] text-[#CA8A04]">
                  <Info className="h-4 w-4 shrink-0" aria-hidden />
                  Machine-drafted message. Please review before sending.
                </p>
              </>
            )}
          </div>
        </section>

        {sent && (
          <p role="status" className="mt-6 rounded-ctl border border-ok-border bg-ok-bg px-4 py-3 text-[14px] text-ok-text">
            Approved. {sent}
          </p>
        )}
        <div className="mt-8 flex gap-4">
          <Button size="lg" className="h-[60px] flex-1 text-[17px] shadow-md" iconRight={<Send className="h-4 w-4" aria-hidden />} onClick={send} loading={sending} disabled={!msg || !!sent || !text[lang].trim()}>
            Approve and send message
          </Button>
          <Button size="lg" variant="secondary" className="h-[60px] w-28 text-[17px]" onClick={() => (sent ? navigate(-1) : setEditing((e) => !e))} disabled={!msg}>
            {sent ? 'Back' : editing ? 'Done' : 'Edit'}
          </Button>
        </div>
        <p className="mt-10 text-center text-[13px] text-muted">Parents will receive this via the TsekMate Parent App or SMS.</p>
      </div>
    </AppShell>
  )
}
