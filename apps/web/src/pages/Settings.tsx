import { useEffect, useState } from 'react'
import { CircleAlert, CircleCheck } from 'lucide-react'
import { api } from '../lib/api'
import type { AppSettings, FeedbackStyle } from '../lib/types'
import { getReduceMotion, loadSettings, setReduceMotion, setSettingsCache } from '../lib/appSettings'
import { AppShell, TopBar } from '../components/layout/AppShell'
import { Toggle } from '../components/ui/Toggle'
import { ErrorState, Loading, Notice } from '../components/ui/States'

export default function Settings() {
  const [s, setS] = useState<AppSettings | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)
  const [motion, setMotion] = useState(getReduceMotion())

  useEffect(() => {
    loadSettings(true)
      .then(setS)
      .catch((e: Error) => setError(e.message))
  }, [])

  async function save(patch: Partial<Omit<AppSettings, 'ai'>>, label: string) {
    setSaved(null)
    try {
      const r = await api.saveSettings(patch)
      setS(r)
      setSettingsCache(r)
      setSaved(r.rerouted ? `${label} saved. ${r.rerouted} paper${r.rerouted === 1 ? '' : 's'} moved between "Needs review" and "Ready to approve".` : `${label} saved.`)
    } catch (e) {
      setSaved(null)
      setError((e as Error).message)
    }
  }

  return (
    <AppShell active="settings" topbar={<TopBar title="Settings" />}>
      {error ? (
        <ErrorState message={error} onRetry={() => window.location.reload()} />
      ) : !s ? (
        <Loading />
      ) : (
        <div className="mx-auto flex max-w-[760px] flex-col gap-6">
          {saved && (
            <Notice tone="ok" className="sticky top-[76px] z-10 shadow-card">
              <CircleCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              {saved}
            </Notice>
          )}

          <Section title="AI grading">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
              <div>
                <p className="text-[15px] font-semibold">AI-assisted grading</p>
                <p className="mt-0.5 text-[13px] text-muted">
                  {s.ai.available || s.ai.demo_mode
                    ? 'The AI drafts a score for each paper from your rubric. You review and approve every grade.'
                    : 'Not available right now. Ask your TsekMate administrator to finish the setup. You can still grade papers by hand.'}
                </p>
              </div>
              <div className="shrink-0 sm:text-right">
                <p className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[12px] font-semibold ${s.ai.available || s.ai.demo_mode ? 'bg-ok-bg text-ok-text' : 'bg-bad-bg text-bad-text'}`}>
                  {s.ai.available || s.ai.demo_mode ? <CircleCheck className="h-3.5 w-3.5" aria-hidden /> : <CircleAlert className="h-3.5 w-3.5" aria-hidden />}
                  {s.ai.available || s.ai.demo_mode ? 'Ready' : 'Not available'}
                </p>
              </div>
            </div>
            <div>
              <label htmlFor="threshold" className="flex items-center justify-between gap-3 text-[15px] font-semibold">
                Confidence threshold
                <span className="rounded-full bg-brand-light px-2.5 py-0.5 text-[14px] font-semibold tabular-nums text-brand-dark">{Math.round(s.confidence_threshold * 100)}%</span>
              </label>
              <p className="mt-0.5 text-[13px] text-muted">
                A paper goes to &quot;Needs review&quot; if any step is below this confidence. Changing it re-sorts papers that are not approved yet.
              </p>
              <input
                id="threshold"
                type="range"
                min={0.5}
                max={0.95}
                step={0.05}
                value={s.confidence_threshold}
                onChange={(e) => setS({ ...s, confidence_threshold: Number(e.target.value) })}
                onMouseUp={() => save({ confidence_threshold: s.confidence_threshold }, 'Confidence threshold')}
                onKeyUp={() => save({ confidence_threshold: s.confidence_threshold }, 'Confidence threshold')}
                onTouchEnd={() => save({ confidence_threshold: s.confidence_threshold }, 'Confidence threshold')}
                className="mt-3 h-6 w-full cursor-pointer accent-brand"
                aria-valuetext={`${Math.round(s.confidence_threshold * 100)} percent`}
              />
            </div>
            <fieldset>
              <legend className="text-[15px] font-semibold">Default feedback mode for new activities</legend>
              <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:gap-3">
                {(
                  [
                    ['hint_only', 'Hint only'],
                    ['full_solution', 'Full solution'],
                  ] as [FeedbackStyle, string][]
                ).map(([v, l]) => (
                  <label key={v} className={`flex min-h-[44px] cursor-pointer items-center gap-2 rounded-ctl border px-4 py-2 text-[14px] transition-colors ${s.default_feedback_style === v ? 'border-brand bg-brand-light/60 font-semibold' : 'border-line hover:border-brand-tint'}`}>
                    <input type="radio" name="fb" className="h-4 w-4 accent-brand" checked={s.default_feedback_style === v} onChange={() => save({ default_feedback_style: v }, 'Default feedback mode')} />
                    {l}
                  </label>
                ))}
              </div>
            </fieldset>
          </Section>

          <Section title="Grading defaults">
            <Toggle
              id="alt"
              checked={s.default_accept_alternate}
              onChange={(v) => save({ default_accept_alternate: v }, 'Alternate methods default')}
              label="Accept alternate valid methods"
              description="Starting value of this setting when you create a new activity."
            />
            <fieldset>
              <legend className="text-[15px] font-semibold">Default rubric option</legend>
              <p className="mt-0.5 text-[13px] text-muted">Which rubric option is selected first when you create an activity. AI drafts always need your review.</p>
              <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:gap-3">
                {(
                  [
                    ['manual', 'Create your own rubric'],
                    ['ai', 'Generate rubric with AI'],
                  ] as const
                ).map(([v, l]) => (
                  <label key={v} className={`flex min-h-[44px] cursor-pointer items-center gap-2 rounded-ctl border px-4 py-2 text-[14px] transition-colors ${s.default_rubric_mode === v ? 'border-brand bg-brand-light/60 font-semibold' : 'border-line hover:border-brand-tint'}`}>
                    <input type="radio" name="rubric" className="h-4 w-4 accent-brand" checked={s.default_rubric_mode === v} onChange={() => save({ default_rubric_mode: v }, 'Default rubric option')} />
                    {l}
                  </label>
                ))}
              </div>
            </fieldset>
            <fieldset>
              <legend className="text-[15px] font-semibold">Grading speed</legend>
              <p className="mt-0.5 text-[13px] text-muted">
                How &quot;Grade all&quot; checks a class set. Saver costs half as much but results take longer: usually within an hour, at most 24 hours. You&apos;ll see an estimate
                and get a notification when the drafts are ready. Grade again on one paper is always fast.
              </p>
              <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:gap-3">
                {(
                  [
                    ['fast', 'Fast (results in minutes)'],
                    ['saver', 'Saver (half price, slower)'],
                  ] as const
                ).map(([v, l]) => (
                  <label key={v} className={`flex min-h-[44px] cursor-pointer items-center gap-2 rounded-ctl border px-4 py-2 text-[14px] transition-colors ${s.grading_mode === v ? 'border-brand bg-brand-light/60 font-semibold' : 'border-line hover:border-brand-tint'}`}>
                    <input type="radio" name="grading_mode" className="h-4 w-4 accent-brand" checked={s.grading_mode === v} onChange={() => save({ grading_mode: v }, 'Grading speed')} />
                    {l}
                  </label>
                ))}
              </div>
            </fieldset>
          </Section>

          <Section title="Privacy">
            <Toggle
              id="del"
              checked={s.delete_images_on_approve}
              onChange={(v) => save({ delete_images_on_approve: v }, 'Photo deletion')}
              label="Delete the photo after approval"
              description="After you approve a paper, its photo is deleted from storage. Scores and feedback are kept."
            />
            <p className="text-[13px] leading-relaxed text-muted">
              Photos are stored in a private bucket and shown only through short-lived signed links. Each photo, including the name written on it, is sent to an outside AI service for grading.
              Use only synthetic papers or papers from people who agreed, until your school has a data processing agreement in place.
            </p>
          </Section>

          <Section title="Interface" note="Saved in this browser only">
            <Toggle
              id="motion"
              checked={motion}
              onChange={(v) => {
                setMotion(v)
                setReduceMotion(v)
                setSaved('Motion preference saved in this browser.')
              }}
              label="Reduce motion"
              description="Turns off page and panel animations. TsekMate also follows your system's reduce-motion setting."
            />
          </Section>
        </div>
      )}
    </AppShell>
  )
}

function Section({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="card px-5 py-6 sm:px-8 sm:py-7" aria-label={title}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="text-[17px] font-semibold">{title}</h2>
        {note && <span className="text-[12px] text-muted">{note}</span>}
      </div>
      <div className="mt-5 flex flex-col gap-6">{children}</div>
    </section>
  )
}
