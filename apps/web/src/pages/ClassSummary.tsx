import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Lightbulb, Share, UserRoundX } from 'lucide-react'
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

const ORANGE = '#F97316'

export default function ClassSummary() {
  const [activityId, setActivityId, idError] = useActivityId()
  const acts = useAsync(() => api.activities(), [])
  const sum = useAsync(() => (activityId ? api.classSummary(activityId) : Promise.resolve(null)), [activityId])
  const [practice, setPractice] = useState<{ items: string[] } | null>(null)
  const [pErr, setPErr] = useState<string | null>(null)
  const [pLoading, setPLoading] = useState(false)
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
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-[24px] font-bold tracking-tight">{s.activity.title.replace(': ', ', ')}</h2>
                <SubjectChip subject={s.activity.subject} size="sm" />
              </div>
              <label className="mt-3 block">
                <span className="sr-only">Activity and class</span>
                <select className="h-[30px] rounded-[6px] border border-line bg-white px-3 pr-8 text-[13px] font-semibold" value={activityId ?? ''} onChange={(e) => setActivityId(e.target.value)}>
                  {(acts.data ?? []).map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.id === s.activity.id ? `${a.class_name} (${s.students} students)` : `${a.title} · ${a.class_name}`}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <Button variant="secondary" size="lg" className="h-[46px] text-[16px]" icon={<Share className="h-4 w-4" aria-hidden />} onClick={exportSummary}>
              Export summary
            </Button>
          </div>

          <div className="mt-8 grid grid-cols-4 gap-5">
            <div className="card px-6 py-7">
              <p className="label-caps">Submitted</p>
              <p className="mt-2 text-[32px] font-bold leading-none">
                {s.submissions.submitted} <span className="text-[15px] font-medium text-muted">of {s.students}</span>
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
            <div className="card px-6 py-7">
              <p className="label-caps">Most missed criterion</p>
              <p className="mt-2 text-[24px] font-bold leading-tight text-bad-strong">{s.most_missed_criterion ?? '—'}</p>
            </div>
          </div>

          <div className="mt-8 grid grid-cols-2 gap-6">
            <ChartCard title="Errors by type" data={s.errors_by_type.map((e) => ({ name: e.label, value: e.count }))} />
            <ChartCard title={isGrammar ? 'Per-item average' : 'Per-problem average'} data={s.per_problem.map((p) => ({ name: p.label, value: p.average }))} max={10} />
          </div>

          <div className="mt-10 grid grid-cols-[minmax(0,1fr)_362px] gap-6">
            <section aria-labelledby="misc-title">
              <h3 id="misc-title" className="px-2 text-[17px] font-semibold">
                Common misconceptions
              </h3>
              <div className="mt-4 flex flex-col gap-3">
                {s.misconceptions.length === 0 && <p className="card px-6 py-6 text-[14px] text-muted">No repeated errors yet.</p>}
                {s.misconceptions.map((m) => (
                  <article key={m.text} className="card lift px-6 py-6">
                    <div className="flex items-start justify-between gap-6">
                      <p className="text-[15px] font-semibold">
                        &quot;{m.count} of {s.students} students {m.text}&quot;
                      </p>
                      <span className="shrink-0 text-[12px] font-semibold text-gray-400">{m.problems.join(', ')}</span>
                    </div>
                    <span className={`mt-1 inline-block rounded border px-2 py-0.5 text-[11px] font-semibold ${m.error_type === 'computational' ? 'border-warn-border bg-warn-bg text-warn-text' : 'border-bad-border bg-bad-bg text-bad-text'}`}>
                      {s.errors_by_type.find((e) => e.error_type === m.error_type)?.label ?? m.error_type}
                    </span>
                    <div className="mt-4 h-2 overflow-hidden rounded-full bg-[#F5F3F1]" role="meter" aria-valuemin={0} aria-valuemax={s.students} aria-valuenow={m.count} aria-label="Share of students">
                      <div className="h-full rounded-full bg-brand" style={{ width: `${(m.count / Math.max(1, s.students)) * 100}%` }} />
                    </div>
                  </article>
                ))}
              </div>
            </section>
            <section aria-labelledby="insight-title">
              <h3 id="insight-title" className="text-[17px] font-semibold">
                Actionable insights
              </h3>
              <div className="mt-4 rounded-2xl border border-[#FBD5B5] bg-[#FFF1E6] px-8 py-8">
                <span className="flex h-10 w-10 items-center justify-center rounded-ctl bg-brand text-white" aria-hidden>
                  <Lightbulb className="h-5 w-5" />
                </span>
                <h4 className="mt-4 text-[17px] font-semibold text-brand-dark">Suggested reteach focus</h4>
                <p className="mt-2 text-[15px] leading-relaxed text-gray-700">{s.reteach_focus}</p>
                <Button variant="soft" className="mt-5 w-full text-[13px]" onClick={gen} loading={pLoading}>
                  {isGrammar ? 'Generate practice items' : 'Generate practice problems'}
                </Button>
                <p className="mt-3 text-[11px] text-muted">{AI_LABEL}. Counts come from the reviewed grades, not from the AI.</p>
              </div>
              {s.submissions.not_submitted.length > 0 && (
                <div className="card mt-4 px-6 py-5">
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

      <Modal open={!!practice} onClose={() => setPractice(null)} labelledBy="practice-title" className="w-[560px] p-8">
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
    <div className="card px-6 py-7">
      <p className="label-caps">{label}</p>
      <p className="mt-2 text-[32px] font-bold leading-none">
        {value} <span className="text-[15px] font-medium text-muted">{sub}</span>
      </p>
    </div>
  )
}

function ChartCard({ title, data, max }: { title: string; data: { name: string; value: number }[]; max?: number }) {
  return (
    <section className="card px-8 py-8" aria-label={title}>
      <h3 className="text-[17px] font-semibold">{title}</h3>
      <div className="mt-6 h-[290px]" role="img" aria-label={`${title}: ${data.map((d) => `${d.name} ${d.value}`).join(', ')}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }} barCategoryGap="8%">
            <CartesianGrid stroke="#F0EEEC" />
            <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#374151' }} tickLine={false} axisLine={{ stroke: '#374151' }} interval={0} />
            <YAxis tick={{ fontSize: 10, fill: '#374151' }} tickLine={false} axisLine={false} domain={max ? [0, max] : [0, 'auto']} allowDecimals={false} />
            <Tooltip cursor={{ fill: '#FFF1E6' }} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <Bar dataKey="value" fill={ORANGE} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
