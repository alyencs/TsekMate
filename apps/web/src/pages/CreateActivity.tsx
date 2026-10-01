import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, ChevronUp, CircleCheck, EllipsisVertical, Plus, Sparkles, Trash2 } from 'lucide-react'
import { api } from '../lib/api'
import { rovingKeyDown } from '../lib/a11y'
import type { ActivityInput, Criterion, FeedbackStyle, Subject } from '../lib/types'
import { fmt, rubricProblems, rubricSum } from '../lib/rubric'
import { SUBJECTS, SUBJECT_LIST } from '../lib/subjects'
import { useAsync } from '../lib/useAsync'
import { useAppSettings } from '../lib/appSettings'
import { AppShell, TopBar } from '../components/layout/AppShell'
import { Button } from '../components/ui/Button'
import { SubjectIcon } from '../components/ui/Chip'
import { Toggle } from '../components/ui/Toggle'

interface ProblemDraft {
  key: number
  text: string
  expected_answer: string
  sample_solution: string
  rule: string
}

let nextKey = 1
const blank = (): ProblemDraft => ({ key: nextKey++, text: '', expected_answer: '', sample_solution: '', rule: '' })

export default function CreateActivity() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const classes = useAsync(() => api.profile(), [])
  const [title, setTitle] = useState('')
  const [klass, setKlass] = useState('BS Computer Science 2A')
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [subject, setSubject] = useState<Subject>('math')
  const [problems, setProblems] = useState<ProblemDraft[]>(() => [blank()])
  const [open, setOpen] = useState<number>(problems[0].key)
  // The rubric starts empty: the teacher adds criteria, or accepts an AI draft. Nothing is prefilled.
  const [rubric, setRubric] = useState<Criterion[]>([])
  const [rubricTotal, setRubricTotal] = useState<number | null>(null)
  const [rubricTouched, setRubricTouched] = useState(false)
  const [acceptAlt, setAcceptAlt] = useState(true)
  const [requireUnits, setRequireUnits] = useState(true)
  const [style, setStyle] = useState<FeedbackStyle>('hint_only')
  const [menu, setMenu] = useState<number | null>(null)
  useEffect(() => {
    if (menu === null) return
    const onDown = (e: PointerEvent) => !(e.target as HTMLElement).closest('[data-rubric-menu]') && setMenu(null)
    document.addEventListener('pointerdown', onDown)
    return () => document.removeEventListener('pointerdown', onDown)
  }, [menu])
  const [errors, setErrors] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [step, setStep] = useState(1)
  const [rubricMode, setRubricMode] = useState<'manual' | 'ai'>('manual')
  const [rubricFromAi, setRubricFromAi] = useState(false)
  const [draftOpen, setDraftOpen] = useState(false) // an AI draft exists that was not used or discarded yet
  const appSettings = useAppSettings()
  const appliedDefaults = useRef(false)
  useEffect(() => {
    // Teacher defaults from Settings (feedback style, alternate methods, rubric mode) for a new activity.
    if (!appSettings || appliedDefaults.current) return
    appliedDefaults.current = true
    setStyle(appSettings.default_feedback_style)
    setAcceptAlt(appSettings.default_accept_alternate)
    setRubricMode(appSettings.default_rubric_mode)
  }, [appSettings])
  const refs = [useRef<HTMLElement>(null), useRef<HTMLElement>(null), useRef<HTMLElement>(null)]
  const cfg = SUBJECTS[subject]

  // scroll-spy for the stepper
  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) setStep(Number((e.target as HTMLElement).dataset.step))
        })
      },
      { rootMargin: '-40% 0px -50% 0px' },
    )
    refs.forEach((r) => r.current && obs.observe(r.current))
    return () => obs.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // An earlier "can't save" list goes stale as soon as the rubric changes; the live message below takes over.
  useEffect(() => setErrors([]), [rubric, rubricTotal])

  const total = rubricSum(rubric)
  const rubricErrs = rubricProblems(rubric, rubricTotal)
  const setP = (key: number, patch: Partial<ProblemDraft>) => setProblems((ps) => ps.map((p) => (p.key === key ? { ...p, ...patch } : p)))
  const setC = (i: number, patch: Partial<Criterion>) => setRubric((rs) => rs.map((c, j) => (j === i ? { ...c, ...patch } : c)))

  async function save() {
    const errs: string[] = []
    if (!title.trim()) errs.push('Add an activity title.')
    const filled = problems.filter((p) => p.text.trim() || p.expected_answer.trim())
    if (!filled.length) errs.push(`Add at least one ${cfg.problemNoun.toLowerCase()}.`)
    filled.forEach((p, i) => {
      if (!p.text.trim() || !p.expected_answer.trim()) errs.push(`${cfg.problemNoun} ${i + 1} needs both the ${cfg.problemTextLabel.toLowerCase()} and the ${cfg.expectedLabel.toLowerCase()}.`)
    })
    if (draftOpen) errs.push('Use or discard the AI-generated rubric draft before saving.')
    errs.push(...rubricErrs)
    setRubricTouched(true)
    setErrors(errs)
    if (errs.length) return
    const input: ActivityInput = {
      title: title.trim(),
      subject,
      class_name: klass,
      date,
      settings: { accept_alternate: acceptAlt, require_units: subject === 'science' && requireUnits, feedback_style: style },
      problems: filled.map((p, i) => ({ order: i + 1, text: p.text, expected_answer: p.expected_answer, sample_solution: p.sample_solution, rule: p.rule })),
      rubric: rubric.map((c) => ({ ...c, name: c.name.trim(), points: Number(c.points) })),
      rubric_total: rubricTotal,
    }
    setSaving(true)
    try {
      const a = await api.createActivity(input)
      navigate(`/activities/${a.id}/upload`)
    } catch (e) {
      setErrors([(e as Error).message])
      setSaving(false)
    }
  }

  const steps = ['Details', subject === 'grammar' ? 'Items and key' : 'Problems and key', 'Rubric']
  return (
    <AppShell
      active="activities"
      topbar={<TopBar title="New activity" search={{ placeholder: 'Search...', value: q, onChange: setQ }} />}
      footer={
        <>
          <p className="hidden text-[13px] text-muted sm:block">Nothing is graded until you upload papers.</p>
          <div className="flex w-full gap-3 sm:w-auto">
            <Button variant="secondary" size="lg" className="flex-1 sm:w-28 sm:flex-none" onClick={() => navigate(-1)}>
              Cancel
            </Button>
            <Button size="lg" className="flex-[2] sm:w-[160px] sm:flex-none" onClick={save} loading={saving}>
              Save activity
            </Button>
          </div>
        </>
      }
    >
      <div className="mx-auto max-w-[896px]">
        <ol className="scroll-x -mx-4 flex items-center gap-2 px-4 sm:mx-0 sm:justify-center sm:gap-3 sm:px-0" aria-label="Form sections">
          {steps.map((s, i) => (
            <li key={s} className="flex shrink-0 items-center gap-2 sm:gap-3">
              {i > 0 && <span className="h-px w-5 bg-line sm:w-12" aria-hidden />}
              <button type="button" onClick={() => refs[i].current?.scrollIntoView({ behavior: 'smooth', block: 'start' })} className="flex items-center gap-2 rounded-full py-1 pr-2" aria-current={step === i + 1 ? 'step' : undefined}>
                <span className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold ${step === i + 1 ? 'bg-navy text-white' : 'border border-line bg-white text-muted'}`}>{i + 1}</span>
                <span className={`whitespace-nowrap text-[13px] sm:text-[15px] ${step === i + 1 ? 'font-semibold text-ink' : 'text-muted'}`}>{s}</span>
              </button>
            </li>
          ))}
        </ol>

        {/* ---------------- details */}
        <section ref={refs[0]} data-step={1} className="scroll-mt-24 pt-8 sm:pt-10" aria-label="Details">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-[1fr_210px_190px]">
            <label className="text-[14px] font-semibold sm:col-span-2 lg:col-span-1">
              Activity title
              <input className="field mt-2 h-12 font-normal" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Solving Linear Equations: Quiz 1" />
            </label>
            <label className="text-[14px] font-semibold">
              Class
              <select className="field mt-2 h-12 font-normal" value={klass} onChange={(e) => setKlass(e.target.value)}>
                {(classes.data?.classes ?? [klass]).map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
            <label className="text-[14px] font-semibold">
              Date
              <input type="date" className="field mt-2 h-12 font-normal" value={date} onChange={(e) => setDate(e.target.value)} />
            </label>
          </div>

          <fieldset className="mt-8">
            <legend className="text-[15px] font-semibold">Subject</legend>
            <div className="mt-3 grid grid-cols-3 gap-2 sm:gap-4" role="radiogroup" aria-label="Subject" onKeyDown={(e) => rovingKeyDown(e, 'radio')}>
              {SUBJECT_LIST.map((s) => {
                const on = s === subject
                return (
                  <button
                    key={s}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    tabIndex={on ? 0 : -1}
                    onClick={() => setSubject(s)}
                    className={`relative flex h-[108px] flex-col items-center justify-center gap-2 rounded-card border bg-white px-2 text-center transition-[border-color,box-shadow] sm:h-[136px] sm:gap-3 ${on ? 'border-brand shadow-[0_0_0_1px_#4F46E5,0_8px_20px_-12px_rgba(79,70,229,0.5)]' : 'border-line hover:border-brand-tint'}`}
                  >
                    {on && <CircleCheck className="absolute right-2 top-2 h-4 w-4 fill-brand text-white sm:right-4 sm:top-4" aria-hidden />}
                    <span className={`flex h-10 w-10 items-center justify-center rounded-full sm:h-12 sm:w-12 ${on ? 'bg-brand-light text-brand' : 'bg-[#E9EDF5] text-muted'}`}>
                      <SubjectIcon subject={s} className="h-5 w-5" />
                    </span>
                    <span className={`text-[13px] font-semibold leading-tight sm:text-[16px] ${on ? 'text-ink' : 'text-muted'}`}>{SUBJECTS[s].label}</span>
                  </button>
                )
              })}
            </div>
          </fieldset>
        </section>

        {/* ---------------- problems */}
        <section ref={refs[1]} data-step={2} className="scroll-mt-24 pt-10 sm:pt-14" aria-labelledby="problems-title">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="problems-title" className="text-[17px] font-semibold">
              {subject === 'grammar' ? 'Items and answer key' : 'Problems and answer key'}
            </h2>
            <p className="text-[13px] text-muted">
              {problems.length} {problems.length === 1 ? cfg.problemNoun.toLowerCase() : cfg.problemsNoun} total
            </p>
          </div>
          <div className="mt-5 flex flex-col gap-4">
            {problems.map((p, i) =>
              p.key === open ? (
                <div key={p.key} className="card animate-fade px-4 py-5 sm:px-6 sm:py-6">
                  <div className="flex items-center justify-between">
                    <button type="button" className="label-caps flex items-center gap-1 rounded" onClick={() => setOpen(-1)} aria-expanded="true">
                      {cfg.problemNoun} {i + 1} <ChevronUp className="h-3.5 w-3.5" aria-hidden />
                    </button>
                    <button
                      type="button"
                      className="flex h-9 w-9 items-center justify-center rounded-ctl text-[#8790A6] hover:bg-bad-bg hover:text-bad-strong disabled:opacity-30"
                      aria-label={`Delete ${cfg.problemNoun.toLowerCase()} ${i + 1}`}
                      disabled={problems.length === 1}
                      onClick={() => setProblems((ps) => ps.filter((x) => x.key !== p.key))}
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                    </button>
                  </div>
                  <label className="label-caps mt-5 block">
                    {cfg.problemTextLabel}
                    <textarea className="field-soft mt-2 block h-[70px] py-3 text-[15px] normal-case tracking-normal text-ink sm:text-[16px]" value={p.text} onChange={(e) => setP(p.key, { text: e.target.value })} />
                  </label>
                  {subject === 'grammar' ? (
                    <>
                      <label className="label-caps mt-5 block">
                        {cfg.expectedLabel}
                        <textarea className="field-soft mt-2 block h-[70px] py-3 text-[15px] normal-case tracking-normal text-ink sm:text-[16px]" value={p.expected_answer} onChange={(e) => setP(p.key, { expected_answer: e.target.value })} />
                      </label>
                      <label className="label-caps mt-5 block">
                        Grammar rule being tested
                        <input className="field-soft mt-2 block h-[46px] text-[15px] normal-case tracking-normal text-ink sm:text-[16px]" value={p.rule} onChange={(e) => setP(p.key, { rule: e.target.value })} />
                      </label>
                    </>
                  ) : (
                    <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-[minmax(0,240px)_minmax(0,1fr)]">
                      <label className="label-caps block">
                        {cfg.expectedLabel}
                        <input className="field-soft mt-2 block h-[46px] text-[15px] normal-case tracking-normal text-ink sm:text-[16px]" value={p.expected_answer} onChange={(e) => setP(p.key, { expected_answer: e.target.value })} />
                      </label>
                      <label className="label-caps block">
                        Sample solution (optional)
                        <input className="field-soft mt-2 block h-[46px] text-[15px] normal-case tracking-normal text-ink sm:text-[16px]" value={p.sample_solution} onChange={(e) => setP(p.key, { sample_solution: e.target.value })} />
                      </label>
                    </div>
                  )}
                </div>
              ) : (
                <button type="button" key={p.key} onClick={() => setOpen(p.key)} className="card flex h-14 items-center gap-3 px-4 text-left transition-colors hover:border-brand-tint sm:gap-4 sm:px-6" aria-expanded="false">
                  <span className="text-[13px] font-semibold text-[#8790A6]">{String(i + 1).padStart(2, '0')}</span>
                  <span className="min-w-0 flex-1 truncate text-[15px]">{p.text ? `${p.text.slice(0, 40)}${p.text.length > 40 ? '...' : ''}` : <span className="text-[#8790A6]">Empty {cfg.problemNoun.toLowerCase()}</span>}</span>
                  <ChevronDown className="h-4 w-4 text-[#8790A6]" aria-hidden />
                </button>
              ),
            )}
            <button
              type="button"
              onClick={() => {
                const b = blank()
                setProblems((ps) => [...ps, b])
                setOpen(b.key)
              }}
              className="flex h-14 items-center justify-center gap-2 rounded-card border-2 border-dashed border-[#CBD2E1] bg-page text-[15px] font-medium text-muted transition-colors hover:border-brand-tint hover:bg-brand-light hover:text-brand-dark"
            >
              <Plus className="h-4 w-4" aria-hidden /> Add {cfg.problemNoun.toLowerCase()}
            </button>
          </div>
        </section>

        {/* ---------------- rubric */}
        <section ref={refs[2]} data-step={3} className="scroll-mt-24 pt-10 sm:pt-14" aria-labelledby="rubric-title">
          <div className="flex items-center justify-between">
            <h2 id="rubric-title" className="text-[17px] font-semibold">
              Rubric
            </h2>
          </div>
          <div role="radiogroup" aria-label="How to make the rubric" className="mt-4 grid grid-cols-2 rounded-[12px] border border-line bg-white p-1 sm:inline-grid" onKeyDown={(e) => rovingKeyDown(e, 'radio')}>
            {(
              [
                ['manual', 'Create your own rubric'],
                ['ai', 'Generate rubric with AI'],
              ] as const
            ).map(([m, label]) => (
              <button
                key={m}
                type="button"
                role="radio"
                aria-checked={rubricMode === m}
                tabIndex={rubricMode === m ? 0 : -1}
                onClick={() => {
                  setRubricMode(m)
                  if (m === 'manual') setDraftOpen(false) // leaving AI mode discards the draft
                }}
                className={`flex min-h-[40px] items-center justify-center gap-1.5 rounded-[9px] px-3 text-center text-[13px] leading-tight transition-colors sm:px-4 sm:text-[14px] ${rubricMode === m ? 'bg-navy font-semibold text-white' : 'text-muted hover:text-ink'}`}
              >
                {m === 'ai' && <Sparkles className="h-3.5 w-3.5" aria-hidden />}
                {label}
              </button>
            ))}
          </div>
          {rubricMode === 'ai' && (
            <AiRubricPanel
              subject={subject}
              title={title}
              problems={problems}
              onDraftChange={setDraftOpen}
              onUse={(criteria, points) => {
                setRubric(criteria)
                setRubricTotal(points)
                setRubricFromAi(true)
                setDraftOpen(false)
                setRubricMode('manual')
              }}
              onCancel={() => {
                setDraftOpen(false)
                setRubricMode('manual')
              }}
            />
          )}
          {rubricMode === 'manual' && rubricFromAi && (
            <p className="mt-4 text-[13px] text-muted">This rubric started from an AI-generated draft that you accepted. You can still edit everything below.</p>
          )}
          {rubricMode === 'ai' ? null : (
            <>
            <label className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-2 text-[14px] font-semibold sm:text-[15px]">
              Total points per {cfg.problemNoun.toLowerCase()}
              <input
                type="number"
                min={0}
                step="any"
                aria-describedby="rubric-total-help"
                className="field h-10 w-24 text-right font-semibold"
                value={rubricTotal ?? ''}
                placeholder="e.g. 10"
                onChange={(e) => setRubricTotal(e.target.value === '' ? null : Number(e.target.value))}
                onBlur={() => setRubricTouched(true)}
              />
              <span id="rubric-total-help" className="text-[13px] font-normal text-muted">
                The criteria points must add up to this number.
              </span>
            </label>
            <div className="card mt-4 overflow-visible">
              <table className="rtable w-full text-left">
                <thead>
                  <tr className="border-b border-line bg-soft text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
                    <th scope="col" className="w-[240px] rounded-tl-card px-6 py-5">Criterion</th>
                    <th scope="col" className="px-4 py-5">Description</th>
                    <th scope="col" className="w-[90px] px-2 py-5 text-right">Points</th>
                    <th scope="col" className="w-[60px] rounded-tr-card py-5"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {rubric.length === 0 && (
                    <tr className="border-b border-line">
                      <td colSpan={4} className="px-6 py-8 text-center text-[15px] text-muted">
                        No criteria yet. Choose <b className="text-ink">Add criterion</b>, or generate a draft with AI and edit it.
                      </td>
                    </tr>
                  )}
                  {rubric.map((c, i) => (
                    <tr key={i} className="border-b border-line max-md:px-4">
                      <td className="px-6 py-2">
                        <input aria-label={`Criterion ${i + 1} name`} placeholder="Criterion name" className="w-full rounded px-1 py-2 text-[15px] font-semibold focus:bg-soft focus:outline-none focus:ring-2 focus:ring-brand/20" value={c.name} onChange={(e) => setC(i, { name: e.target.value })} />
                      </td>
                      <td className="px-4 py-2">
                        <input aria-label={`Criterion ${i + 1} description`} placeholder="What earns these points" className="w-full rounded px-1 py-2 text-[14px] text-muted focus:bg-soft focus:outline-none focus:ring-2 focus:ring-brand/20" value={c.description} onChange={(e) => setC(i, { description: e.target.value })} />
                      </td>
                      <td className="px-2 py-2 text-right">
                        <input aria-label={`Criterion ${i + 1} points`} type="number" min={0} step="any" className="w-14 rounded px-1 py-2 text-right text-[15px] font-semibold [appearance:textfield] focus:bg-soft focus:outline-none focus:ring-2 focus:ring-brand/20 [&::-webkit-inner-spin-button]:appearance-none" value={c.points} onChange={(e) => setC(i, { points: Number(e.target.value) })} />
                      </td>
                      <td className="relative py-2 text-center" data-rubric-menu>
                        <button type="button" className="flex h-9 w-9 items-center justify-center rounded-ctl text-[#8790A6] hover:bg-soft hover:text-ink" aria-label={`Options for ${c.name || 'criterion'}`} aria-expanded={menu === i} onClick={() => setMenu(menu === i ? null : i)}>
                          <EllipsisVertical className="h-4 w-4" aria-hidden />
                        </button>
                        {menu === i && (
                          <div role="menu" aria-label={`Options for ${c.name || 'criterion'}`} onKeyDown={(e) => { if (e.key === 'Escape') setMenu(null); rovingKeyDown(e, 'menuitem') }} className="animate-pop absolute right-2 top-11 z-10 w-36 rounded-ctl border border-line bg-white py-1 text-left shadow-pop">
                            <button type="button" role="menuitem" className="w-full px-3 py-2.5 text-left text-[14px] hover:bg-soft disabled:opacity-40" disabled={i === 0} onClick={() => { setRubric((rs) => { const r = [...rs]; [r[i - 1], r[i]] = [r[i], r[i - 1]]; return r }); setMenu(null) }}>Move up</button>
                            <button type="button" role="menuitem" className="w-full px-3 py-2.5 text-left text-[14px] text-bad-strong hover:bg-soft" onClick={() => { setRubric((rs) => rs.filter((_, j) => j !== i)); setMenu(null) }}>Delete</button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                  <tr className="rtotal bg-soft">
                    <td colSpan={2} className="rounded-bl-card px-6 py-5 text-right text-[13px] font-semibold uppercase tracking-wider text-[#8790A6]">
                      Criteria total
                    </td>
                    <td className={`whitespace-nowrap px-3 py-5 text-right text-[20px] font-bold ${rubricTotal !== null && total !== rubricTotal ? 'text-bad-strong' : 'text-navy'}`}>
                      {fmt(total)}
                      {rubricTotal !== null && <span className="text-[14px] font-semibold text-muted"> / {fmt(rubricTotal)}</span>}
                    </td>
                    <td className="rounded-br-card" />
                  </tr>
                </tbody>
              </table>
            </div>
            </>
          )}
          {rubricMode === 'manual' && (
            <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
              <button type="button" className="flex items-center gap-1.5 rounded text-[15px] font-semibold text-brand-dark hover:underline" onClick={() => setRubric((rs) => [...rs, { name: '', description: '', points: 0 }])}>
                <Plus className="h-4 w-4" aria-hidden /> Add criterion
              </button>
              {rubricTotal !== null && rubricTotal > 0 && (
                <p className="text-[13px] text-muted">
                  {fmt(rubricTotal)} pts per {cfg.problemNoun.toLowerCase()} × {problems.length} = <b className="text-ink">{fmt(rubricTotal * problems.length)} pts</b> for the activity
                </p>
              )}
            </div>
          )}
          {rubricMode === 'manual' && (rubricTouched || rubric.length > 0) && rubricErrs.length > 0 && (
            <ul aria-live="polite" className="mt-3 list-disc rounded-ctl border border-warn-border bg-warn-bg py-2 pl-8 pr-3 text-[13px] text-warn-text">
              {rubricErrs.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
        </section>

        {/* ---------------- settings */}
        <section className="card mt-10 px-4 py-6 sm:mt-12 sm:px-8 sm:py-8" aria-labelledby="settings-title">
          <h2 id="settings-title" className="text-[17px] font-semibold">
            Settings
          </h2>
          <div className="mt-6 flex flex-col gap-6 sm:mt-8">
            {subject === 'science' && <Toggle id="units" checked={requireUnits} onChange={setRequireUnits} label="Require units in answers" description="Final answer must include correct units (e.g., m/s) to be marked correct." />}
            {subject === 'grammar' ? (
              <Toggle id="alt" checked={acceptAlt} onChange={setAcceptAlt} label="Accept other valid corrections" description="Allow students to use alternative phrasings that are also grammatically correct." />
            ) : (
              <Toggle id="alt" checked={acceptAlt} onChange={setAcceptAlt} label="Accept alternate valid methods" description="Allow students to get full points using different but correct logic." />
            )}
          </div>
          <fieldset className="mt-8">
            <legend className="text-[15px] font-semibold">Student feedback style</legend>
            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
              {(
                [
                  ['hint_only', 'Hint only (default)', 'Guide them to find their own mistake.'],
                  ['full_solution', 'Full solution', 'Show them exactly where they went wrong.'],
                ] as const
              ).map(([v, l, d]) => (
                <label key={v} className={`flex cursor-pointer items-center gap-4 rounded-card border bg-white px-4 py-4 transition-[border-color,box-shadow] ${style === v ? 'border-brand shadow-[0_0_0_1px_#4F46E5]' : 'border-line hover:border-brand-tint'}`}>
                  <input type="radio" name="style" value={v} checked={style === v} onChange={() => setStyle(v)} className="h-4 w-4 accent-brand" />
                  <span>
                    <span className="block text-[15px] font-semibold">{l}</span>
                    <span className="block text-[13px] text-muted">{d}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
        </section>

        {errors.length > 0 && (
          <div role="alert" className="notice notice-bad mt-6 block">
            <ul className="list-disc pl-5">
              {errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </AppShell>
  )
}

// ---------------------------------------------------------------- optional AI rubric draft
function AiRubricPanel({
  subject,
  title,
  problems,
  onUse,
  onCancel,
  onDraftChange,
}: {
  subject: Subject
  title: string
  problems: ProblemDraft[]
  onUse: (c: Criterion[], points: number) => void
  onCancel: () => void
  onDraftChange: (open: boolean) => void
}) {
  const [outcome, setOutcome] = useState('')
  const [points, setPoints] = useState(10)
  const [draft, setDraft] = useState<Criterion[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const sum = rubricSum(draft ?? [])
  const draftErrs = draft ? rubricProblems(draft, points) : []
  const set = (i: number, patch: Partial<Criterion>) => setDraft((d) => (d ? d.map((c, j) => (j === i ? { ...c, ...patch } : c)) : d))

  async function generate() {
    setLoading(true)
    setError(null)
    try {
      const r = await api.generateRubric({
        subject,
        title,
        problems: problems.map((p) => ({ text: p.text, expected_answer: p.expected_answer, rule: p.rule })),
        learning_outcome: outcome,
        points_per_problem: points,
      })
      setDraft(r.criteria) // points exactly as drafted; never rescaled to fit
      onDraftChange(true)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="animate-fade card mt-5 px-4 py-5 sm:px-6 sm:py-6">
      <p className="text-[14px] text-[#3B4260]">
        TsekMate drafts criteria from the subject, title, and {SUBJECTS[subject].problemsNoun} you entered above. Your current rubric is not changed unless you choose <b>Use this rubric</b>.
      </p>
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-[minmax(0,1fr)_170px]">
        <label className="text-[13px] font-semibold text-muted">
          Expected learning outcome (optional)
          <input className="field mt-1.5 font-normal" value={outcome} onChange={(e) => setOutcome(e.target.value)} placeholder="e.g. Solve linear equations that need the distributive property" />
        </label>
        <label className="text-[13px] font-semibold text-muted">
          Points per {SUBJECTS[subject].problemNoun.toLowerCase()}
          <input type="number" min={1} max={100} step={1} className="field mt-1.5 font-normal" value={points} onChange={(e) => setPoints(Math.max(1, Number(e.target.value) || 10))} />
        </label>
      </div>
      <div className="mt-4 flex flex-col gap-3 sm:flex-row">
        <Button icon={<Sparkles className="h-4 w-4" aria-hidden />} onClick={generate} loading={loading}>
          {draft ? 'Generate again' : 'Generate rubric'}
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          {draft ? 'Discard draft' : 'Back to my own rubric'}
        </Button>
      </div>
      {error && (
        <p role="alert" className="mt-4 rounded-ctl border border-bad-border bg-bad-bg px-3 py-2 text-[14px] text-bad-text">
          {error}
        </p>
      )}
      {draft && (
        <div className="animate-fade mt-6">
          <p className="inline-flex items-center gap-1.5 rounded border border-warn-border bg-warn-bg px-2 py-1 text-[12px] font-semibold text-warn-text">
            <Sparkles className="h-3.5 w-3.5" aria-hidden /> AI-generated draft — review and edit before using
          </p>
          <table className="rtable mt-3 w-full text-left">
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
                    <input aria-label={`Draft criterion ${i + 1} name`} className="field h-9 font-semibold" value={c.name} onChange={(e) => set(i, { name: e.target.value })} />
                  </td>
                  <td className="py-1.5 pr-3">
                    <input aria-label={`Draft criterion ${i + 1} description`} className="field h-9" value={c.description} onChange={(e) => set(i, { description: e.target.value })} />
                  </td>
                  <td className="py-1.5 text-right">
                    <input aria-label={`Draft criterion ${i + 1} points`} type="number" min={0} step="any" className="field h-9 w-16 px-2 text-right" value={c.points} onChange={(e) => set(i, { points: Number(e.target.value) })} />
                  </td>
                  <td className="py-1.5 text-center">
                    <button type="button" className="flex h-9 w-9 items-center justify-center rounded-ctl text-[#8790A6] hover:bg-bad-bg hover:text-bad-strong" aria-label={`Remove draft criterion ${i + 1}`} onClick={() => setDraft((d) => (d ? d.filter((_, j) => j !== i) : d))}>
                      <Trash2 className="h-4 w-4" aria-hidden />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className={`text-[13px] ${draftErrs.length ? 'font-semibold text-bad-text' : 'text-muted'}`}>
              Total {fmt(sum)} of {fmt(points)} points{draftErrs.length ? ` — ${draftErrs[0]}` : ''}
            </p>
            <Button disabled={draftErrs.length > 0} onClick={() => onUse(draft.map((c) => ({ ...c, name: c.name.trim(), points: Number(c.points) })), points)}>
              Use this rubric
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
