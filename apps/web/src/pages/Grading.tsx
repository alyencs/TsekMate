import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { CircleCheck, CircleX, Hourglass, Loader2, Sparkles } from 'lucide-react'
import { api } from '../lib/api'
import type { GradingProgress } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { AppShell } from '../components/layout/AppShell'
import { ErrorState } from '../components/ui/States'
import { Button } from '../components/ui/Button'

export default function Grading() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const activity = useAsync(() => api.activity(id), [id])
  const [prog, setProg] = useState<GradingProgress | null>(null)
  const [error, setError] = useState<string | null>(null)
  const timer = useRef<number>()

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const p = await api.gradingProgress(id)
        if (!alive) return
        setProg(p)
        setError(null)
        if (!p.running && p.total > 0 && p.done >= p.total) {
          timer.current = window.setTimeout(() => navigate(`/queue?activity=${id}`), 1400)
          return
        }
      } catch (e) {
        if (alive) setError((e as Error).message)
      }
      if (alive) timer.current = window.setTimeout(tick, 1200)
    }
    tick()
    return () => {
      alive = false
      window.clearTimeout(timer.current)
    }
  }, [id, navigate])

  const total = prog?.total ?? 0
  const done = prog?.done ?? 0
  const pct = total ? Math.round((done / total) * 100) : 0
  const items = prog?.items ?? []
  const cur = Math.max(0, items.findIndex((i) => i.state === 'checking' || i.state === 'waiting'))
  const start = Math.max(0, Math.min(cur - 2, items.length - 5))
  const windowed = items.slice(start, start + 5)
  const short = (activity.data?.title ?? '').split(':')[0].replace(/^Solving /, '')
  const failed = items.filter((i) => i.state === 'failed').length

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
            {total === 0 ? 'Nothing to check' : `TsekMate is checking ${total} paper${total === 1 ? '' : 's'}`}
          </h1>
          <p className="mt-3 text-[15px] text-muted">Our AI is analyzing every step of the students&apos; work against your rubric.</p>

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
                <li key={i.submission_id} className={`flex items-center gap-3 border-b border-line px-6 py-4 last:border-0 ${i.state === 'checking' ? 'bg-[#FFFBF7]' : i.state === 'waiting' ? 'text-gray-400' : ''}`}>
                  <span className="w-11 text-[13px] font-semibold text-muted">{i.student_id}</span>
                  <span className="flex-1 text-[15px]">{short}</span>
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
              {failed} paper{failed === 1 ? '' : 's'} could not be graded automatically and will wait for you in the queue.
            </p>
          )}
          {total === 0 && prog && (
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
