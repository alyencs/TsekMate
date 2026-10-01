import { useState, type ReactNode } from 'react'
import { ArrowUp, ArrowDown, BadgeCheck, FlagTriangleRight, Hourglass, TrendingUp } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { greeting, headerDate } from '../lib/format'
import { getTeacher } from '../lib/session'
import { AppShell, SearchBox, TopBarActions } from '../components/layout/AppShell'
import { ActivitiesTable } from '../components/activities/ActivitiesTable'
import { ErrorState, Loading } from '../components/ui/States'

export default function Dashboard() {
  const [q, setQ] = useState('')
  const dash = useAsync(() => api.dashboard(), [])
  const acts = useAsync(() => api.activities(), [])
  const teacher = getTeacher()
  const name = teacher?.name ?? 'Prof. Ana Reyes'

  return (
    <AppShell
      active="dashboard"
      variant="dashboard"
      queueBadge={dash.data?.queue_badge}
      topbar={
        <>
          <div className="flex-1">
            <h1 className="text-[17px] font-semibold leading-tight">Dashboard</h1>
            <p className="text-[13px] text-muted">{headerDate()}</p>
          </div>
          <SearchBox placeholder="Search activities..." value={q} onChange={setQ} width="w-60" />
          <TopBarActions full />
        </>
      }
    >
      <p className="text-[15px] text-muted">Welcome back,</p>
      <h2 className="mt-1 text-[24px] font-bold tracking-tight">
        {greeting()}, {name}
      </h2>

      {dash.error ? (
        <ErrorState message={dash.error} onRetry={dash.reload} />
      ) : !dash.data ? (
        <Loading label="Loading your dashboard…" />
      ) : (
        <div className="mt-8 grid grid-cols-2 gap-5 xl:grid-cols-4">
          <Stat icon={<Hourglass className="h-4 w-4" />} iconCls="bg-[#FEF9C3] text-[#CA8A04]" value={dash.data.awaiting_review.value} label="Awaiting review" delta={dash.data.awaiting_review.delta} deltaCls="text-brand-dark" />
          <Stat icon={<FlagTriangleRight className="h-4 w-4" />} iconCls="bg-bad-bg text-bad-strong" value={dash.data.flagged.value} label="Flagged for you" delta={dash.data.flagged.delta} deltaCls="text-bad-strong" />
          <Stat icon={<BadgeCheck className="h-4 w-4" />} iconCls="bg-ok-bg text-[#16A34A]" value={dash.data.approved_today.value} label="Approved today" delta={dash.data.approved_today.delta} deltaCls="text-[#16A34A]" />
          <Stat
            icon={<TrendingUp className="h-4 w-4" />}
            iconCls="bg-brand-light text-brand"
            value={dash.data.class_average.value}
            outOf={dash.data.class_average.out_of}
            label="Class average"
            delta={dash.data.class_average.delta_pct}
            suffix="%"
            deltaCls="text-brand-dark"
          />
        </div>
      )}

      <div className="mt-8">
        {acts.error ? <ErrorState message={acts.error} onRetry={acts.reload} /> : !acts.data ? <Loading /> : <ActivitiesTable activities={acts.data} query={q} />}
      </div>
    </AppShell>
  )
}

function Stat({
  icon,
  iconCls,
  value,
  outOf,
  label,
  delta,
  suffix = '',
  deltaCls,
}: {
  icon: ReactNode
  iconCls: string
  value: number
  outOf?: number
  label: string
  delta: number
  suffix?: string
  deltaCls: string
}) {
  return (
    <div className="card lift p-5">
      <div className="flex items-start justify-between">
        <span className={`flex h-9 w-9 items-center justify-center rounded-ctl ${iconCls}`} aria-hidden>
          {icon}
        </span>
        {delta !== 0 && (
          <span className={`flex items-center gap-0.5 text-[12px] font-semibold ${deltaCls}`} aria-label={`${delta > 0 ? 'up' : 'down'} ${Math.abs(delta)}${suffix} since yesterday`}>
            {delta > 0 ? <ArrowUp className="h-3 w-3" aria-hidden /> : <ArrowDown className="h-3 w-3" aria-hidden />}
            {delta > 0 ? '+' : '−'}
            {Math.abs(delta)}
            {suffix}
          </span>
        )}
      </div>
      <p className="mt-4 text-[26px] font-bold leading-none">
        {value}
        {outOf !== undefined && <span className="ml-1 text-[17px] font-medium text-gray-400">/ {outOf}</span>}
      </p>
      <p className="mt-2 text-[13px] text-gray-600">{label}</p>
    </div>
  )
}
