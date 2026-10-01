import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileSpreadsheet, Send } from 'lucide-react'
import { api } from '../lib/api'
import type { Subject } from '../lib/types'
import { SUBJECTS, SUBJECT_LIST } from '../lib/subjects'
import { useAsync } from '../lib/useAsync'
import { useActivityId } from '../lib/useActivity'
import { downloadCsv, fmtScore } from '../lib/format'
import { AppShell, TopBar } from '../components/layout/AppShell'
import { Button } from '../components/ui/Button'
import { SubjectChip } from '../components/ui/Chip'
import { EmptyState, ErrorState, Loading } from '../components/ui/States'

export default function Gradebook() {
  const navigate = useNavigate()
  const [activityId, setActivityId, idError] = useActivityId()
  const [subject, setSubject] = useState<Subject | 'all'>('all')
  const [notice, setNotice] = useState<{ tone: 'ok' | 'bad'; text: string } | null>(null)
  const [sending, setSending] = useState(false)
  const acts = useAsync(() => api.activities(), [])
  const book = useAsync(() => (activityId ? api.gradebook(activityId) : Promise.resolve(null)), [activityId])
  const options = (acts.data ?? []).filter((a) => subject === 'all' || a.subject === subject || a.id === activityId)
  const klass = book.data?.activity.class_name ?? 'Grade 8 Rizal'

  function exportCsv() {
    if (!book.data) return
    const b = book.data
    downloadCsv(`${b.activity.title.replace(/[^a-z0-9]+/gi, '-')}-gradebook.csv`, [
      ['Student ID', ...b.columns, 'Total', 'Out of'],
      ...b.rows.map((r) => [r.student_id, ...r.scores, r.total, r.total === null ? null : b.activity.total_points]),
    ])
  }

  async function send() {
    if (!activityId) return
    setSending(true)
    setNotice(null)
    try {
      const r = await api.sendToSchool(activityId)
      setNotice({ tone: 'ok', text: `${r.accepted} approved grade${r.accepted === 1 ? '' : 's'} packaged. ${r.note}` })
    } catch (e) {
      setNotice({ tone: 'bad', text: (e as Error).message })
    } finally {
      setSending(false)
    }
  }

  return (
    <AppShell
      active="gradebook"
      topbar={
        <TopBar
          title={`Gradebook: ${klass}`}
          right={
            <div className="flex items-center gap-3">
              <Button variant="secondary" icon={<FileSpreadsheet className="h-4 w-4" aria-hidden />} onClick={exportCsv} disabled={!book.data}>
                Export CSV
              </Button>
              <Button icon={<Send className="h-4 w-4" aria-hidden />} onClick={send} loading={sending} disabled={!book.data}>
                Send to school system
              </Button>
            </div>
          }
        />
      }
    >
      {idError ? (
        <ErrorState message={idError} />
      ) : (
        <>
          <div className="flex items-center gap-3">
            <label>
              <span className="sr-only">Activity</span>
              <select className="field h-[34px] w-auto min-w-[262px] pr-9 font-semibold" value={activityId ?? ''} onChange={(e) => setActivityId(e.target.value)}>
                {options.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.title}
                  </option>
                ))}
              </select>
            </label>
            {book.data && <SubjectChip subject={book.data.activity.subject} size="sm" />}
            <span className="mx-2 h-5 w-px bg-line" aria-hidden />
            <div role="group" aria-label="Filter activities by subject" className="flex gap-2">
              {(['all', ...SUBJECT_LIST] as const).map((s) => (
                <button
                  key={s}
                  aria-pressed={subject === s}
                  onClick={() => {
                    setSubject(s)
                    const first = (acts.data ?? []).find((a) => s === 'all' || a.subject === s)
                    if (first && s !== 'all' && book.data?.activity.subject !== s) setActivityId(first.id)
                  }}
                  className={`h-7 rounded-full px-3 text-[13px] font-medium ${subject === s ? 'bg-brand text-white' : 'bg-brand-light text-brand-dark hover:bg-orange-100'}`}
                >
                  {s === 'all' ? 'All' : SUBJECTS[s].label}
                </button>
              ))}
            </div>
          </div>

          <div className="card mt-6 px-7 py-4">
            <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-gray-500">Mock gradebook with sample data</p>
          </div>
          {notice && (
            <p role={notice.tone === 'bad' ? 'alert' : 'status'} className={`mt-4 rounded-ctl border px-4 py-3 text-[14px] ${notice.tone === 'bad' ? 'border-bad-border bg-bad-bg text-bad-text' : 'border-ok-border bg-ok-bg text-ok-text'}`}>
              {notice.text}
            </p>
          )}

          <div className="card mt-6 overflow-x-auto">
            {book.error ? (
              <ErrorState message={book.error} onRetry={book.reload} />
            ) : !book.data ? (
              <Loading />
            ) : book.data.rows.length === 0 ? (
              <EmptyState title="No students in this class" />
            ) : (
              <table className="w-full min-w-[900px] text-left">
                <thead>
                  <tr className="border-b border-line text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
                    <th scope="col" className="w-[160px] px-6 py-7">Student ID</th>
                    {book.data.columns.map((c) => (
                      <th key={c} scope="col" className="px-4 py-7 text-center">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {book.data.rows.map((r) => (
                    <tr
                      key={r.student_id}
                      className={`border-b border-line last:border-0 ${r.just_approved ? 'bg-[#FFF7F0] shadow-[inset_4px_0_0_#F97316]' : ''} ${r.submission_id ? 'cursor-pointer hover:bg-[#FFFBF7]' : ''}`}
                      onClick={() => r.submission_id && navigate(`/submissions/${r.submission_id}`)}
                    >
                      <th scope="row" className="whitespace-nowrap px-6 py-6 text-[15px] font-semibold">
                        <span className="flex items-center gap-3">
                          {r.student_id}
                          {r.just_approved && <span className="rounded-full bg-brand px-2 py-1 text-[11px] font-semibold text-white">Just approved</span>}
                        </span>
                      </th>
                      {r.scores.map((s, i) => (
                        <td key={i} className="px-4 py-6 text-center text-[15px]">
                          {s === null ? (
                            <span className="text-gray-300" aria-label="Not approved yet">
                              —
                            </span>
                          ) : r.edited[i] ? (
                            <span className="inline-flex flex-col items-center">
                              <span className="font-semibold text-brand-dark">{fmtScore(s)}</span>
                              <span className="mt-0.5 rounded bg-brand-light px-1 text-[10px] font-semibold text-brand-dark">Edited</span>
                            </span>
                          ) : (
                            fmtScore(s)
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </AppShell>
  )
}
