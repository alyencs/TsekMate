import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowDownWideNarrow, ChevronDown, CircleCheck, Clock, Filter, FlagTriangleRight, CircleX, UserRoundCheck } from 'lucide-react'
import { api } from '../lib/api'
import type { QueueRow, QueueTab } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useActivityId } from '../lib/useActivity'
import { AI_LABEL } from '../lib/subjects'
import { fmtScore } from '../lib/format'
import { AppShell, TopBar } from '../components/layout/AppShell'
import { Button } from '../components/ui/Button'
import { rovingKeyDown } from '../lib/a11y'
import { SubjectChip } from '../components/ui/Chip'
import { ConfidenceBar } from '../components/ui/ConfidenceBar'
import { StudentLabel } from '../components/ui/StudentLabel'
import { EmptyState, ErrorState, Loading } from '../components/ui/States'

const TABS: { key: QueueTab; label: string }[] = [
  { key: 'needs_review', label: 'Needs review' },
  { key: 'ready', label: 'Ready to approve' },
  { key: 'approved', label: 'Approved' },
  { key: 'all', label: 'All' },
]

export default function Queue() {
  const navigate = useNavigate()
  const [activityId, setActivityId, idError] = useActivityId()
  const [tab, setTab] = useState<QueueTab>('needs_review')
  const [q, setQ] = useState('')
  const [flag, setFlag] = useState('all')
  const [sort, setSort] = useState<'confidence' | 'student'>('confidence')
  const acts = useAsync(() => api.activities(), [])
  const queue = useAsync(() => (activityId ? api.queue(activityId, tab) : Promise.resolve(null)), [activityId, tab])

  const rows = (queue.data?.rows ?? [])
    .filter((r) => !q || `${r.student_id ?? ''} ${r.student_name ?? 'not identified'}`.toLowerCase().includes(q.toLowerCase()))
    .filter((r) => flag === 'all' || (flag === 'none' ? r.chips.length === 0 : r.chips.includes(flag)))
    .sort((a, b) => (sort === 'student' ? (a.student_name ?? '~').localeCompare(b.student_name ?? '~') : 0))
  const allChips = Array.from(new Set((queue.data?.rows ?? []).flatMap((r) => r.chips)))
  const [retrying, setRetrying] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  async function gradeAgain(r: QueueRow) {
    setRetrying(r.submission_id)
    setNotice(null)
    try {
      await api.regrade(r.submission_id)
      navigate(`/activities/${activityId}/grading?return=${r.submission_id}`)
    } catch (e) {
      setNotice((e as Error).message)
      setRetrying(null)
    }
  }
  const open = (r: QueueRow) => navigate(`/submissions/${r.submission_id}${r.focus_problem_order ? `?p=${r.focus_problem_order}` : ''}`)

  return (
    <AppShell active="queue" topbar={<TopBar title="Review Queue" subtitle={AI_LABEL} search={{ placeholder: 'Search students...', value: q, onChange: setQ }} />}>
      {idError ? (
        <ErrorState message={idError} />
      ) : (
        <>
          <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:gap-4">
            <label className="w-full min-w-0 sm:w-auto">
              <span className="sr-only">Activity</span>
              <select className="field h-11 w-full pr-9 font-semibold sm:w-auto sm:min-w-[300px] sm:max-w-[460px]" value={activityId ?? ''} onChange={(e) => setActivityId(e.target.value)}>
                {(acts.data ?? []).map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.title}
                  </option>
                ))}
              </select>
            </label>
            {queue.data && <SubjectChip subject={queue.data.activity.subject} size="sm" />}
          </div>

          <div className="mt-5 flex flex-col gap-3 border-b border-line lg:flex-row lg:items-end lg:justify-between lg:gap-4">
            <div role="tablist" aria-label="Queue" className="scroll-x -mx-4 flex gap-1 px-4 sm:mx-0 sm:px-0" onKeyDown={(e) => rovingKeyDown(e, 'tab')}>
              {TABS.map((t) => (
                <button
                  key={t.key}
                  type="button"
                  role="tab"
                  id={`qtab-${t.key}`}
                  aria-selected={tab === t.key}
                  aria-controls="queue-panel"
                  tabIndex={tab === t.key ? 0 : -1}
                  onClick={() => setTab(t.key)}
                  className={`-mb-px shrink-0 whitespace-nowrap border-b-2 px-3 pb-3 pt-1 text-[14px] transition-colors sm:px-4 ${tab === t.key ? 'border-accent font-semibold text-navy' : 'border-transparent text-muted hover:text-ink'}`}
                >
                  {t.label}{' '}
                  <span className={`ml-1 rounded-full px-1.5 py-0.5 text-[11px] font-semibold ${tab === t.key ? 'bg-navy text-white' : 'bg-soft text-muted'}`}>{queue.data?.counts[t.key] ?? '…'}</span>
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2 pb-3">
              <label className="relative flex h-9 min-w-0 flex-1 items-center rounded-ctl border border-line bg-white pl-8 pr-2 text-[13px] sm:flex-none">
                <Filter className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-[#8790A6]" aria-hidden />
                <span className="sr-only">Filter by flag</span>
                <select value={flag} onChange={(e) => setFlag(e.target.value)} className="w-full min-w-0 appearance-none truncate bg-transparent pr-6 focus:outline-none">
                  <option value="all">Flag: All flags</option>
                  {allChips.map((c) => (
                    <option key={c} value={c}>
                      Flag: {c}
                    </option>
                  ))}
                  <option value="none">Flag: No flags</option>
                </select>
                <ChevronDown className="pointer-events-none absolute right-2 h-3.5 w-3.5 text-[#8790A6]" aria-hidden />
              </label>
              <label className="relative flex h-9 min-w-0 flex-1 items-center rounded-ctl border border-line bg-white pl-8 pr-2 text-[13px] sm:flex-none">
                <ArrowDownWideNarrow className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-[#8790A6]" aria-hidden />
                <span className="sr-only">Sort</span>
                <select value={sort} onChange={(e) => setSort(e.target.value as 'confidence' | 'student')} className="w-full min-w-0 appearance-none truncate bg-transparent pr-6 focus:outline-none">
                  <option value="confidence">Sort: Lowest confidence first</option>
                  <option value="student">Sort: Student name</option>
                </select>
                <ChevronDown className="pointer-events-none absolute right-2 h-3.5 w-3.5 text-[#8790A6]" aria-hidden />
              </label>
            </div>
          </div>
          {notice && (
            <p role="alert" className="animate-fade mt-4 rounded-ctl border border-bad-border bg-bad-bg px-4 py-2.5 text-[14px] text-bad-text">
              {notice}
            </p>
          )}

          <p className="mt-4 flex items-start gap-2 text-[13px] text-muted">
            <UserRoundCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden />
            Scores here are AI suggestions. Nothing reaches the gradebook until you open the paper and approve it.
          </p>
          <div id="queue-panel" role="tabpanel" aria-labelledby={`qtab-${tab}`} className="card mt-4 overflow-hidden">
            {queue.error ? (
              <ErrorState message={queue.error} onRetry={queue.reload} />
            ) : !queue.data ? (
              <Loading />
            ) : rows.length === 0 ? (
              <EmptyState title={tab === 'needs_review' ? 'Nothing needs your review' : 'No papers here'}>
                {tab === 'needs_review' ? 'Every flagged paper has been reviewed. Check the Ready to approve tab.' : 'Upload and grade papers to fill this list.'}
              </EmptyState>
            ) : (
              <>
              <ul className="divide-y divide-line md:hidden">
                {rows.map((r) => {
                  const flags = r.chips.filter((c) => c !== 'Student not identified')
                  return (
                    <li key={r.submission_id} className="px-4 py-4">
                      <div className="flex items-start justify-between gap-3">
                        <StudentLabel id={r.student_id} name={r.student_name} />
                        <span className="shrink-0 text-right">
                          <span className="block text-[15px] font-semibold tabular-nums">{r.score === null ? '—' : `${fmtScore(r.score)} / ${fmtScore(r.score_max)}`}</span>
                          <span className="block text-[11px] text-muted">AI suggestion</span>
                        </span>
                      </div>
                      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-2">
                        <StatusLabel status={r.status} />
                        {r.confidence !== null && <ConfidenceBar value={r.confidence} width="w-16" />}
                      </div>
                      {flags.length > 0 && (
                        <span className="mt-2.5 flex flex-wrap gap-1">
                          {flags.map((c) => (
                            <span key={c} className="inline-flex h-6 items-center gap-1 rounded-full border border-warn-border bg-warn-bg px-2 text-[11px] font-semibold text-warn-text">
                              <FlagTriangleRight className="h-3 w-3" aria-hidden />
                              {c}
                            </span>
                          ))}
                        </span>
                      )}
                      <div className="mt-3 flex gap-2">
                        {r.status === 'failed' && (
                          <Button variant="secondary" size="sm" className="flex-1" onClick={() => gradeAgain(r)} disabled={retrying !== null} aria-label={`Grade again ${r.student_name ?? r.student_id ?? 'unidentified paper'}`}>
                            {retrying === r.submission_id ? 'Starting…' : 'Grade again'}
                          </Button>
                        )}
                        <Button variant={r.status === 'approved' ? 'secondary' : 'primary'} size="sm" className="flex-1" onClick={() => open(r)} aria-label={`${r.status === 'approved' ? 'View' : 'Review'} ${r.student_name ?? r.student_id ?? 'unidentified paper'}`}>
                          {r.status === 'approved' ? 'View' : 'Review'}
                        </Button>
                      </div>
                    </li>
                  )
                })}
              </ul>
              <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[760px] text-left">
                <thead>
                  <tr className="border-b border-line bg-soft/70 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
                    <th scope="col" className="px-6 py-3.5">Student</th>
                    <th scope="col" className="px-4 py-3.5">AI suggested score</th>
                    <th scope="col" className="px-4 py-3.5">Confidence</th>
                    <th scope="col" className="px-4 py-3.5">Flags</th>
                    <th scope="col" className="px-4 py-3.5">Status</th>
                    <th scope="col" className="px-6 py-3.5 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={r.submission_id} className={`border-b border-line transition-colors last:border-0 hover:bg-rowhover ${i === 0 && tab === 'needs_review' ? 'bg-rowhover' : ''}`}>
                      <th scope="row" className="px-6 py-4 text-left font-normal">
                        <StudentLabel id={r.student_id} name={r.student_name} />
                      </th>
                      <td className="px-4 py-5 text-[15px]" title={r.focus_problem_order ? `Problem ${r.focus_problem_order}, the one to check first` : undefined}>
                        {r.score === null ? '—' : `${fmtScore(r.score)} / ${fmtScore(r.score_max)}`}
                      </td>
                      <td className="px-4 py-5">{r.confidence === null ? '—' : <ConfidenceBar value={r.confidence} />}</td>
                      <td className="px-4 py-5">
                        {r.chips.filter((c) => c !== 'Student not identified').length ? (
                          <span className="flex flex-wrap gap-1">
                            {r.chips.filter((c) => c !== 'Student not identified').map((c) => (
                              <span key={c} className="inline-flex h-6 items-center gap-1 rounded-full border border-warn-border bg-warn-bg px-2 text-[11px] font-semibold text-warn-text">
                                <FlagTriangleRight className="h-3 w-3" aria-hidden />
                                {c}
                              </span>
                            ))}
                          </span>
                        ) : (
                          <span className="text-[#8790A6]" aria-label="No flags">
                            —
                          </span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-5">
                        <StatusLabel status={r.status} />
                      </td>
                      <td className="px-6 py-5 text-right">
                        <span className="inline-flex gap-2">
                          {r.status === 'failed' && (
                            <button
                              onClick={() => gradeAgain(r)}
                              disabled={retrying !== null}
                              className="h-9 whitespace-nowrap rounded-ctl border border-brand-tint bg-white px-3 text-[13px] font-semibold text-brand-dark transition-colors hover:bg-brand-light disabled:opacity-50"
                              aria-label={`Grade again ${r.student_name ?? r.student_id ?? 'unidentified paper'}`}
                            >
                              {retrying === r.submission_id ? 'Starting…' : 'Grade again'}
                            </button>
                          )}
                          <button onClick={() => open(r)} className={`h-9 rounded-ctl px-4 text-[13px] font-semibold transition-colors ${r.status === 'approved' ? 'border border-line bg-white text-ink hover:bg-soft' : 'bg-accent-strong text-white shadow-cta hover:bg-accent-dark'}`} aria-label={`${r.status === 'approved' ? 'View' : 'Review'} ${r.student_name ?? r.student_id ?? 'unidentified paper'}`}>
                            {r.status === 'approved' ? 'View' : 'Review'}
                          </button>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
              </>
            )}
          </div>
        </>
      )}
    </AppShell>
  )
}

function StatusLabel({ status }: { status: string }) {
  if (status === 'approved')
    return (
      <span className="flex items-center gap-1.5 text-[13px] font-semibold text-ok-text">
        <CircleCheck className="h-3.5 w-3.5" aria-hidden /> Approved
      </span>
    )
  if (status === 'ready')
    return (
      <span className="flex items-center gap-1.5 text-[13px] font-semibold text-ok-text">
        <CircleCheck className="h-3.5 w-3.5" aria-hidden /> Ready to approve
      </span>
    )
  if (status === 'failed')
    return (
      <span className="flex items-center gap-1.5 text-[13px] font-semibold text-bad-text">
        <CircleX className="h-3.5 w-3.5" aria-hidden /> Grading failed
      </span>
    )
  if (status === 'uploaded' || status === 'grading')
    return <span className="text-[13px] font-medium text-muted">{status === 'grading' ? 'Checking…' : 'Not graded yet'}</span>
  return (
    <span className="flex items-center gap-1.5 text-[13px] font-medium text-muted">
      <Clock className="h-3.5 w-3.5" aria-hidden /> Needs review
    </span>
  )
}
