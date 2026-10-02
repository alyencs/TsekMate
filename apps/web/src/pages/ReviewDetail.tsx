import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Check, CircleAlert, FlagTriangleRight, ImageOff, MessageSquareText, RefreshCw, RotateCcw, Sparkles, UserRound, UserRoundX, ZoomIn, ZoomOut } from 'lucide-react'
import { api } from '../lib/api'
import type { Criterion, CriterionScore, ProblemResult, SubmissionDetail, Unit, UnitEdit, Verdict } from '../lib/types'
import { AI_LABEL, SUBJECTS, errorTypeLabel } from '../lib/subjects'
import { fmtScore, timeAgo } from '../lib/format'
import { rememberActivity } from '../lib/session'
import { useThreshold } from '../lib/appSettings'
import { useUnsavedChanges } from '../lib/useUnsavedChanges'
import { AppShell } from '../components/layout/AppShell'
import { Badge, SubjectChip } from '../components/ui/Chip'
import { ConfidenceBar } from '../components/ui/ConfidenceBar'
import { Button } from '../components/ui/Button'
import { TopBarActions } from '../components/layout/AppShell'
import { StudentLabel } from '../components/ui/StudentLabel'
import { Modal } from '../components/ui/Modal'
import { ErrorState, Loading, Notice } from '../components/ui/States'

type U = Unit & { edited?: boolean }

const ukey = (pid: string, u: { index: number }) => `${pid}:${u.index}`
const ckey = (pid: string, name: string) => `${pid}::${name}`
const r2 = (n: number) => Math.round(n * 100) / 100

type Row = CriterionScore & { value: number; override: number | null | undefined; invalid: boolean }

/**
 * The score breakdown is the activity rubric, row for row: every criterion with its exact points.
 * `computed` follows the AI's marks (with the teacher's unsaved step edits); the teacher's typed score replaces it.
 * The problem score is always the sum of the rows.
 */
function breakdown(pid: string, units: U[], rubric: Criterion[], server: CriterionScore[], overrides: Record<string, number | null>): Row[] {
  return rubric.map((c) => {
    const s = server.find((x) => x.name === c.name)
    const got = units.filter((u) => u.criterion.trim().toLowerCase() === c.name.trim().toLowerCase()).reduce((t, u) => t + (Number(u.points_awarded) || 0), 0)
    const computed = r2(Math.min(got, c.points))
    const override = overrides[ckey(pid, c.name)]
    const invalid = override !== undefined && override !== null && (Number.isNaN(override) || override < 0 || override > c.points)
    const value = override !== undefined && override !== null && !invalid ? override : computed
    return { name: c.name, description: c.description, points: c.points, computed, awarded: value, assessed: s?.assessed ?? false, edited: override !== undefined && override !== null, value, override, invalid }
  })
}

/** Same rule as the server's routing, with the confidence threshold from Settings. */
function needsCheck(p: ProblemResult, threshold: number) {
  return (
    p.flags.length > 0 ||
    p.overall_confidence < threshold ||
    p.units.some((u) => u.verdict === 'unclear' || u.confidence < threshold) ||
    p.criteria_scores.some((c) => !c.assessed)
  )
}

export default function ReviewDetail() {
  const { id = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState<SubmissionDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [unitEdits, setUnitEdits] = useState<Record<string, UnitEdit>>({})
  const [scores, setScores] = useState<Record<string, number | null>>({}) // `${problem_id}::${criterion}` -> points
  const [feedback, setFeedback] = useState<Record<string, string>>({})
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState<'draft' | 'approve' | null>(null)
  const [notice, setNotice] = useState<{ tone: 'ok' | 'bad'; text: string } | null>(null)
  const [approved, setApproved] = useState<{ total: number; max: number } | null>(null)
  const threshold = useThreshold()
  const confirmLeave = useUnsavedChanges(dirty)

  useEffect(() => {
    let alive = true
    setDetail(null)
    setError(null)
    setApproved(null)
    api
      .submission(id)
      .then((d) => {
        if (!alive) return
        setDetail(d)
        setUnitEdits(d.review.unit_edits)
        setScores(d.review.criterion_scores)
        setFeedback(d.review.feedback)
        setDirty(false)
        rememberActivity(d.activity.id)
      })
      .catch((e: Error) => alive && setError(e.message))
    return () => {
      alive = false
    }
  }, [id])

  const problems = detail?.ai_result?.problems ?? []
  const order = Number(params.get('p')) || detail?.activity.problems.find((p) => p.id === detail?.focus_problem_id)?.order || 1
  const prob = detail?.activity.problems.find((p) => p.order === order) ?? detail?.activity.problems[0]
  const result = problems.find((p) => p.problem_id === prob?.id)
  const subject = detail?.activity.subject ?? 'math'
  const cfg = SUBJECTS[subject]
  const rubric = detail?.activity.rubric ?? []

  // units with the teacher's local (unsaved) edits applied
  const units: U[] = useMemo(() => {
    if (!result) return []
    return result.units.map((u) => {
      const e = unitEdits[ukey(result.problem_id, u)]
      return e ? { ...u, ...e, edited: true } : u
    })
  }, [result, unitEdits])
  const rows = useMemo(() => (result ? breakdown(result.problem_id, units, rubric, result.criteria_scores, scores) : []), [result, units, rubric, scores])
  const finalScore = r2(rows.reduce((s, c) => s + c.value, 0))
  const maxScore = r2(rows.reduce((s, c) => s + c.points, 0))
  const problemEdited = rows.some((c) => c.edited) || units.some((u) => u.edited)
  const invalidRows = rows.filter((c) => c.invalid)

  function setCriterion(name: string, v: number | null) {
    if (!result) return
    setScores((s) => ({ ...s, [ckey(result.problem_id, name)]: v }))
    setDirty(true)
  }

  function setProblem(n: number) {
    const next = new URLSearchParams(params)
    next.set('p', String(n))
    setParams(next, { replace: true })
  }

  function editUnit(u: U, patch: UnitEdit) {
    if (!result) return
    const k = ukey(result.problem_id, u)
    setUnitEdits((prev) => ({ ...prev, [k]: { ...prev[k], ...patch } }))
    setDirty(true)
  }

  async function save(): Promise<SubmissionDetail | null> {
    if (!detail) return null
    const bad = Object.entries(scores).find(([k, v]) => {
      if (v === null || v === undefined) return false
      const c = rubric.find((x) => x.name === k.split('::').slice(1).join('::'))
      return !c || Number.isNaN(v) || v < 0 || v > c.points
    })
    if (bad) throw new Error(`Check the score for ${bad[0].split('::').slice(1).join('::')}: it must be from 0 to the criterion's points.`)
    const d = await api.saveReview(detail.id, { unit_edits: unitEdits, criterion_scores: scores, feedback })
    setDetail(d)
    setUnitEdits(d.review.unit_edits)
    setScores(d.review.criterion_scores)
    setFeedback(d.review.feedback)
    setDirty(false)
    return d
  }

  async function saveDraft() {
    setSaving('draft')
    setNotice(null)
    try {
      const wasApproved = detail?.status === 'approved'
      const d = await save()
      setNotice({
        tone: 'ok',
        text:
          wasApproved && d && d.status !== 'approved'
            ? 'Saved. Because you changed an approved grade, this paper is back in the review queue: approve it again to update the gradebook.'
            : 'Draft saved. Nothing is final until you approve.',
      })
    } catch (e) {
      setNotice({ tone: 'bad', text: (e as Error).message })
    } finally {
      setSaving(null)
    }
  }

  async function approve() {
    if (!detail) return
    const handGraded = Object.values(scores).some((v) => v !== null && v !== undefined)
    if (detail.status === 'failed' && !handGraded && !window.confirm('The AI could not grade this paper and you have not entered any scores. Approve it with 0 points?')) return
    setSaving('approve')
    setNotice(null)
    try {
      if (dirty) await save()
      const r = await api.approve(detail.id)
      setDetail(r.submission)
      setApproved({ total: r.final_score, max: r.max_score })
    } catch (e) {
      setNotice({ tone: 'bad', text: (e as Error).message })
    } finally {
      setSaving(null)
    }
  }

  const back = () => confirmLeave() && navigate(`/queue?activity=${detail?.activity.id ?? ''}`)
  const [regrading, setRegrading] = useState(false)

  async function gradeAgain() {
    if (!detail || !confirmLeave()) return
    setRegrading(true)
    setNotice(null)
    try {
      await api.regrade(detail.id)
      navigate(`/activities/${detail.activity.id}/grading?return=${detail.id}`)
    } catch (e) {
      setNotice({ tone: 'bad', text: (e as Error).message })
      setRegrading(false)
    }
  }

  async function assign(studentId: string) {
    if (!detail) return
    setNotice(null)
    try {
      const d = await api.assignStudent(detail.id, studentId)
      setDetail(d)
      setNotice({ tone: 'ok', text: `Paper assigned to ${d.student_name} (${d.student_id}).` })
    } catch (e) {
      setNotice({ tone: 'bad', text: (e as Error).message })
    }
  }

  if (error) return <AppShell active="queue"><ErrorState message={error} /></AppShell>
  if (!detail || !prob) return <AppShell active="queue"><Loading label="Loading paper…" /></AppShell>

  const isApproved = detail.status === 'approved'
  const failed = detail.status === 'failed' || detail.ai_result?.flags.includes('grading_failed')
  const label = subject === 'grammar' ? `Item ${prob.order}` : `Problem ${prob.order}`
  const shortTitle = detail.activity.title.replace(/^Solving /, '')
  const problemNav = (
    <nav aria-label={`${cfg.problemNoun}s`} className="scroll-x flex gap-1.5 p-0.5">
      {detail.activity.problems.map((p) => {
        const r = problems.find((x) => x.problem_id === p.id)
        const sel = p.order === prob.order
        const clean = r && !needsCheck(r, threshold) && r.suggested_score === r.max_score
        const flag = r && needsCheck(r, threshold)
        return (
          <button
            key={p.id}
            type="button"
            onClick={() => setProblem(p.order)}
            aria-current={sel ? 'true' : undefined}
            aria-label={`${cfg.problemNoun} ${p.order}${flag ? ', needs your check' : clean ? ', all correct' : ''}`}
            className={`relative flex h-9 w-9 shrink-0 items-center justify-center rounded-ctl border text-[13px] font-semibold transition-colors ${
              sel ? 'border-navy bg-navy text-white ring-2 ring-accent ring-offset-1' : clean ? 'border-ok-bar bg-ok-bar text-white' : 'border-line bg-white text-ink hover:border-brand-tint hover:bg-brand-light'
            }`}
          >
            {p.order}
            {flag && !sel && <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-warn-bar ring-2 ring-white" aria-hidden />}
          </button>
        )
      })}
    </nav>
  )
  const approvedLinks = isApproved && (
    <>
      <Link to={`/submissions/${detail.id}/parent-message`} className="inline-flex h-9 items-center gap-1.5 whitespace-nowrap rounded-ctl border border-line bg-white px-3 text-[12px] font-semibold transition-colors hover:bg-soft">
        <MessageSquareText className="h-3.5 w-3.5" aria-hidden /> Parent update
      </Link>
      <Link to={`/feedback/${detail.id}?p=${prob.order}`} className="inline-flex h-9 items-center gap-1.5 whitespace-nowrap rounded-ctl border border-line bg-white px-3 text-[12px] font-semibold transition-colors hover:bg-soft">
        <UserRound className="h-3.5 w-3.5" aria-hidden /> Student view
      </Link>
    </>
  )


  return (
    <AppShell
      active="queue"
      topbar={
        <>
          <button type="button" onClick={back} className="flex h-10 w-10 shrink-0 items-center justify-center rounded-ctl border border-line transition-colors hover:bg-soft" aria-label="Back to review queue">
            <ArrowLeft className="h-5 w-5" aria-hidden />
          </button>
          <h1 className="min-w-0 truncate max-sm:[&>span>span+span]:hidden">
            <StudentLabel id={detail.student_id} name={detail.student_name} size="lg" inline />
          </h1>
          <span className="hidden h-5 w-px shrink-0 bg-line xl:block" aria-hidden />
          <div className="hidden min-w-0 xl:block">{problemNav}</div>
          <div className="flex-1" />
          <div className="hidden items-center gap-2 2xl:flex">{approvedLinks}</div>
          <TopBarActions />
        </>
      }
    >
      <div className="mb-4 flex flex-col gap-3 sm:mb-5 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 items-center gap-3 xl:hidden">
          <span className="label-caps shrink-0">{cfg.problemNoun}s</span>
          <div className="min-w-0">{problemNav}</div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SubjectChip subject={subject} size="sm" />
          <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white px-2.5 py-1 text-[11px] font-medium text-muted">
            <Sparkles className="h-3 w-3 text-accent" aria-hidden /> {AI_LABEL}
          </span>
          <span className="flex flex-wrap gap-2 2xl:hidden">{approvedLinks}</span>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)] lg:gap-6 xl:grid-cols-[minmax(0,480px)_minmax(0,1fr)] xl:gap-8">
        <div className="mx-auto w-full max-w-[520px] self-start lg:sticky lg:top-[88px] lg:max-w-none">
          <ImageViewer url={detail.image_url} deleted={detail.image_deleted} units={units} studentId={detail.student_name ?? detail.student_id ?? 'an unidentified student'} />
          <p className="mt-3 text-center text-[11px] uppercase tracking-[0.12em] text-muted lg:mt-5">
            Student submission: {shortTitle}, {label}
          </p>
        </div>

        <div className="flex min-w-0 flex-col gap-4">
          <IdentityBar detail={detail} onAssign={assign} />
          <section className="card px-4 py-5 sm:px-6 sm:py-6">
            {subject === 'grammar' ? (
              <>
                <p className="label-caps">Item {prob.order}: Correct the sentence</p>
                <h2 className="mt-1.5 text-[17px] font-bold leading-snug sm:text-[19px]">&quot;{prob.text}&quot;</h2>
                <p className="mt-1.5 text-[14px] font-medium text-ok-text sm:text-[15px]">Expected: &quot;{prob.expected_answer}&quot;</p>
                {result?.student_answer && (
                  <div className="mt-4 rounded-card border border-line bg-soft px-4 py-4">
                    <p className="label-caps">Student answer (transcribed)</p>
                    <p className="mt-2 break-words font-mono text-[14px] italic leading-relaxed sm:text-[15px]">&quot;{result.student_answer}&quot;</p>
                  </div>
                )}
              </>
            ) : (
              <>
                <h2 className="text-[17px] font-bold leading-snug sm:text-[20px]">
                  {label}: {prob.text}
                </h2>
                <p className="mt-1.5 text-[14px] font-medium text-ok-text sm:text-[15px]">Expected answer: {prob.expected_answer}</p>
              </>
            )}
          </section>

          {failed ? (
            <div role="alert" className="card flex gap-3 border-bad-border bg-bad-bg px-4 py-5 text-bad-text sm:px-6">
              <CircleAlert className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
              <div>
                <p className="font-semibold">TsekMate could not grade this paper automatically.</p>
                {detail.ai_result?.failure_reason && <p className="mt-1 text-[14px]">Reason: {detail.ai_result.failure_reason}</p>}
                <p className="mt-1 text-[14px]">Try grading it again, or grade it by hand: enter the points for each rubric criterion below and approve.</p>
                <Button className="mt-4" icon={<RefreshCw className="h-4 w-4" aria-hidden />} onClick={gradeAgain} loading={regrading}>
                  Grade again
                </Button>
              </div>
            </div>
          ) : (
            units.map((u, i) => <UnitCard key={u.index} unit={u} position={i} units={units} subject={subject} onEdit={(patch) => editUnit(u, patch)} disabled={false} />)
          )}

          <RubricBreakdown rows={rows} total={finalScore} max={maxScore} label={label} onChange={setCriterion} />

          <section className="card mt-2 overflow-hidden shadow-pop" aria-label="Score and approval">
            <div className="flex items-center gap-2 border-b border-line bg-soft px-5 py-3 text-[13px] font-medium text-navy sm:px-8">
              <UserRound className="h-4 w-4 text-accent" aria-hidden /> You decide the final grade. The AI only suggests.
            </div>
            <div className="px-5 py-6 sm:px-8 sm:py-8">
            <div className="grid grid-cols-2 gap-4 sm:gap-6">
              <div className="rounded-ctl border border-line bg-soft/60 p-3 sm:border-0 sm:bg-transparent sm:p-0">
                <p className="label-caps tracking-[0.12em]">AI suggested</p>
                <p className="mt-2 text-[28px] font-bold leading-none text-[#3B4260] sm:text-[38px]">
                  {fmtScore(result?.ai_suggested_score ?? 0)} <span className="text-[15px] font-medium text-muted sm:text-[20px]">/ {fmtScore(maxScore)}</span>
                </p>
              </div>
              <div className="rounded-ctl border border-accent-tint bg-accent-light p-3 sm:border-0 sm:bg-transparent sm:p-0">
                <p className="label-caps tracking-[0.12em] text-muted">Your final score</p>
                <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[28px] font-bold leading-none text-navy sm:text-[38px]" aria-live="polite">
                  <span>
                    {fmtScore(finalScore)} <span className="text-[15px] font-medium text-muted sm:text-[20px]">/ {fmtScore(maxScore)}</span>
                  </span>
                  {problemEdited && <span className="rounded bg-accent-strong px-2 py-1 text-[11px] font-semibold text-white">Edited by you</span>}
                </p>
                <p className="mt-2 text-[12px] text-muted">The sum of the rubric breakdown above.</p>
              </div>
            </div>

            <label htmlFor="feedback" className="label-caps mt-6 block tracking-[0.12em] sm:mt-8">
              Feedback to student
            </label>
            <div className="relative mt-3">
              <textarea
                id="feedback"
                rows={3}
                value={feedback[prob.id] ?? ''}
                onChange={(e) => {
                  setFeedback((f) => ({ ...f, [prob.id]: e.target.value }))
                  setDirty(true)
                }}
                className="field-soft min-h-[110px] resize-y py-3 pb-11"
              />
              <span className="pointer-events-none absolute bottom-3 right-3 rounded border border-line bg-white px-2 py-1 text-[11px] font-semibold text-muted">
                {detail.activity.settings.feedback_style === 'hint_only' ? 'Hint only mode' : 'Full solution mode'}
              </span>
            </div>

            <hr className="my-6 border-line" />
            {notice && (
              <Notice tone={notice.tone} className="mb-4">
                {notice.text}
              </Notice>
            )}
            <div className="flex flex-wrap items-center gap-3 sm:flex-nowrap sm:gap-4">
              <Button
                size="lg"
                className="w-full sm:w-auto sm:flex-1"
                onClick={approve}
                loading={saving === 'approve'}
                disabled={saving !== null || !detail.student_id || invalidRows.length > 0}
                title={!detail.student_id ? 'Choose the student first' : invalidRows.length ? 'Fix the scores marked in the rubric breakdown' : undefined}
              >
                {isApproved ? 'Save and re-approve' : 'Approve and save'}
              </Button>
              <Button size="lg" variant="secondary" className="flex-1 sm:w-36 sm:flex-none" onClick={saveDraft} loading={saving === 'draft'} disabled={saving !== null || !dirty}>
                Save draft
              </Button>
              <button
                type="button"
                className="flex h-12 w-12 shrink-0 items-center justify-center rounded-ctl border border-line text-muted transition-colors hover:bg-soft hover:text-ink"
                title="Leave flagged and go to the next paper"
                aria-label="Leave this paper flagged and go to the next paper"
                onClick={() => (detail.next_submission ? confirmLeave() && navigate(`/submissions/${detail.next_submission.id}`) : back())}
              >
                <FlagTriangleRight className="h-5 w-5" />
              </button>
            </div>
            <p className="mt-3 text-[12px] text-muted">
              {detail.student_id ? `Approving saves all ${detail.activity.problems.length} ${cfg.problemsNoun} of this paper to the gradebook.` : 'Choose the student above before approving.'}
            </p>
            <p className="mt-6 flex items-center gap-1.5 text-[12px] text-muted">
              <Sparkles className="h-3.5 w-3.5 shrink-0 text-brand" aria-hidden />
              {isApproved && detail.review.approved_at
                ? `Approved by you ${timeAgo(detail.review.approved_at)}. You can still change scores and re-approve.`
                : 'AI-assisted draft. Review the suggested score before approving.'}
            </p>
            </div>
          </section>
        </div>
      </div>

      <Modal open={!!approved} onClose={back} labelledBy="approved-title" className="max-w-[500px] px-6 pb-8 pt-10 text-center sm:px-12 sm:pb-10 sm:pt-12">
        <span className="animate-check mx-auto flex h-24 w-24 items-center justify-center rounded-full bg-ok-bg" aria-hidden>
          <span className="flex h-20 w-20 items-center justify-center rounded-full bg-[#16A34A]">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white">
              <Check className="h-4 w-4 text-[#15803D]" strokeWidth={3} />
            </span>
          </span>
        </span>
        <h2 id="approved-title" className="mt-6 text-[24px] font-bold sm:text-[30px]">
          Approved and saved
        </h2>
        <div className="mt-5 rounded-card border border-line bg-soft px-4 py-5 sm:px-6 sm:py-6">
          <p className="text-[16px] leading-relaxed sm:text-[18px]">
            <b>{detail.student_name ?? detail.student_id}</b> scored{' '}
            <b className="text-[#15803D]">
              {fmtScore(approved?.total)} / {fmtScore(approved?.max)}
            </b>{' '}
            on <b className="italic">{detail.activity.title}</b>.
          </p>
          <p className="mx-auto mt-4 w-fit rounded-full border border-line bg-white px-3 py-1 text-[12px] text-muted">Approved by you. The grade is now in the gradebook.</p>
        </div>
        {detail.next_submission && (
          <Button size="lg" className="mt-8 w-full whitespace-normal" iconRight={<ArrowRight className="h-4 w-4" aria-hidden />} onClick={() => navigate(`/submissions/${detail.next_submission!.id}`)}>
            Next paper ({detail.next_submission.student_name ?? 'not identified'})
          </Button>
        )}
        <Button size="lg" variant="secondary" className={`${detail.next_submission ? 'mt-3' : 'mt-8'} w-full`} onClick={back}>
          Back to review queue
        </Button>
      </Modal>
    </AppShell>
  )
}

// ---------------------------------------------------------------- unit card
function unitLabel(subject: string, u: U, position: number, units: U[]) {
  if (subject !== 'grammar') return `Step ${position + 1}`
  const c = u.criterion.toLowerCase()
  if (c === 'finds the errors') return `Correction ${units.slice(0, position + 1).filter((x) => x.criterion.toLowerCase() === 'finds the errors').length}`
  if (c === 'correct revision') return 'Revision'
  if (c === 'rule explanation') return 'Rule explanation'
  if (c === 'spelling and punctuation') return 'Spelling check'
  return u.criterion
}

function UnitCard({ unit: u, position, units, subject, onEdit }: { unit: U; position: number; units: U[]; subject: 'math' | 'science' | 'grammar'; onEdit: (p: UnitEdit) => void; disabled: boolean }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<UnitEdit>({})
  const err = u.verdict === 'error'
  const unclear = u.verdict === 'unclear'
  const isCorrection = subject === 'grammar' && ['finds the errors'].includes(u.criterion.toLowerCase())
  const name = unitLabel(subject, u, position, units)
  const frame = err ? 'border-bad-border' : unclear ? 'border-line border-l-4 border-l-[#CA8A04]' : 'border-line'
  const head = err ? 'bg-bad-bg/60' : unclear ? 'bg-warn-bg/50' : 'bg-soft/60'
  const id = `unit-${u.index}`

  return (
    <article id={id} className={`card overflow-hidden ${frame}`} aria-label={`${name}: ${u.verdict}`}>
      <header className={`flex flex-wrap items-center gap-2 border-b border-line px-4 py-3 sm:py-4 ${head}`}>
        <h3 className="text-[13px] font-semibold uppercase tracking-wide text-muted">{name}</h3>
        {u.verdict === 'correct' && (
          <Badge tone="ok" icon={<Check className="h-3 w-3" aria-hidden />}>
            Correct
          </Badge>
        )}
        {err && (
          <Badge tone="bad" icon={<CircleAlert className="h-3 w-3" aria-hidden />}>
            ERROR
          </Badge>
        )}
        {err && u.error_type && (
          <Badge tone="bad" shape="tag">
            {errorTypeLabel(subject, u.error_type)}
          </Badge>
        )}
        {unclear && (
          <>
            <Badge tone="warn" icon={<CircleAlert className="h-3 w-3" aria-hidden />}>
              Unclear
            </Badge>
            <span className="rounded border border-[#D9A21B] bg-white px-2 py-0.5 text-[11px] font-semibold text-warn-text">Needs your check</span>
          </>
        )}
        {u.edited && <span className="rounded bg-brand-light px-1.5 py-0.5 text-[10px] font-semibold text-brand-dark">Edited</span>}
        <span className="ml-auto flex items-center gap-3 sm:gap-4">
          <ConfidenceBar value={u.confidence} width="w-16" />
          <button
            type="button"
            className="rounded px-1.5 py-1 text-[13px] font-semibold text-brand-dark hover:bg-brand-light"
            aria-expanded={editing}
            onClick={() => {
              setDraft({ transcribed_text: u.transcribed_text, verdict: u.verdict, error_type: u.error_type, comment: u.comment })
              setEditing((e) => !e)
            }}
          >
            {editing ? 'Close' : 'Edit'}
          </button>
        </span>
      </header>

      {editing ? (
        <div className="grid grid-cols-1 gap-4 px-4 py-5 sm:grid-cols-2 sm:px-6">
          <label className="text-[12px] font-semibold text-muted sm:col-span-2">
            Transcription
            <textarea className="field-soft mt-1 h-auto py-2 font-mono text-[14px]" rows={2} value={draft.transcribed_text ?? ''} onChange={(e) => setDraft({ ...draft, transcribed_text: e.target.value })} />
          </label>
          <label className="text-[12px] font-semibold text-muted">
            Verdict
            <select className="field mt-1" value={draft.verdict} onChange={(e) => setDraft({ ...draft, verdict: e.target.value as Verdict, error_type: e.target.value === 'error' ? draft.error_type : null })}>
              <option value="correct">Correct</option>
              <option value="error">Error</option>
              <option value="unclear">Unclear</option>
            </select>
          </label>
          <label className="text-[12px] font-semibold text-muted">
            Error type
            <select className="field mt-1" value={draft.error_type ?? ''} disabled={draft.verdict !== 'error'} onChange={(e) => setDraft({ ...draft, error_type: e.target.value || null })}>
              <option value="">None (follows from an earlier error)</option>
              {SUBJECTS[subject].errorTypes.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-[12px] font-semibold text-muted sm:col-span-2">
            Comment (describe the work, not the student)
            <input className="field mt-1" value={draft.comment ?? ''} onChange={(e) => setDraft({ ...draft, comment: e.target.value })} />
          </label>
          <div className="flex justify-end gap-2 sm:col-span-2">
            <Button variant="secondary" size="sm" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              variant="dark"
              onClick={() => {
                const patch: UnitEdit = {}
                ;(Object.keys(draft) as (keyof UnitEdit)[]).forEach((k) => {
                  if (draft[k] !== (u as unknown as Record<string, unknown>)[k]) (patch as Record<string, unknown>)[k] = draft[k]
                })
                if (Object.keys(patch).length) onEdit(patch)
                setEditing(false)
              }}
            >
              Apply edit
            </Button>
          </div>
        </div>
      ) : (
        <div className="px-4 py-5 sm:px-6 sm:py-6">
          {isCorrection ? (
            <p className="text-[16px] font-semibold">{u.transcribed_text}</p>
          ) : (
            <div className="break-words rounded-ctl border border-line bg-soft px-3 py-3 font-mono text-[14px] sm:text-[15px]">{u.transcribed_text}</div>
          )}
          {u.alt_reading && <p className="mt-2 text-[12px] text-warn-text">Other possible reading: {u.alt_reading}</p>}
          <div className="mt-5 flex items-end justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">Criterion: {u.criterion}</p>
              {u.comment && <p className={`mt-1 text-[13px] ${err ? 'text-bad-strong' : unclear ? 'text-[#A16207]' : 'italic text-muted'}`}>{u.verdict === 'correct' ? `"${u.comment}"` : u.comment}</p>}
            </div>
          </div>
        </div>
      )}
    </article>
  )
}

// ---------------------------------------------------------------- image viewer with bbox overlays
function ImageViewer({ url, deleted, units, studentId }: { url: string | null; deleted: boolean; units: U[]; studentId: string }) {
  const [zoom, setZoom] = useState(1.5)
  const [rot, setRot] = useState(0)
  const box = useRef<HTMLDivElement>(null)
  const boxes = units.filter((u) => u.bbox)

  useEffect(() => {
    // Bring the current problem into view.
    const el = box.current
    if (!el || !boxes.length) return
    const top = Math.min(...boxes.map((u) => u.bbox![1]))
    const left = Math.min(...boxes.map((u) => u.bbox![0]))
    const inner = el.firstElementChild as HTMLElement | null
    const r = inner?.getBoundingClientRect()
    el.scrollTo({ top: Math.max(0, top * (r?.height ?? 0) - 80), left: Math.max(0, left * (r?.width ?? 0) - 60), behavior: 'smooth' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [units.map((u) => u.index).join(','), zoom, boxes.length])

  if (!url)
    return (
      <div className="flex aspect-[3/4] flex-col items-center justify-center gap-3 rounded-2xl border border-line bg-white text-center text-muted shadow-pop">
        <ImageOff className="h-8 w-8" aria-hidden />
        <p className="max-w-[260px] text-[14px]">{deleted ? 'The photo was deleted after approval (privacy setting). Scores and feedback are kept.' : 'No photo for this paper.'}</p>
      </div>
    )
  const color = (v: string) => (v === 'error' ? '#DC2626' : v === 'unclear' ? '#CA8A04' : '#16A34A')
  return (
    <div className="relative overflow-hidden rounded-2xl border border-line bg-[#E9EDF5] shadow-pop">
      <div ref={box} className="aspect-[3/4] max-h-[72vh] overflow-auto lg:max-h-none">
        <div className="relative origin-top-left transition-transform" style={{ width: `${zoom * 100}%`, transform: rot ? `rotate(${rot}deg)` : undefined, transformOrigin: 'center' }}>
          <img src={url} alt={`Photo of ${studentId}'s handwritten work`} className="block w-full select-none" draggable={false} />
          {boxes.map((u) => (
            <a
              key={u.index}
              href={`#unit-${u.index}`}
              className="absolute rounded-sm border-[3px]"
              style={{ left: `${u.bbox![0] * 100}%`, top: `${u.bbox![1] * 100}%`, width: `${u.bbox![2] * 100}%`, height: `${u.bbox![3] * 100}%`, borderColor: color(u.verdict) }}
              aria-label={`Go to ${u.verdict} line: ${u.transcribed_text}`}
            />
          ))}
        </div>
      </div>
      <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-full border border-line bg-white/95 px-3 py-1.5 shadow-pop sm:bottom-6 sm:px-4 sm:py-2">
        <button type="button" className="flex h-10 w-10 items-center justify-center rounded-full transition-colors hover:bg-soft" aria-label="Zoom in" onClick={() => setZoom((z) => Math.min(3, z + 0.5))}>
          <ZoomIn className="h-4 w-4" aria-hidden />
        </button>
        <button type="button" className="flex h-10 w-10 items-center justify-center rounded-full transition-colors hover:bg-soft" aria-label="Zoom out" onClick={() => setZoom((z) => Math.max(1, z - 0.5))}>
          <ZoomOut className="h-4 w-4" aria-hidden />
        </button>
        <span className="mx-2 h-5 w-px bg-line" aria-hidden />
        <button type="button" className="flex h-10 w-10 items-center justify-center rounded-full transition-colors hover:bg-soft" aria-label="Rotate" onClick={() => setRot((r) => (r + 90) % 360)}>
          <RotateCcw className="h-4 w-4" aria-hidden />
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- rubric breakdown
function RubricBreakdown({ rows, total, max, label, onChange }: { rows: Row[]; total: number; max: number; label: string; onChange: (name: string, v: number | null) => void }) {
  return (
    <section className="card overflow-hidden" aria-labelledby="breakdown-title">
      <div className="flex flex-col gap-1 px-4 pt-5 sm:flex-row sm:items-baseline sm:justify-between sm:px-6">
        <h3 id="breakdown-title" className="label-caps">
          Rubric breakdown · {label}
        </h3>
        <p className="text-[12px] text-muted">Type a score to change it. Clear it to use the AI&apos;s points.</p>
      </div>
      <table className="mt-3 w-full text-left">
        <thead>
          <tr className="border-y border-line bg-soft text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
            <th scope="col" className="px-4 py-2.5 sm:px-6">Criterion</th>
            <th scope="col" className="hidden w-[90px] px-2 py-2.5 text-right sm:table-cell">AI points</th>
            <th scope="col" className="w-[120px] px-4 py-2.5 text-right sm:w-[150px] sm:px-6">Your score</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => {
            const id = `crit-${c.name.replace(/\W+/g, '-')}`
            return (
              <tr key={c.name} className={`border-b border-line align-top ${c.assessed || c.edited ? '' : 'bg-warn-bg/40'}`}>
                <td className="px-4 py-3 sm:px-6">
                  <label htmlFor={id} className="text-[14px] font-semibold sm:text-[15px]">
                    {c.name}
                  </label>
                  {c.description && <p className="text-[13px] text-muted">{c.description}</p>}
                  <p className="mt-0.5 text-[12px] text-muted sm:hidden">AI points: {c.assessed ? fmtScore(c.computed) : '—'}</p>
                  <p className="mt-1 flex flex-wrap gap-1.5">
                    {!c.assessed && !c.edited && (
                      <span className="rounded border border-[#D9A21B] bg-white px-1.5 py-0.5 text-[11px] font-semibold text-warn-text">Not scored by the AI · please score it</span>
                    )}
                    {c.edited && <span className="rounded bg-brand-light px-1.5 py-0.5 text-[11px] font-semibold text-brand-dark">Edited</span>}
                  </p>
                  {c.invalid && (
                    <p role="alert" className="mt-1 text-[12px] font-semibold text-bad-strong">
                      Enter a score from 0 to {fmtScore(c.points)}.
                    </p>
                  )}
                </td>
                <td className="hidden px-2 py-3 text-right text-[14px] text-muted sm:table-cell">{c.assessed ? fmtScore(c.computed) : '—'}</td>
                <td className="px-4 py-3 text-right sm:px-6">
                  <span className="inline-flex items-center gap-1.5 text-[14px] text-muted">
                    <ScoreInput
                      id={id}
                      value={c.value}
                      aiValue={c.computed}
                      max={c.points}
                      invalid={c.invalid}
                      describedBy={`${id}-max`}
                      onCommit={(v) => onChange(c.name, v)}
                    />
                    <span id={`${id}-max`}>/ {fmtScore(c.points)}</span>
                  </span>
                </td>
              </tr>
            )
          })}
          <tr className="bg-soft">
            <td className="hidden sm:table-cell" />
            <td className="px-4 py-3 text-right text-[12px] font-semibold uppercase tracking-wider text-muted sm:px-6">
              Total
            </td>
            <td className="whitespace-nowrap px-4 py-3 text-right text-[17px] font-bold text-navy sm:px-6">
              {fmtScore(total)} / {fmtScore(max)}
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  )
}

// ---------------------------------------------------------------- criterion score field
const SCORE_TEXT = /^\d*\.?\d{0,2}$/ // digits, one decimal point, up to 2 decimals; no sign
const STEP = 0.5

/**
 * A typed score for one criterion (0 to the criterion's points).
 *
 * A text field with a decimal keypad, not type="number": the teacher's draft text is kept as typed, so the field can be
 * empty or end in "." while they type. Every complete number is applied at once (the total updates live); a value
 * above the maximum becomes the maximum and a minus sign is not accepted. Leaving the field empty restores the AI's
 * points. Arrow up/down step by 0.5 within the limits.
 */
function ScoreInput({ id, value, aiValue, max, invalid, describedBy, onCommit }: { id: string; value: number; aiValue: number; max: number; invalid: boolean; describedBy: string; onCommit: (v: number | null) => void }) {
  const [text, setText] = useState(fmtScore(value))
  const [editing, setEditing] = useState(false)
  const [hint, setHint] = useState<string | null>(null)
  useEffect(() => {
    if (!editing) setText(fmtScore(value))
  }, [value, editing])

  function apply(n: number) {
    const v = r2(Math.min(Math.max(n, 0), max))
    setHint(n > max ? `The most for this criterion is ${fmtScore(max)}.` : null)
    onCommit(v)
    return v
  }

  return (
    <span className="relative inline-flex flex-col items-end">
      <input
        id={id}
        type="text"
        inputMode="decimal"
        autoComplete="off"
        value={text}
        onFocus={(e) => {
          setEditing(true)
          e.currentTarget.select()
        }}
        onChange={(e) => {
          const raw = e.target.value.replace(',', '.').trim()
          if (raw.includes('-')) return setHint("Scores can't be negative.")
          if (!SCORE_TEXT.test(raw)) return setHint('Type a number, for example 2 or 1.5.')
          setHint(null)
          if (raw === '' || raw === '.') return setText(raw) // in progress: nothing to apply yet
          const n = Number(raw)
          if (n > max) return setText(fmtScore(apply(n)))
          setText(raw)
          apply(n)
        }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
            e.preventDefault()
            const base = text === '' || text === '.' ? value : Number(text)
            setText(fmtScore(apply(base + (e.key === 'ArrowUp' ? STEP : -STEP))))
            setHint(null)
          } else if (e.key === 'Enter') {
            e.currentTarget.blur()
          }
        }}
        onBlur={() => {
          setEditing(false)
          setHint(null)
          if (text === '' || text === '.') {
            onCommit(null) // empty: back to the AI's points
            setText(fmtScore(aiValue))
          }
        }}
        aria-invalid={invalid || undefined}
        aria-describedby={hint ? `${describedBy} ${id}-hint` : describedBy}
        className={`h-10 w-14 rounded-ctl border bg-white text-center text-[15px] font-semibold text-ink focus:outline-none focus:ring-2 sm:w-16 ${
          invalid ? 'border-bad-strong focus:ring-bad-strong/20' : 'border-line focus:border-brand focus:ring-brand/20'
        }`}
      />
      {hint && (
        <span id={`${id}-hint`} role="status" className="absolute right-0 top-10 w-max max-w-[220px] text-right text-[11px] font-semibold text-warn-text">
          {hint}
        </span>
      )}
    </span>
  )
}

// ---------------------------------------------------------------- student identity
function IdentityBar({ detail, onAssign }: { detail: SubmissionDetail; onAssign: (studentId: string) => void }) {
  const id = detail.identity ?? {}
  const [changing, setChanging] = useState(!detail.student_id)
  const [choice, setChoice] = useState(id.suggested_student_id ?? '')
  useEffect(() => {
    setChanging(!detail.student_id)
    setChoice(detail.identity?.suggested_student_id ?? '')
  }, [detail.id, detail.student_id, detail.identity?.suggested_student_id])
  const read = [id.extracted_name, id.extracted_id].filter(Boolean).join(', ')
  const how = id.method === 'id' ? 'Matched by student ID' : id.method === 'name' ? 'Matched by name' : id.method === 'teacher' ? 'Assigned by you' : id.method === 'teacher_upload' ? 'Chosen at upload' : null
  const approved = detail.status === 'approved'

  if (!changing && detail.student_id)
    return (
      <p className="flex flex-wrap items-center gap-x-2 px-1 text-[13px] text-muted">
        <UserRound className="h-3.5 w-3.5" aria-hidden />
        {how ?? 'Student'}
        {read && <span>· paper says &quot;{read}&quot;</span>}
        {!approved && (
          <button type="button" className="ml-1 rounded font-semibold text-brand-dark hover:underline" onClick={() => setChanging(true)}>
            Change student
          </button>
        )}
      </p>
    )
  const options = detail.roster.filter((r) => !r.has_paper)
  return (
    <section className="animate-fade card border-warn-border bg-warn-bg/40 px-4 py-4 sm:px-5" aria-label="Student identity">
      <div className="flex items-start gap-3">
        <UserRoundX className="mt-0.5 h-5 w-5 shrink-0 text-warn-text" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-semibold text-warn-text">{detail.student_id ? 'Change the student for this paper' : 'Student: Not identified'}</p>
          <p className="mt-0.5 text-[13px] text-[#3B4260]">
            {id.reason ?? 'TsekMate could not match this paper to the class roster.'} {read && `The paper says "${read}".`} Grading is not affected.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <label className="sr-only" htmlFor="assign-student">
              Student
            </label>
            <select id="assign-student" className="field h-10 w-full text-[14px] sm:w-auto sm:min-w-[260px]" value={choice} onChange={(e) => setChoice(e.target.value)}>
              <option value="">Choose a student from {detail.activity.class_name}…</option>
              {options.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} · {r.id}
                  {r.id === id.suggested_student_id ? ' (suggested)' : ''}
                </option>
              ))}
            </select>
            <Button size="sm" variant="dark" className="h-10" disabled={!choice} onClick={() => onAssign(choice)}>
              Assign
            </Button>
            {detail.student_id && (
              <Button size="sm" variant="ghost" className="h-10" onClick={() => setChanging(false)}>
                Cancel
              </Button>
            )}
          </div>
          {options.length === 0 && <p className="mt-2 text-[12px] text-muted">Every student on the roster already has a paper. Delete or reassign a paper first.</p>}
        </div>
      </div>
    </section>
  )
}
