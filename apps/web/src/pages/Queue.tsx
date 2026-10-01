import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowDownWideNarrow, ChevronDown, CircleCheck, Clock, Filter, FlagTriangleRight, CircleX } from 'lucide-react'
import { api } from '../lib/api'
import type { QueueRow, QueueTab } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useActivityId } from '../lib/useActivity'
import { AI_LABEL } from '../lib/subjects'
import { fmtScore } from '../lib/format'
import { AppShell, TopBar } from '../components/layout/AppShell'
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
          <div className="flex items-center gap-4">
            <label>
              <span className="sr-only">Activity</span>
              <select className="field h-[38px] w-auto min-w-[270px] pr-9 font-semibold" value={activityId ?? ''} onChange={(e) => setActivityId(e.target.value)}>
                {(acts.data ?? []).map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.title}
                  </option>
                ))}
              </select>
            </label>
            {queue.data && <SubjectChip subject={queue.data.activity.subject} size="sm" />}
          </div>

          <div className="mt-6 flex items-end justify-between gap-4 border-b border-line">
          <div role="tablist" aria-label="Queue" className="flex gap-2">
            {TABS.map((t) => (
              <button
                key={t.key}
                role="tab"
                aria-selected={tab === t.key}
                onClick={() => setTab(t.key)}
                className={`-mb-px border-b-2 px-4 pb-2.5 text-[15px] ${tab === t.key ? 'border-brand font-semibold text-brand-dark' : 'border-transparent text-gray-500 hover:text-ink'}`}
              >
                {t.label} ({queue.data?.counts[t.key] ?? '…'})
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2 pb-2">
            <label className="relative flex h-[30px] items-center rounded-ctl border border-line bg-[#F9F7F5] pl-8 pr-2 text-[13px]">
              <Filter className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-gray-400" aria-hidden />
              <span className="sr-only">Filter by flag</span>
              <select value={flag} onChange={(e) => setFlag(e.target.value)} className="appearance-none bg-transparent pr-5 focus:outline-none">
                <option value="all">Flag: All flags</option>
                {allChips.map((c) => (
                  <option key={c} value={c}>
                    Flag: {c}
                  </option>
                ))}
                <option value="none">Flag: No flags</option>
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 h-3.5 w-3.5 text-gray-400" aria-hidden />
            </label>
            <label className="relative flex h-[30px] items-center rounded-ctl border border-line bg-[#F9F7F5] pl-8 pr-2 text-[13px]">
              <ArrowDownWideNarrow className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-gray-400" aria-hidden />
              <span className="sr-only">Sort</span>
              <select value={sort} onChange={(e) => setSort(e.target.value as 'confidence' | 'student')} className="appearance-none bg-transparent pr-5 focus:outline-none">
                <option value="confidence">Sort: Lowest confidence first</option>
                <option value="student">Sort: Student name</option>
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 h-3.5 w-3.5 text-gray-400" aria-hidden />
            </label>
          </div>
          </div>
          {notice && (
            <p role="alert" className="animate-fade mt-4 rounded-ctl border border-bad-border bg-bad-bg px-4 py-2.5 text-[14px] text-bad-text">
              {notice}
            </p>
          )}

          <div className="card mt-5 overflow-hidden">
            {queue.error ? (
              <ErrorState message={queue.error} onRetry={queue.reload} />
            ) : !queue.data ? (
              <Loading />
            ) : rows.length === 0 ? (
              <EmptyState title={tab === 'needs_review' ? 'Nothing needs your review' : 'No papers here'}>
                {tab === 'needs_review' ? 'Every flagged paper has been reviewed. Check the Ready to approve tab.' : 'Upload and grade papers to fill this list.'}
              </EmptyState>
            ) : (
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-line text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
                    <th scope="col" className="px-6 py-5">Student</th>
                    <th scope="col" className="px-4 py-5">Suggested score</th>
                    <th scope="col" className="px-4 py-5">Confidence</th>
                    <th scope="col" className="px-4 py-5">Flags</th>
                    <th scope="col" className="px-4 py-5">Status</th>
                    <th scope="col" className="px-6 py-5 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={r.submission_id} className={`border-b border-line transition-colors last:border-0 hover:bg-[#FFFBF7] ${i === 0 && tab === 'needs_review' ? 'bg-[#FFFBF7]' : ''}`}>
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
                          <span className="text-gray-400" aria-label="No flags">
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
                              className="h-8 whitespace-nowrap rounded-[6px] border border-brand-tint bg-white px-3 text-[13px] font-semibold text-brand-dark transition-colors hover:bg-brand-light disabled:opacity-50"
                              aria-label={`Grade again ${r.student_name ?? r.student_id ?? 'unidentified paper'}`}
                            >
                              {retrying === r.submission_id ? 'Starting…' : 'Grade again'}
                            </button>
                          )}
                          <button onClick={() => open(r)} className={`h-8 rounded-[6px] px-4 text-[13px] font-semibold transition-colors ${r.status === 'approved' ? 'border border-line bg-white text-ink hover:bg-gray-50' : 'bg-brand text-white hover:bg-brand-dark'}`} aria-label={`${r.status === 'approved' ? 'View' : 'Review'} ${r.student_name ?? r.student_id ?? 'unidentified paper'}`}>
                            {r.status === 'approved' ? 'View' : 'Review'}
                          </button>
                        </span>
                      </td>
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
    <span className="flex items-center gap-1.5 text-[13px] font-medium text-gray-500">
      <Clock className="h-3.5 w-3.5" aria-hidden /> Needs review
    </span>
  )
}
