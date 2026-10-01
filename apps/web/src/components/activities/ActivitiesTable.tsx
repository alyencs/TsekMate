import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, ChevronLeft, ChevronRight, Filter, Plus } from 'lucide-react'
import type { ActivitySummary, Subject } from '../../lib/types'
import { SUBJECTS, SUBJECT_LIST, AI_LABEL } from '../../lib/subjects'
import { relativeDay } from '../../lib/format'
import { SubjectChip } from '../ui/Chip'
import { Button } from '../ui/Button'
import { EmptyState } from '../ui/States'

const PAGE = 10

export function ActivitiesTable({
  activities,
  query = '',
  initialSubject = 'all',
  title = 'Your activities',
}: {
  activities: ActivitySummary[]
  query?: string
  initialSubject?: Subject | 'all'
  title?: string
}) {
  const navigate = useNavigate()
  const [subject, setSubject] = useState<Subject | 'all'>(initialSubject)
  const [klass, setKlass] = useState<string>('all')
  const [menu, setMenu] = useState(false)
  const [page, setPage] = useState(0)
  const classes = useMemo(() => Array.from(new Set(activities.map((a) => a.class_name))).sort(), [activities])
  const rows = activities.filter(
    (a) =>
      (subject === 'all' || a.subject === subject) &&
      (klass === 'all' || a.class_name === klass) &&
      (!query || a.title.toLowerCase().includes(query.toLowerCase())),
  )
  const pages = Math.max(1, Math.ceil(rows.length / PAGE))
  const shown = rows.slice(page * PAGE, page * PAGE + PAGE)
  const active = activities.length

  return (
    <section className="card overflow-hidden" aria-labelledby="activities-title">
      <div className="flex items-start justify-between gap-4 border-b border-line px-6 py-5">
        <div>
          <h2 id="activities-title" className="text-[17px] font-semibold">
            {title}
          </h2>
          <p className="mt-0.5 text-[13px] text-muted">
            {active} active assignment{active === 1 ? '' : 's'} across your classes
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Button variant="secondary" icon={<Filter className="h-4 w-4 text-muted" aria-hidden />} iconRight={<ChevronDown className="h-4 w-4 text-muted" aria-hidden />} aria-expanded={menu} aria-haspopup="listbox" onClick={() => setMenu((m) => !m)}>
              {klass === 'all' ? 'Filter' : klass}
            </Button>
            {menu && (
              <ul role="listbox" aria-label="Filter by class" className="absolute right-0 z-10 mt-2 w-48 rounded-ctl border border-line bg-white py-1 shadow-pop">
                {['all', ...classes].map((c) => (
                  <li key={c}>
                    <button
                      role="option"
                      aria-selected={klass === c}
                      className={`w-full px-3 py-2 text-left text-[14px] hover:bg-gray-50 ${klass === c ? 'font-semibold text-brand-dark' : ''}`}
                      onClick={() => {
                        setKlass(c)
                        setMenu(false)
                        setPage(0)
                      }}
                    >
                      {c === 'all' ? 'All classes' : c}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <Button icon={<Plus className="h-4 w-4" aria-hidden />} onClick={() => navigate('/activities/new')}>
            New activity
          </Button>
        </div>
      </div>

      <div className="flex gap-2 px-6 pt-5" role="group" aria-label="Filter by subject">
        {(['all', ...SUBJECT_LIST] as const).map((s) => (
          <button
            key={s}
            aria-pressed={subject === s}
            onClick={() => {
              setSubject(s)
              setPage(0)
            }}
            className={`h-7 rounded-full px-3 text-[13px] font-medium transition-colors ${subject === s ? 'bg-brand text-white' : 'bg-brand-light text-brand-dark hover:bg-orange-100'}`}
          >
            {s === 'all' ? 'All' : SUBJECTS[s].label}
          </button>
        ))}
      </div>

      {shown.length === 0 ? (
        <EmptyState title="No activities match">Try another subject or class, or create a new activity.</EmptyState>
      ) : (
        <table className="mt-3 w-full text-left">
          <thead>
            <tr className="border-b border-line text-[12px] font-semibold uppercase tracking-wider text-muted">
              <th scope="col" className="px-6 py-3">Activity</th>
              <th scope="col" className="px-4 py-3">Subject</th>
              <th scope="col" className="px-4 py-3">Class</th>
              <th scope="col" className="px-4 py-3">Papers</th>
              <th scope="col" className="px-4 py-3">Status</th>
              <th scope="col" className="px-6 py-3">Last updated</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((a) => {
              const done = a.papers > 0 && a.to_review === 0
              const target = a.papers === 0 ? `/activities/${a.id}/upload` : done ? `/class-summary?activity=${a.id}` : `/queue?activity=${a.id}`
              return (
                <tr key={a.id} className="cursor-pointer border-b border-line last:border-0 hover:bg-[#FFFBF7]" onClick={() => navigate(target)}>
                  <td className="px-6 py-4">
                    <a
                      href={target}
                      onClick={(e) => {
                        e.preventDefault()
                        navigate(target)
                      }}
                      className="text-[15px] font-semibold text-ink hover:underline"
                    >
                      {a.title}
                    </a>
                    {a.to_review > 0 && (
                      <span className="mt-1.5 block w-fit rounded bg-brand-light px-2 py-1 text-[11px] text-brand-dark">{AI_LABEL}</span>
                    )}
                  </td>
                  <td className="px-4 py-4">
                    <SubjectChip subject={a.subject} />
                  </td>
                  <td className="px-4 py-4 text-[15px] text-gray-700">{a.class_name}</td>
                  <td className="px-4 py-4 text-[15px] text-gray-700">{a.papers}</td>
                  <td className="px-4 py-4 text-[15px] font-medium">{a.papers === 0 ? 'No papers yet' : done ? 'Done' : `${a.to_review} to review`}</td>
                  <td className="px-6 py-4 text-[15px] text-muted">{relativeDay(a.updated_at)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}

      <div className="flex items-center justify-between border-t border-line px-6 py-4">
        <p className="text-[13px] text-muted">
          Showing {shown.length} of {rows.length} activit{rows.length === 1 ? 'y' : 'ies'}
        </p>
        <nav aria-label="Pagination" className="flex items-center gap-2">
          <button className="flex h-8 w-8 items-center justify-center rounded-ctl border border-line text-muted disabled:opacity-40" disabled={page === 0} onClick={() => setPage(page - 1)} aria-label="Previous page">
            <ChevronLeft className="h-4 w-4" />
          </button>
          {Array.from({ length: pages }, (_, i) => (
            <button
              key={i}
              aria-current={i === page ? 'page' : undefined}
              onClick={() => setPage(i)}
              className={`h-8 min-w-8 rounded-ctl px-2 text-[14px] font-medium ${i === page ? 'bg-brand text-white' : 'border border-line text-ink'}`}
            >
              {i + 1}
            </button>
          ))}
          <button className="flex h-8 w-8 items-center justify-center rounded-ctl border border-line text-muted disabled:opacity-40" disabled={page >= pages - 1} onClick={() => setPage(page + 1)} aria-label="Next page">
            <ChevronRight className="h-4 w-4" />
          </button>
        </nav>
      </div>
    </section>
  )
}
