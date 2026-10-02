import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
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
import { EmptyState, ErrorState, Loading, Notice } from '../components/ui/States'
import { StudentLabel } from '../components/ui/StudentLabel'

const STATUS_STYLE: Record<string, string> = {
  Approved: 'text-ok-text',
  'Not submitted': 'text-[#8790A6]',
  'Student not identified': 'text-warn-text font-semibold',
  'Needs review': 'text-warn-text',
  'Grading failed': 'text-bad-text',
}

export default function Gradebook() {
  const navigate = useNavigate()
  const [activityId, setActivityId, idError] = useActivityId()
  const [subject, setSubject] = useState<Subject | 'all'>('all')
  const [notice, setNotice] = useState<{ tone: 'ok' | 'bad'; text: string } | null>(null)
  const [sending, setSending] = useState(false)
  const acts = useAsync(() => api.activities(), [])
  const book = useAsync(() => (activityId ? api.gradebook(activityId) : Promise.resolve(null)), [activityId])
  const options = (acts.data ?? []).filter((a) => subject === 'all' || a.subject === subject || a.id === activityId)
  const klass = book.data?.activity.class_name ?? ''

  function exportCsv() {
    if (!book.data) return
    const b = book.data
    downloadCsv(`${b.activity.title.replace(/[^a-z0-9]+/gi, '-')}-gradebook.csv`, [
      ['Student ID', 'Student name', 'Status', ...b.columns, 'Total', 'Out of'],
      ...b.rows.map((r) => [r.student_id ?? '', r.student_name ?? 'Not identified', r.status, ...r.scores, r.total, r.total === null ? null : b.activity.total_points]),
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
          title={
            <>
              Gradebook<span className="hidden sm:inline">: {klass}</span>
            </>
          }
          subtitle={klass}
          right={
            <div className="flex items-center gap-2">
              <Button variant="secondary" className="px-2.5 sm:px-4" icon={<FileSpreadsheet className="h-4 w-4" aria-hidden />} onClick={exportCsv} disabled={!book.data} aria-label="Export CSV" title="Export CSV">
                <span className="hidden lg:inline">Export CSV</span>
              </Button>
              <Button className="px-2.5 sm:px-4" icon={<Send className="h-4 w-4" aria-hidden />} onClick={send} loading={sending} disabled={!book.data} aria-label="Send to school system" title="Send to school system">
                <span className="hidden lg:inline">Send to school system</span>
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
          <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-center">
            <div className="flex min-w-0 items-center gap-3">
            <label className="min-w-0 flex-1 lg:flex-none">
              <span className="sr-only">Activity</span>
              <select className="field h-11 w-full pr-9 font-semibold lg:w-auto lg:min-w-[300px]" value={activityId ?? ''} onChange={(e) => setActivityId(e.target.value)}>
                {options.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.title}
                  </option>
                ))}
              </select>
            </label>
            {book.data && <SubjectChip subject={book.data.activity.subject} size="sm" />}
            </div>
            <span className="mx-1 hidden h-5 w-px bg-line lg:block" aria-hidden />
            <div role="group" aria-label="Filter activities by subject" className="scroll-x -mx-4 flex gap-2 px-4 sm:mx-0 sm:px-0">
              {(['all', ...SUBJECT_LIST] as const).map((s) => (
                <button
                  key={s}
                  aria-pressed={subject === s}
                  onClick={() => {
                    setSubject(s)
                    const first = (acts.data ?? []).find((a) => s === 'all' || a.subject === s)
                    if (first && s !== 'all' && book.data?.activity.subject !== s) setActivityId(first.id)
                  }}
                  type="button"
                  className={`pill ${subject === s ? 'pill-on' : 'pill-off'}`}
                >
                  {s === 'all' ? 'All' : SUBJECTS[s].label}
                </button>
              ))}
            </div>
          </div>

          {book.data && (
            <p className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-muted">
              <span className="w-full font-semibold uppercase tracking-[0.12em] text-[11px] text-muted sm:w-auto">Practice gradebook · not connected to your school system</span>
              <span>
                {book.data.activity.papers - book.data.activity.unidentified} of {book.data.activity.roster_size} students submitted
              </span>
              {book.data.activity.not_submitted > 0 && <span>{book.data.activity.not_submitted} not submitted</span>}
              {book.data.activity.unidentified > 0 && <span className="text-warn-text">{book.data.activity.unidentified} paper not identified</span>}
            </p>
          )}
          {notice && (
            <Notice tone={notice.tone} className="mt-4">
              {notice.text}
            </Notice>
          )}

          <p className="mt-4 text-[12px] text-muted md:hidden">Swipe the table sideways to see every column.</p>
          <div className="card mt-2 overflow-x-auto md:mt-5" tabIndex={0} role="region" aria-label="Gradebook table">
            {book.error ? (
              <ErrorState message={book.error} onRetry={book.reload} />
            ) : !book.data ? (
              <Loading />
            ) : book.data.rows.length === 0 ? (
              <EmptyState title="No students in this class" />
            ) : (
              <table className="w-full min-w-[760px] text-left">
                <thead>
                  <tr className="border-b border-line bg-soft text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
                    <th scope="col" className="sticky left-0 z-10 w-[220px] bg-soft px-4 py-3.5 sm:px-6">Student</th>
                    <th scope="col" className="w-[150px] px-4 py-3.5">Status</th>
                    {book.data.columns.map((c) => (
                      <th key={c} scope="col" className="px-4 py-3.5 text-center">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {book.data.rows.map((r) => (
                    <tr
                      key={r.student_id ?? r.submission_id ?? ''}
                      className={`group border-b border-line transition-colors last:border-0 ${r.just_approved ? 'bg-accent-light' : 'bg-white'} ${r.submission_id ? 'cursor-pointer hover:bg-rowhover' : ''}`}
                      onClick={() => r.submission_id && navigate(`/submissions/${r.submission_id}`)}
                    >
                      <th scope="row" className={`sticky left-0 z-[1] whitespace-nowrap px-4 py-3.5 text-left font-normal transition-colors sm:px-6 ${r.just_approved ? 'bg-accent-light shadow-[inset_4px_0_0_#F97316]' : 'bg-white'} ${r.submission_id ? 'group-hover:bg-rowhover' : ''}`}>
                        <span className="flex items-center gap-3">
                          {r.submission_id ? (
                            <Link to={`/submissions/${r.submission_id}`} onClick={(e) => e.stopPropagation()} className="rounded hover:underline" aria-label={`Open paper for ${r.student_name ?? r.student_id ?? 'unidentified student'}`}>
                              <StudentLabel id={r.student_id} name={r.student_name} />
                            </Link>
                          ) : (
                            <StudentLabel id={r.student_id} name={r.student_name} />
                          )}
                          {r.just_approved && <span className="animate-fade rounded-full bg-accent-strong px-2 py-1 text-[11px] font-semibold text-white">Just approved</span>}
                        </span>
                      </th>
                      <td className={`whitespace-nowrap px-4 py-3.5 text-[13px] ${STATUS_STYLE[r.status] ?? 'text-muted'}`}>{r.status}</td>
                      {r.scores.map((s, i) => (
                        <td key={i} className="px-4 py-3.5 text-center text-[15px] tabular-nums">
                          {s === null ? (
                            <span className="text-[#B7C0D3]" aria-label="Not approved yet">
                              —
                            </span>
                          ) : r.edited[i] ? (
                            <span className="inline-flex flex-col items-center">
                              <span className="font-semibold text-accent-text">{fmtScore(s)}</span>
                              <span className="mt-0.5 rounded bg-accent-light px-1 text-[10px] font-semibold text-accent-text">Edited</span>
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
