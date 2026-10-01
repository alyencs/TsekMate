import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDown, ArrowRight, ArrowUp, BadgeCheck, Camera, FlagTriangleRight, Hourglass, Sparkles, TrendingUp, UserRoundCheck } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { greeting, headerDate } from '../lib/format'
import { getTeacher } from '../lib/session'
import { AppShell, TopBar } from '../components/layout/AppShell'
import { ActivitiesTable } from '../components/activities/ActivitiesTable'
import { ErrorState, Loading } from '../components/ui/States'
import { TAGLINE } from '../components/ui/Logo'

export default function Dashboard() {
  const [q, setQ] = useState('')
  const dash = useAsync(() => api.dashboard(), [])
  const acts = useAsync(() => api.activities(), [])
  const teacher = getTeacher()
  const name = teacher?.name ?? 'Prof. Ana Reyes'
  const review = dash.data?.activity_id ? `/queue?activity=${dash.data.activity_id}` : '/queue'

  return (
    <AppShell
      active="dashboard"
      variant="dashboard"
      queueBadge={dash.data?.queue_badge}
      topbar={<TopBar title="Dashboard" subtitle={headerDate()} search={{ placeholder: 'Search activities...', value: q, onChange: setQ }} fullActions />}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="text-[14px] text-muted">Welcome back,</p>
          <h2 className="mt-0.5 text-[22px] font-bold leading-tight sm:text-[26px]">
            {greeting()}, <span className="text-navy">{name}</span>
          </h2>
        </div>
        <p className="hidden items-center gap-1.5 text-[13px] font-semibold text-accent-text sm:flex">
          <Sparkles className="h-4 w-4 text-accent" aria-hidden /> {TAGLINE}
        </p>
      </div>

      {dash.error ? (
        <ErrorState message={dash.error} onRetry={dash.reload} />
      ) : !dash.data ? (
        <Loading label="Loading your dashboard…" />
      ) : (
        <div className="mt-6 grid grid-cols-2 gap-3 sm:gap-5 xl:grid-cols-4">
          <Stat i={0} to={review} icon={<Hourglass className="h-4 w-4" />} iconCls="bg-warn-bg text-[#A16207]" value={dash.data.awaiting_review.value} label="Awaiting review" delta={dash.data.awaiting_review.delta} />
          <Stat i={1} to={review} icon={<FlagTriangleRight className="h-4 w-4" />} iconCls="bg-bad-bg text-bad-strong" value={dash.data.flagged.value} label="Flagged for you" delta={dash.data.flagged.delta} />
          <Stat i={2} icon={<BadgeCheck className="h-4 w-4" />} iconCls="bg-ok-bg text-ok-text" value={dash.data.approved_today.value} label="Approved today" delta={dash.data.approved_today.delta} />
          <Stat
            i={3}
            to={dash.data.activity_id ? `/class-summary?activity=${dash.data.activity_id}` : '/class-summary'}
            icon={<TrendingUp className="h-4 w-4" />}
            iconCls="bg-brand-light text-brand"
            value={dash.data.class_average.value}
            outOf={dash.data.class_average.out_of}
            label="Class average"
            delta={dash.data.class_average.delta_pct}
            suffix="%"
          />
        </div>
      )}

      <Workflow reviewTo={review} />

      <div className="mt-6 sm:mt-8">
        {acts.error ? <ErrorState message={acts.error} onRetry={acts.reload} /> : !acts.data ? <Loading /> : <ActivitiesTable activities={acts.data} query={q} />}
      </div>
    </AppShell>
  )
}

/** The grading flow at a glance: the AI drafts, the teacher decides. */
function Workflow({ reviewTo }: { reviewTo: string }) {
  const steps = [
    { icon: Camera, title: 'Upload work', text: 'Photos of handwritten papers' },
    { icon: Sparkles, title: 'AI drafts a grade', text: 'Step by step, from your rubric' },
    { icon: UserRoundCheck, title: 'You review and approve', text: 'Every final grade is yours', you: true },
  ]
  return (
    <section aria-labelledby="flow-title" className="card mt-6 overflow-hidden sm:mt-8">
      <div className="flex flex-col gap-4 p-4 sm:p-5 lg:flex-row lg:items-center lg:gap-6">
        <div className="lg:w-[220px] lg:shrink-0">
          <h2 id="flow-title" className="text-[15px] font-semibold">
            How grading works
          </h2>
          <p className="mt-0.5 text-[13px] text-muted">You stay in control of the final grade.</p>
        </div>
        <ol className="grid flex-1 gap-2 sm:grid-cols-3 sm:gap-3">
          {steps.map(({ icon: Icon, title, text, you }, i) => (
            <li key={title} className={`flex items-center gap-3 rounded-ctl border px-3 py-2.5 ${you ? 'border-accent-tint bg-accent-light' : 'border-line bg-soft'}`}>
              <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${you ? 'bg-accent-strong text-white' : 'bg-white text-brand ring-1 ring-line'}`} aria-hidden>
                <Icon className="h-4 w-4" />
              </span>
              <span className="min-w-0">
                <span className="block text-[13px] font-semibold leading-tight">
                  <span className="sr-only">Step {i + 1}: </span>
                  {title}
                </span>
                <span className="block text-[12px] text-muted">{text}</span>
              </span>
            </li>
          ))}
        </ol>
        <Link to={reviewTo} className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-ctl bg-navy px-4 text-[14px] font-semibold text-white transition-colors hover:bg-navy-700">
          Open review queue <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
      </div>
    </section>
  )
}

function Stat({
  i,
  to,
  icon,
  iconCls,
  value,
  outOf,
  label,
  delta,
  suffix = '',
}: {
  i: number
  to?: string
  icon: ReactNode
  iconCls: string
  value: number
  outOf?: number
  label: string
  delta: number
  suffix?: string
}) {
  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <span className={`flex h-9 w-9 items-center justify-center rounded-ctl ${iconCls}`} aria-hidden>
          {icon}
        </span>
        {delta !== 0 && (
          <span className={`flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[11px] font-semibold sm:text-[12px] ${delta > 0 ? 'bg-ok-bg text-ok-text' : 'bg-bad-bg text-bad-text'}`}>
            {delta > 0 ? <ArrowUp className="h-3 w-3" aria-hidden /> : <ArrowDown className="h-3 w-3" aria-hidden />}
            <span className="sr-only">{delta > 0 ? 'up' : 'down'}</span>
            {Math.abs(delta)}
            {suffix}
            <span className="sr-only"> since yesterday</span>
          </span>
        )}
      </div>
      <p className="mt-3 text-[26px] font-bold leading-none text-navy sm:mt-4 sm:text-[28px]">
        {value}
        {outOf !== undefined && <span className="ml-1 text-[15px] font-medium text-muted sm:text-[17px]">/ {outOf}</span>}
      </p>
      <p className="mt-1.5 text-[13px] text-muted">{label}</p>
    </>
  )
  const cls = 'card lift animate-rise block p-4 sm:p-5'
  const style = { animationDelay: `${i * 50}ms` }
  return to ? (
    <Link to={to} className={`${cls} hover:border-brand-tint`} style={style}>
      {body}
    </Link>
  ) : (
    <div className={cls} style={style}>
      {body}
    </div>
  )
}
