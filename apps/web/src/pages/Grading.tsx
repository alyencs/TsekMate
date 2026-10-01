import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { BellRing, CircleCheck, CircleX, Clock, Hourglass, Loader2, Sparkles } from 'lucide-react'
import { api } from '../lib/api'
import { clockTime, duration } from '../lib/format'
import type { GradingProgress, SaverStatus } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { AppShell } from '../components/layout/AppShell'
import { ErrorState } from '../components/ui/States'
import { Button } from '../components/ui/Button'

export default function Grading() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const returnTo = params.get('return') // Grade again: go back to that paper when done
  const activity = useAsync(() => api.activity(id), [id])
  const [prog, setProg] = useState<GradingProgress | null>(null)
  const [error, setError] = useState<string | null>(null)
  const timer = useRef<number>()
  const saverRef = useRef(false)
  const [round, setRound] = useState(0) // restarts polling after "Grade remaining papers"
  const [restarting, setRestarting] = useState(false)

  useEffect(() => {
    let alive = true
    let failures = 0
    const tick = async () => {
      try {
        const p = await api.gradingProgress(id)
        if (!alive) return
        setProg(p)
        saverRef.current = !!p.saver
        setError(null)
        failures = 0
        if (!p.running && p.total > 0 && p.done >= p.total && !p.items.some((i) => i.state === 'stopped')) {
          timer.current = window.setTimeout(() => navigate(returnTo ? `/submissions/${returnTo}` : `/queue?activity=${id}`), 1400)
          return
        }
        // Nothing is running any more: stop asking. The page shows what is left and how to continue.
        if (!p.running) return
      } catch (e) {
        if (!alive) return
        setError((e as Error).message)
        if (++failures >= 5) return // the server is unreachable: stop polling; the error stays on screen
      }
      // Saver results arrive in one go after minutes to hours, so there is no need to ask every second.
      if (alive) timer.current = window.setTimeout(tick, saverRef.current ? 15000 : 1200)
    }
    tick()
    return () => {
      alive = false
      window.clearTimeout(timer.current)
    }
  }, [id, navigate, returnTo, round])

  async function gradeRemaining() {
    setRestarting(true)
    try {
      await api.startGrading(id)
      setError(null)
      setRound((r) => r + 1)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setRestarting(false)
    }
  }

  const total = prog?.total ?? 0
  const done = prog?.done ?? 0
  const pct = total ? Math.round((done / total) * 100) : 0
  const items = prog?.items ?? []
  const cur = Math.max(0, items.findIndex((i) => i.state === 'checking' || i.state === 'waiting'))
  const start = Math.max(0, Math.min(cur - 2, items.length - 5))
  const windowed = items.slice(start, start + 5)
  const short = (activity.data?.title ?? '').split(':')[0].replace(/^Solving /, '')
  const failed = items.filter((i) => i.state === 'failed').length
  const stopped = items.filter((i) => i.state === 'stopped').length
  const halted = !!prog && !prog.running && (stopped > 0 || (total > 0 && done < total))
  const saver = prog?.saver ?? null

  return (
    <AppShell active="queue" contentClassName="flex items-start justify-center px-8 py-[140px]">
      {error && !prog ? (
        <ErrorState message={error} />
      ) : (
        <section className="relative w-full max-w-[598px] rounded-2xl border border-line bg-white px-10 pb-10 pt-20 text-center shadow-pop">
          <Sparkles className="absolute right-6 top-4 h-12 w-12 text-brand-tint/70" aria-hidden />
          <span className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-brand-light text-brand" aria-hidden>
            <Sparkles className="h-8 w-8" />
          </span>
          <h1 className="mt-6 text-[24px] font-bold">
            {total === 0 ? 'Nothing to check' : returnTo ? 'Grading this paper again' : `TsekMate is checking ${total} paper${total === 1 ? '' : 's'}`}
          </h1>
          <p className="mt-3 text-[15px] text-muted">Our AI is analyzing every step of the students&apos; work against your rubric.</p>
          {saver && <SaverNotice saver={saver} />}

          <div className="mt-10 flex items-center justify-between text-[15px]">
            <span className="font-semibold" aria-live="polite" aria-atomic="true">
              {done} of {total} done
            </span>
            <span className="font-semibold text-brand">{pct}%</span>
          </div>
          <div className="mt-4 h-4 overflow-hidden rounded-full border border-line bg-gray-100" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done} aria-label="Grading progress">
            <div className="h-full rounded-full bg-brand transition-all duration-500" style={{ width: `${pct}%` }} />
          </div>

          {windowed.length > 0 && (
            <ul className="mt-10 overflow-hidden rounded-card border border-line text-left">
              {windowed.map((i) => (
                <li key={i.submission_id} className={`animate-fade flex items-center gap-3 border-b border-line px-6 py-4 transition-colors last:border-0 ${i.state === 'checking' ? 'bg-[#FFFBF7]' : i.state === 'waiting' ? 'text-gray-400' : ''}`}>
                  <span className="flex-1 text-[15px]">{i.student_name ?? (i.state === 'done' || i.state === 'failed' ? 'Student not identified' : 'Reading name…')}</span>
                  <span className="text-[13px] tabular-nums text-muted">{i.student_id ?? short}</span>
                  {i.state === 'done' && (
                    <span className="flex items-center gap-1.5 text-[15px] font-semibold text-[#16A34A]">
                      <CircleCheck className="h-4 w-4 fill-[#16A34A] text-white" aria-hidden /> Done
                    </span>
                  )}
                  {i.state === 'checking' && (
                    <span className="flex items-center gap-1.5 text-[15px] font-semibold text-brand">
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Checking...
                    </span>
                  )}
                  {i.state === 'waiting' && (
                    <span className="flex items-center gap-1.5 text-[15px] font-semibold">
                      <Hourglass className="h-4 w-4" aria-hidden /> Waiting
                    </span>
                  )}
                  {i.state === 'stopped' && (
                    <span className="flex items-center gap-1.5 text-[15px] font-semibold text-muted">
                      <CircleX className="h-4 w-4" aria-hidden /> Not graded
                    </span>
                  )}
                  {i.state === 'failed' && (
                    <span className="flex items-center gap-1.5 text-[15px] font-semibold text-bad-strong">
                      <CircleX className="h-4 w-4" aria-hidden /> Needs teacher
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
          {failed > 0 && (
            <p className="mt-4 text-[13px] text-bad-text" role="status">
              {failed} paper{failed === 1 ? '' : 's'} could not be graded automatically. Open {failed === 1 ? 'it' : 'them'} from the queue and press Grade again, or grade by hand.
            </p>
          )}
          {halted && (
            <div className="mt-6 rounded-card border border-line bg-[#F9F7F5] px-5 py-4 text-left" role="status">
              <p className="text-[15px] font-semibold">Grading stopped before every paper was checked.</p>
              <p className="mt-1 text-[13px] text-muted">
                This happens when the server restarts during grading. Nothing was lost: {prog?.pending ?? stopped} paper{(prog?.pending ?? stopped) === 1 ? ' is' : 's are'} waiting to be graded.
              </p>
              <div className="mt-4 flex gap-3">
                <Button onClick={gradeRemaining} loading={restarting} disabled={!prog?.pending}>
                  Grade remaining papers
                </Button>
                <Button variant="secondary" onClick={() => navigate(`/queue?activity=${id}`)}>
                  Go to the review queue
                </Button>
              </div>
            </div>
          )}
          {total === 0 && prog && !halted && (
            <Button className="mt-8" onClick={() => navigate(`/queue?activity=${id}`)}>
              Go to the review queue
            </Button>
          )}
          <p className="mt-10 text-[12px] italic text-gray-400">You will review every result before anything is saved.</p>
        </section>
      )}
    </AppShell>
  )
}

function SaverNotice({ saver }: { saver: SaverStatus }) {
  const when =
    saver.eta_seconds !== null
      ? `About ${duration(saver.eta_seconds)} left`
      : `Taking longer than usual. Results will be ready by ${clockTime(saver.deadline)} at the latest`
  const basis =
    saver.eta_basis === 'progress'
      ? 'Estimated from the papers graded so far.'
      : saver.eta_basis === 'history'
        ? 'Estimated from how long your earlier Saver grading took.'
        : 'Saver grading usually finishes within an hour (at most 24 hours).'
  return (
    <div className="mt-6 rounded-card border border-line bg-brand-light/40 px-5 py-4 text-left" role="status" aria-live="polite">
      <p className="flex items-center gap-2 text-[15px] font-semibold">
        <Clock className="h-4 w-4 text-brand" aria-hidden /> {when}
      </p>
      <p className="mt-1 text-[13px] text-muted">
        Saver mode (half price). Sent at {clockTime(saver.submitted_at)}. {basis}
      </p>
      <p className="mt-2 flex items-center gap-2 text-[13px] text-muted">
        <BellRing className="h-3.5 w-3.5" aria-hidden /> You can close this page. You&apos;ll get a notification when the drafts are ready.
      </p>
    </div>
  )
}
