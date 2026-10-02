import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Lightbulb, RefreshCw, Share, UserRoundX } from 'lucide-react'
import { api } from '../lib/api'
import { AI_LABEL } from '../lib/subjects'
import { useAsync } from '../lib/useAsync'
import { useActivityId } from '../lib/useActivity'
import { downloadCsv } from '../lib/format'
import { AppShell, TopBar } from '../components/layout/AppShell'
import { Button } from '../components/ui/Button'
import { SubjectChip } from '../components/ui/Chip'
import { Modal } from '../components/ui/Modal'
import { ErrorState, Loading } from '../components/ui/States'

const BLUE = '#2563EB' // accent

export default function ClassSummary() {
  const [activityId, setActivityId, idError] = useActivityId()
  const acts = useAsync(() => api.activities(), [])
  const sum = useAsync(() => (activityId ? api.classSummary(activityId) : Promise.resolve(null)), [activityId])
  const [practice, setPractice] = useState<{ items: string[] } | null>(null)
  const [pErr, setPErr] = useState<string | null>(null)
  const [pLoading, setPLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [rErr, setRErr] = useState<string | null>(null)
  const s = sum.data
  const isGrammar = s?.activity.subject === 'grammar'

  async function gen() {
    if (!activityId) return
    setPLoading(true)
    setPErr(null)
    try {
      setPractice(await api.practice(activityId))
    } catch (e) {
      setPErr((e as Error).message)
      setPractice({ items: [] })
    } finally {
      setPLoading(false)
    }
  }

  // The AI part is generated only when the teacher asks; opening the page never calls the AI.
  async function refreshAi() {
    if (!activityId) return
    setRefreshing(true)
    setRErr(null)
    try {
      const fresh = await api.refreshClassSummary(activityId)
      sum.setData(fresh)
      if (fresh.ai_summary.refresh_failed) setRErr('The AI summary could not be updated right now. The counts above are current.')
    } catch (e) {
      setRErr((e as Error).message)
    } finally {
      setRefreshing(false)
    }
  }

  function exportSummary() {
    if (!s) return
    downloadCsv(`${s.activity.title.replace(/[^a-z0-9]+/gi, '-')}-summary.csv`, [
      ['Activity', s.activity.title],
      ['Papers approved', `${s.approved} of ${s.students}`],
      ['Average score', `${s.average_score} / ${s.out_of}`],
      ['Most missed criterion', s.most_missed_criterion ?? ''],
      [],
      ['Error type', 'Count'],
      ...s.errors_by_type.map((e) => [e.label, e.count]),
      [],
      [isGrammar ? 'Item' : 'Problem', 'Average'],
      ...s.per_problem.map((p) => [p.label, p.average]),
      [],
      ['Misconception', 'Students', 'Where'],
      ...s.misconceptions.map((m) => [m.text, m.count, m.problems.join(' ')]),
      [],
      ['Suggested reteach focus (AI draft)', s.reteach_focus],
    ])
  }

  return (
    <AppShell active="summary" topbar={<TopBar title="Class Summary" />}>
      {idError || sum.error ? (
        <ErrorState message={idError ?? sum.error ?? ''} onRetry={sum.reload} />
      ) : !s ? (
        <Loading label="Building the class summary…" />
      ) : (
        <>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <h2 className="text-[20px] font-bold leading-snug sm:text-[24px]">{s.activity.title.replace(': ', ', ')}</h2>
                <SubjectChip subject={s.activity.subject} size="sm" />
              </div>
              <label className="mt-3 block max-w-full">
                <span className="sr-only">Activity and class</span>
                <select className="field h-10 w-full max-w-full pr-8 text-[13px] font-semibold sm:w-auto" value={activityId ?? ''} onChange={(e) => setActivityId(e.target.value)}>
                  {(acts.data ?? []).map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.id === s.activity.id ? `${a.class_name} (${s.students} students)` : `${a.title} · ${a.class_name}`}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <Button variant="secondary" className="w-full shrink-0 sm:w-auto" icon={<Share className="h-4 w-4" aria-hidden />} onClick={exportSummary}>
              Export summary
            </Button>
          </div>

          <div className="mt-6 grid grid-cols-2 gap-3 sm:mt-8 sm:gap-5 xl:grid-cols-4">
            <div className="card animate-rise px-4 py-5 sm:px-6 sm:py-6">
              <p className="label-caps">Submitted</p>
              <p className="mt-2 text-[26px] font-bold leading-none text-navy sm:text-[32px]">
                {s.submissions.submitted} <span className="text-[14px] font-medium text-muted sm:text-[15px]">of {s.students}</span>
              </p>
              {(s.submissions.not_submitted.length > 0 || s.submissions.unidentified > 0) && (
                <p className="mt-2 text-[12px] text-muted">
                  {s.submissions.not_submitted.length} not submitted
                  {s.submissions.unidentified > 0 && <span className="text-warn-text"> · {s.submissions.unidentified} paper not identified</span>}
                </p>
              )}
            </div>
            <Stat label="Papers approved" value={String(s.approved)} sub={`of ${s.students}`} />
            <Stat label="Average score" value={String(s.average_score)} sub={`/ ${s.out_of}`} />
            <div className="card animate-rise px-4 py-5 sm:px-6 sm:py-6" style={{ animationDelay: '150ms' }}>
              <p className="label-caps">Most missed criterion</p>
              <p className="mt-2 text-[17px] font-bold leading-tight text-bad-text sm:text-[22px]">{s.most_missed_criterion ?? '—'}</p>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 sm:mt-8 sm:gap-6 lg:grid-cols-2">
            <ChartCard title="Errors by type" data={s.errors_by_type.map((e) => ({ name: e.label, value: e.count }))} />
            <ChartCard title={isGrammar ? 'Per-item average' : 'Per-problem average'} data={s.per_problem.map((p) => ({ name: p.label, value: p.average }))} max={10} />
          </div>

          <div className="mt-8 grid grid-cols-1 gap-6 sm:mt-10 xl:grid-cols-[minmax(0,1fr)_362px]">
            <section aria-labelledby="misc-title">
              <div className="flex items-center justify-between gap-4 px-2">
                <h3 id="misc-title" className="text-[17px] font-semibold">
                  Common misconceptions
                </h3>
                {s.ai_summary.stale && (
                  <Button size="sm" variant="secondary" onClick={refreshAi} loading={refreshing} icon={<RefreshCw className="h-3.5 w-3.5" aria-hidden />}>
                    {s.ai_summary.cached ? 'Update AI summary' : 'Name misconceptions with AI'}
                  </Button>
                )}
              </div>
              {s.ai_summary.stale && (
                <p className="mt-2 px-2 text-[12px] text-muted" role="status">
                  {s.ai_summary.cached ? 'Grades changed since the AI summary was written. Counts are current; update to rename the misconceptions.' : 'Showing errors grouped by type. Ask the AI to name the common misconceptions.'}
                </p>
              )}
              {rErr && (
                <p className="mt-2 px-2 text-[13px] text-bad-text" role="alert">
                  {rErr}
                </p>
              )}
              <div className="mt-4 flex flex-col gap-3">
                {s.misconceptions.length === 0 && <p className="card px-6 py-6 text-[14px] text-muted">No repeated errors yet.</p>}
                {s.misconceptions.map((m) => (
                  <article key={m.text} className="card lift px-4 py-5 sm:px-6 sm:py-6">
                    <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
                      <p className="text-[15px] font-semibold">
                        &quot;{m.count} of {s.students} students {m.text}&quot;
                      </p>
                      <span className="shrink-0 text-[12px] font-semibold text-muted">{m.problems.join(', ')}</span>
                    </div>
                    <span className={`mt-1 inline-block rounded border px-2 py-0.5 text-[11px] font-semibold ${m.error_type === 'computational' ? 'border-warn-border bg-warn-bg text-warn-text' : 'border-bad-border bg-bad-bg text-bad-text'}`}>
                      {s.errors_by_type.find((e) => e.error_type === m.error_type)?.label ?? m.error_type}
                    </span>
                    <div className="mt-4 h-2 overflow-hidden rounded-full bg-[#E9EDF5]" role="meter" aria-valuemin={0} aria-valuemax={s.students} aria-valuenow={m.count} aria-label="Share of students">
                      <div className="h-full rounded-full bg-accent" style={{ width: `${(m.count / Math.max(1, s.students)) * 100}%` }} />
                    </div>
                  </article>
                ))}
              </div>
            </section>
            <section aria-labelledby="insight-title">
              <h3 id="insight-title" className="text-[17px] font-semibold">
                Actionable insights
              </h3>
              <div className="on-dark mt-4 rounded-2xl bg-navy bg-[radial-gradient(90%_70%_at_100%_0%,#323C96_0%,transparent_70%)] px-5 py-6 text-white sm:px-8 sm:py-8">
                <span className="flex h-10 w-10 items-center justify-center rounded-ctl bg-accent text-navy-950" aria-hidden>
                  <Lightbulb className="h-5 w-5" />
                </span>
                <h4 className="mt-4 text-[17px] font-semibold text-white">Suggested reteach focus</h4>
                <p className="mt-2 text-[15px] leading-relaxed text-[#DDE2F7]">{s.reteach_focus}</p>
                <Button className="mt-5 w-full" onClick={gen} loading={pLoading}>
                  {isGrammar ? 'Generate practice items' : 'Generate practice problems'}
                </Button>
                <p className="mt-3 text-[11px] text-[#B8C0E8]">{AI_LABEL}. Counts come from the reviewed grades, not from the AI.</p>
              </div>
              {s.submissions.not_submitted.length > 0 && (
                <div className="card mt-4 px-4 py-5 sm:px-6">
                  <h4 className="flex items-center gap-2 text-[15px] font-semibold">
                    <UserRoundX className="h-4 w-4 text-muted" aria-hidden /> Not submitted ({s.submissions.not_submitted.length})
                  </h4>
                  <ul className="mt-3 space-y-1.5 text-[14px]">
                    {s.submissions.not_submitted.map((r) => (
                      <li key={r.student_id} className="flex justify-between gap-3">
                        <span>{r.student_name}</span>
                        <span className="tabular-nums text-muted">{r.student_id}</span>
                      </li>
                    ))}
                  </ul>
                  {s.submissions.unidentified > 0 && (
                    <p className="mt-3 text-[12px] text-muted">One of these may be the unidentified paper. Assign it from the review queue.</p>
                  )}
                </div>
              )}
            </section>
          </div>
        </>
      )}

      <Modal open={!!practice} onClose={() => setPractice(null)} labelledBy="practice-title" className="max-w-[560px] p-5 sm:p-8">
        <h2 id="practice-title" className="text-[20px] font-bold">
          {isGrammar ? 'Practice items' : 'Practice problems'}
        </h2>
        <p className="mt-1 text-[13px] text-muted">For you to use in class. {AI_LABEL}: check each one before using it.</p>
        {pErr ? (
          <p role="alert" className="mt-5 rounded-ctl border border-bad-border bg-bad-bg px-3 py-2 text-[14px] text-bad-text">
            {pErr}
          </p>
        ) : (
          <ol className="mt-5 list-decimal space-y-3 pl-5 text-[15px]">
            {practice?.items.map((it, i) => <li key={i}>{it}</li>)}
          </ol>
        )}
        <div className="mt-6 flex justify-end">
          <Button variant="secondary" onClick={() => setPractice(null)}>
            Close
          </Button>
        </div>
      </Modal>
    </AppShell>
  )
}

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="card animate-rise px-4 py-5 sm:px-6 sm:py-6" style={{ animationDelay: '75ms' }}>
      <p className="label-caps">{label}</p>
      <p className="mt-2 text-[26px] font-bold leading-none text-navy sm:text-[32px]">
        {value} <span className="text-[14px] font-medium text-muted sm:text-[15px]">{sub}</span>
      </p>
    </div>
  )
}

function useNarrow(px = 640) {
  const q = `(max-width: ${px - 1}px)`
  const [narrow, setNarrow] = useState(() => typeof window !== 'undefined' && window.matchMedia(q).matches)
  useEffect(() => {
    const m = window.matchMedia(q)
    const on = () => setNarrow(m.matches)
    m.addEventListener('change', on)
    return () => m.removeEventListener('change', on)
  }, [q])
  return narrow
}

function ChartCard({ title, data, max }: { title: string; data: { name: string; value: number }[]; max?: number }) {
  const narrow = useNarrow()
  return (
    <section className="card px-4 py-5 sm:px-8 sm:py-7" aria-label={title}>
      <h3 className="text-[17px] font-semibold">{title}</h3>
      <div className="mt-4 h-[230px] sm:mt-6 sm:h-[280px]" role="img" aria-label={`${title}: ${data.map((d) => `${d.name} ${d.value}`).join(', ')}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }} barCategoryGap="8%">
            <CartesianGrid stroke="#EEF1F7" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#5B6478' }} tickLine={false} axisLine={{ stroke: '#CBD2E1' }} interval={0} angle={narrow ? -30 : 0} textAnchor={narrow ? 'end' : 'middle'} height={narrow ? 64 : 30} />
            <YAxis tick={{ fontSize: 10, fill: '#5B6478' }} tickLine={false} axisLine={false} domain={max ? [0, max] : [0, 'auto']} allowDecimals={false} />
            <Tooltip cursor={{ fill: '#EFF6FF' }} contentStyle={{ fontSize: 12, borderRadius: 10, border: '1px solid #E3E7F0', fontFamily: 'Poppins, sans-serif' }} />
            <Bar dataKey="value" fill={BLUE} radius={[6, 6, 0, 0]} maxBarSize={56} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
