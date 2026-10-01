import { useCallback, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Check, ChevronDown, ChevronLeft, ChevronRight, ChevronRight as Go, Filter, Plus } from 'lucide-react'
import type { ActivitySummary, Subject } from '../../lib/types'
import { SUBJECTS, SUBJECT_LIST } from '../../lib/subjects'
import { relativeDay } from '../../lib/format'
import { rovingKeyDown, useDismiss } from '../../lib/a11y'
import { SubjectChip } from '../ui/Chip'
import { Button } from '../ui/Button'
import { EmptyState } from '../ui/States'

const PAGE = 10

function statusOf(a: ActivitySummary) {
  const done = a.papers > 0 && a.to_review === 0
  const target = a.papers === 0 ? `/activities/${a.id}/upload` : done ? `/class-summary?activity=${a.id}` : `/queue?activity=${a.id}`
  const label = a.papers === 0 ? 'No papers yet' : done ? 'Done' : `${a.to_review} to review`
  const tone = a.papers === 0 ? 'bg-soft text-muted ring-line' : done ? 'bg-ok-bg text-ok-text ring-ok-border' : 'bg-accent-light text-accent-text ring-accent-tint'
  return { target, label, tone }
}

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
  const menuBox = useRef<HTMLDivElement>(null)
  const menuBtn = useRef<HTMLButtonElement>(null)
  const closeMenu = useCallback(() => setMenu(false), [])
  useDismiss(menu, closeMenu, menuBox, menuBtn)
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
      <div className="flex flex-col gap-4 border-b border-line px-4 py-4 sm:flex-row sm:items-start sm:justify-between sm:px-6 sm:py-5">
        <div className="min-w-0">
          <h2 id="activities-title" className="text-[17px] font-semibold">
            {title}
          </h2>
          <p className="mt-0.5 text-[13px] text-muted">
            {active} assignment{active === 1 ? '' : 's'} across your classes · grades stay AI-assisted drafts until you approve them
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <div className="relative flex-1 sm:flex-none" ref={menuBox}>
            <Button
              ref={menuBtn}
              variant="secondary"
              className="w-full max-w-full sm:w-auto"
              icon={<Filter className="h-4 w-4 text-muted" aria-hidden />}
              iconRight={<ChevronDown className={`h-4 w-4 text-muted transition-transform ${menu ? 'rotate-180' : ''}`} aria-hidden />}
              aria-expanded={menu}
              aria-haspopup="menu"
              onClick={() => setMenu((m) => !m)}
              onKeyDown={(e) => e.key === 'ArrowDown' && (e.preventDefault(), setMenu(true))}
            >
              <span className="max-w-[160px] truncate">{klass === 'all' ? 'All classes' : klass}</span>
            </Button>
            {menu && (
              <div
                role="menu"
                aria-label="Filter by class"
                onKeyDown={(e) => rovingKeyDown(e, 'menuitemradio')}
                className="animate-pop absolute left-0 z-20 mt-2 w-64 origin-top-left rounded-card border border-line bg-white py-1 shadow-pop sm:left-auto sm:right-0 sm:origin-top-right"
                ref={(el) => el?.querySelector<HTMLElement>('[aria-checked="true"]')?.focus()}
              >
                {['all', ...classes].map((c) => (
                  <button
                    key={c}
                    type="button"
                    role="menuitemradio"
                    aria-checked={klass === c}
                    tabIndex={-1}
                    className={`flex w-full items-center justify-between gap-2 px-4 py-2.5 text-left text-[14px] hover:bg-soft focus:bg-soft focus:outline-none ${klass === c ? 'font-semibold text-brand-dark' : ''}`}
                    onClick={() => {
                      setKlass(c)
                      setMenu(false)
                      setPage(0)
                      menuBtn.current?.focus()
                    }}
                  >
                    {c === 'all' ? 'All classes' : c}
                    {klass === c && <Check className="h-4 w-4 text-brand" aria-hidden />}
                  </button>
                ))}
              </div>
            )}
          </div>
          <Button icon={<Plus className="h-4 w-4" aria-hidden />} onClick={() => navigate('/activities/new')} className="shrink-0">
            New activity
          </Button>
        </div>
      </div>

      <div className="scroll-x flex gap-2 px-4 pt-4 sm:px-6 sm:pt-5" role="group" aria-label="Filter by subject">
        {(['all', ...SUBJECT_LIST] as const).map((s) => (
          <button
            key={s}
            type="button"
            aria-pressed={subject === s}
            onClick={() => {
              setSubject(s)
              setPage(0)
            }}
            className={`pill ${subject === s ? 'pill-on' : 'pill-off'}`}
          >
            {s === 'all' ? 'All subjects' : SUBJECTS[s].label}
          </button>
        ))}
      </div>

      {shown.length === 0 ? (
        <EmptyState title="No activities match" action={<Button variant="secondary" size="sm" className="mt-2" onClick={() => navigate('/activities/new')}>Create an activity</Button>}>
          Try another subject or class, or create a new activity.
        </EmptyState>
      ) : (
        <>
          {/* Cards on phones */}
          <ul className="mt-3 divide-y divide-line border-t border-line md:hidden">
            {shown.map((a) => {
              const st = statusOf(a)
              return (
                <li key={a.id}>
                  <Link to={st.target} className="flex items-center gap-3 px-4 py-4 transition-colors hover:bg-rowhover">
                    <span className="min-w-0 flex-1">
                      <span className="block text-[15px] font-semibold leading-snug text-ink">{a.title}</span>
                      <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1.5 text-[12px] text-muted">
                        <SubjectChip subject={a.subject} size="sm" />
                        <span className={`inline-flex h-6 items-center rounded-full px-2 font-semibold ring-1 ring-inset ${st.tone}`}>{st.label}</span>
                      </span>
                      <span className="mt-1.5 block truncate text-[12px] text-muted">
                        {a.class_name} · {a.papers}
                        {a.roster_size > 0 ? `/${a.roster_size}` : ''} papers · {relativeDay(a.updated_at)}
                      </span>
                    </span>
                    <Go className="h-4 w-4 shrink-0 text-[#8790A6]" aria-hidden />
                  </Link>
                </li>
              )
            })}
          </ul>

          {/* Table on tablet and desktop */}
          <div className="mt-3 hidden overflow-x-auto md:block">
            <table className="w-full text-left">
              <thead>
                <tr className="border-y border-line bg-soft/70 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
                  <th scope="col" className="px-6 py-3">Activity</th>
                  <th scope="col" className="px-4 py-3">Subject</th>
                  <th scope="col" className="hidden px-4 py-3 lg:table-cell">Class</th>
                  <th scope="col" className="px-4 py-3">Papers</th>
                  <th scope="col" className="px-4 py-3">Status</th>
                  <th scope="col" className="px-6 py-3">Updated</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((a) => {
                  const st = statusOf(a)
                  return (
                    <tr key={a.id} className="group cursor-pointer border-b border-line transition-colors last:border-0 hover:bg-rowhover" onClick={() => navigate(st.target)}>
                      <td className="px-6 py-4">
                        <Link to={st.target} onClick={(e) => e.stopPropagation()} className="text-[14px] font-semibold text-ink group-hover:text-brand-dark hover:underline">
                          {a.title}
                        </Link>
                        <span className="mt-0.5 block text-[12px] text-muted lg:hidden">{a.class_name}</span>
                      </td>
                      <td className="px-4 py-4">
                        <SubjectChip subject={a.subject} size="sm" />
                      </td>
                      <td className="hidden px-4 py-4 text-[14px] text-[#3B4260] lg:table-cell">{a.class_name}</td>
                      <td className="whitespace-nowrap px-4 py-4 text-[14px] text-[#3B4260]">
                        <span className="tabular-nums">{a.papers}</span>
                        {a.roster_size > 0 && <span className="text-[13px] text-muted"> / {a.roster_size}</span>}
                      </td>
                      <td className="px-4 py-4">
                        <span className={`inline-flex h-6 items-center whitespace-nowrap rounded-full px-2.5 text-[12px] font-semibold ring-1 ring-inset ${st.tone}`}>{st.label}</span>
                        {a.not_submitted > 0 && <span className="mt-1 block text-[12px] text-muted">{a.not_submitted} not submitted</span>}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-[14px] text-muted">{relativeDay(a.updated_at)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 sm:px-6 sm:py-4">
        <p className="text-[13px] text-muted">
          Showing {shown.length} of {rows.length} activit{rows.length === 1 ? 'y' : 'ies'}
        </p>
        <nav aria-label="Pagination" className="flex items-center gap-1.5">
          <button type="button" className="flex h-9 w-9 items-center justify-center rounded-ctl border border-line text-muted transition-colors hover:bg-soft disabled:opacity-40" disabled={page === 0} onClick={() => setPage(page - 1)} aria-label="Previous page">
            <ChevronLeft className="h-4 w-4" aria-hidden />
          </button>
          {Array.from({ length: pages }, (_, i) => (
            <button
              key={i}
              type="button"
              aria-current={i === page ? 'page' : undefined}
              aria-label={`Page ${i + 1}`}
              onClick={() => setPage(i)}
              className={`h-9 min-w-9 rounded-ctl px-2 text-[14px] font-medium transition-colors ${i === page ? 'bg-navy text-white' : 'border border-line text-ink hover:bg-soft'}`}
            >
              {i + 1}
            </button>
          ))}
          <button type="button" className="flex h-9 w-9 items-center justify-center rounded-ctl border border-line text-muted transition-colors hover:bg-soft disabled:opacity-40" disabled={page >= pages - 1} onClick={() => setPage(page + 1)} aria-label="Next page">
            <ChevronRight className="h-4 w-4" aria-hidden />
          </button>
        </nav>
      </div>
    </section>
  )
}
