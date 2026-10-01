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
    .filter((r) => !q || r.student_id.toLowerCase().includes(q.toLowerCase()))
    .filter((r) => flag === 'all' || (flag === 'none' ? r.chips.length === 0 : r.chips.includes(flag)))
    .sort((a, b) => (sort === 'student' ? a.student_id.localeCompare(b.student_id) : 0))
  const allChips = Array.from(new Set((queue.data?.rows ?? []).flatMap((r) => r.chips)))
  const open = (r: QueueRow) => navigate(`/submissions/${r.submission_id}${r.focus_problem_order ? `?p=${r.focus_problem_order}` : ''}`)
  const n = queue.data?.counts[tab] ?? 0
  const countText = { needs_review: 'awaiting your review', ready: 'ready to approve', approved: 'approved', all: 'in this activity' }[tab]

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

          <div role="tablist" aria-label="Queue" className="mt-6 flex gap-2 border-b border-line">
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

          <div className="card mt-8 flex items-center gap-3 px-4 py-3">
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
                <option value="student">Sort: Student ID</option>
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 h-3.5 w-3.5 text-gray-400" aria-hidden />
            </label>
            <p className="ml-auto text-[13px] text-gray-600">
              {n} paper{n === 1 ? '' : 's'} {countText}
            </p>
          </div>

          <div className="card mt-6 overflow-hidden">
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
                    <th scope="col" className="px-6 py-5">Student ID</th>
                    <th scope="col" className="px-4 py-5">Suggested score</th>
                    <th scope="col" className="px-4 py-5">Confidence</th>
                    <th scope="col" className="px-4 py-5">Flags</th>
                    <th scope="col" className="px-4 py-5">Status</th>
                    <th scope="col" className="px-6 py-5 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={r.submission_id} className={`border-b border-line last:border-0 ${i === 0 && tab === 'needs_review' ? 'bg-[#FFFBF7]' : ''}`}>
                      <th scope="row" className="px-6 py-5 text-[16px] font-semibold">
                        {r.student_id}
                      </th>
                      <td className="px-4 py-5 text-[15px]" title={r.focus_problem_order ? `Problem ${r.focus_problem_order}, the one to check first` : undefined}>
                        {r.score === null ? '—' : `${fmtScore(r.score)} / ${fmtScore(r.score_max)}`}
                      </td>
                      <td className="px-4 py-5">{r.confidence === null ? '—' : <ConfidenceBar value={r.confidence} />}</td>
                      <td className="px-4 py-5">
                        {r.chips.length ? (
                          <span className="flex flex-wrap gap-1">
                            {r.chips.map((c) => (
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
                      <td className="px-4 py-5">
                        <StatusLabel status={r.status} />
                      </td>
                      <td className="px-6 py-5 text-right">
                        <button onClick={() => open(r)} className={`h-8 rounded-[6px] px-4 text-[13px] font-semibold ${r.status === 'approved' ? 'border border-line bg-white text-ink hover:bg-gray-50' : 'bg-brand text-white hover:bg-brand-dark'}`} aria-label={`${r.status === 'approved' ? 'View' : 'Review'} ${r.student_id}`}>
                          {r.status === 'approved' ? 'View' : 'Review'}
                        </button>
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
