import { useState } from 'react'
import { Lock, Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from '../lib/api'
import { fmt, rubricProblems, rubricSum } from '../lib/rubric'
import type { Activity, Criterion } from '../lib/types'
import { SUBJECTS } from '../lib/subjects'
import { Button } from './ui/Button'

/** The activity's rubric: what every paper is scored against. Editable until the first paper is graded. */
export function RubricCard({ activity, onSaved }: { activity: Activity; onSaved: (a: Activity) => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<Criterion[]>([])
  const [total, setTotal] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const noun = SUBJECTS[activity.subject].problemNoun.toLowerCase()
  const errs = editing ? rubricProblems(draft, total) : activity.rubric_errors
  const set = (i: number, patch: Partial<Criterion>) => setDraft((d) => d.map((c, j) => (j === i ? { ...c, ...patch } : c)))

  function start() {
    setDraft(activity.rubric.map((c) => ({ ...c })))
    setTotal(activity.rubric_total)
    setError(null)
    setEditing(true)
  }

  async function save() {
    setSaving(true)
    setError(null)
    try {
      onSaved(await api.updateRubric(activity.id, draft.map((c) => ({ ...c, name: c.name.trim(), points: Number(c.points) })), total))
      setEditing(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className={`card mt-6 px-6 py-5 ${errs.length ? 'border-warn-border' : ''}`} aria-labelledby="rubric-card-title">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 id="rubric-card-title" className="text-[15px] font-semibold">
            Rubric · {fmt(activity.rubric_total)} points per {noun}
          </h2>
          <p className="text-[13px] text-muted">Every paper is scored with these criteria and points.</p>
        </div>
        {activity.rubric_locked ? (
          <span className="flex items-center gap-1.5 text-[12px] text-muted">
            <Lock className="h-3.5 w-3.5" aria-hidden /> Can&apos;t change after grading starts
          </span>
        ) : (
          !editing && (
            <Button variant="secondary" size="sm" icon={<Pencil className="h-3.5 w-3.5" aria-hidden />} onClick={start}>
              Edit rubric
            </Button>
          )
        )}
      </div>

      {editing ? (
        <div className="mt-4">
          <label className="flex items-center gap-3 text-[14px] font-semibold">
            Total points per {noun}
            <input type="number" min={0} step="any" className="field h-9 w-24 text-right" value={total ?? ''} onChange={(e) => setTotal(e.target.value === '' ? null : Number(e.target.value))} />
          </label>
          <table className="mt-3 w-full text-left">
            <thead>
              <tr className="border-b border-line text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
                <th scope="col" className="w-[220px] py-2 pr-3">Criterion</th>
                <th scope="col" className="py-2 pr-3">Description</th>
                <th scope="col" className="w-[80px] py-2 text-right">Points</th>
                <th scope="col" className="w-[40px]"><span className="sr-only">Remove</span></th>
              </tr>
            </thead>
            <tbody>
              {draft.map((c, i) => (
                <tr key={i} className="border-b border-line">
                  <td className="py-1.5 pr-3">
                    <input aria-label={`Criterion ${i + 1} name`} className="field h-9 font-semibold" value={c.name} onChange={(e) => set(i, { name: e.target.value })} />
                  </td>
                  <td className="py-1.5 pr-3">
                    <input aria-label={`Criterion ${i + 1} description`} className="field h-9" value={c.description} onChange={(e) => set(i, { description: e.target.value })} />
                  </td>
                  <td className="py-1.5 text-right">
                    <input aria-label={`Criterion ${i + 1} points`} type="number" min={0} step="any" className="field h-9 w-16 px-2 text-right" value={c.points} onChange={(e) => set(i, { points: Number(e.target.value) })} />
                  </td>
                  <td className="py-1.5 text-center">
                    <button className="rounded p-1 text-gray-400 hover:text-bad-strong" aria-label={`Remove criterion ${i + 1}`} onClick={() => setDraft((d) => d.filter((_, j) => j !== i))}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-3 flex items-center justify-between">
            <button className="flex items-center gap-1.5 text-[14px] font-semibold text-brand-dark hover:underline" onClick={() => setDraft((d) => [...d, { name: '', description: '', points: 0 }])}>
              <Plus className="h-4 w-4" aria-hidden /> Add criterion
            </button>
            <p className="text-[13px] text-muted">
              Criteria add up to <b className="text-ink">{fmt(rubricSum(draft))}</b>
              {total !== null && ` of ${fmt(total)}`} points
            </p>
          </div>
        </div>
      ) : (
        <ul className="mt-3 flex flex-wrap gap-2">
          {activity.rubric.map((c) => (
            <li key={c.name} className="rounded-full border border-line bg-[#F9F7F5] px-3 py-1 text-[13px]" title={c.description}>
              {c.name} <b>{fmt(c.points)}</b>
            </li>
          ))}
        </ul>
      )}

      {errs.length > 0 && (
        <ul aria-live="polite" className="mt-3 list-disc rounded-ctl border border-warn-border bg-warn-bg py-2 pl-8 pr-3 text-[13px] text-warn-text">
          {errs.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
      {error && (
        <p role="alert" className="mt-3 rounded-ctl border border-bad-border bg-bad-bg px-3 py-2 text-[13px] text-bad-text">
          {error}
        </p>
      )}
      {editing && (
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={() => setEditing(false)}>
            Cancel
          </Button>
          <Button size="sm" onClick={save} loading={saving} disabled={errs.length > 0}>
            Save rubric
          </Button>
        </div>
      )}
    </section>
  )
}
