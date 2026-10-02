import { useRef, useState, type DragEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Camera, CircleAlert, CircleCheck, FileText, Sparkles, Trash2 } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { rememberActivity } from '../lib/session'
import type { UploadedPaper } from '../lib/types'
import { AppShell, TopBar } from '../components/layout/AppShell'
import { Button } from '../components/ui/Button'
import { SubjectChip } from '../components/ui/Chip'
import { ErrorState, Loading, Notice } from '../components/ui/States'
import { StudentLabel } from '../components/ui/StudentLabel'
import { RubricCard } from '../components/RubricCard'

const ACCEPT = 'image/jpeg,image/png,image/webp,application/pdf'
const MAX_BYTES = 10 * 1024 * 1024
// Hosts cap the size of one request (Cloud Run: 32 MiB), so a class set is sent in several smaller uploads.
const MAX_REQUEST_BYTES = 24 * 1024 * 1024

function batches(files: File[]): File[][] {
  const out: File[][] = []
  let cur: File[] = []
  let size = 0
  for (const f of files) {
    if (cur.length && (size + f.size > MAX_REQUEST_BYTES || cur.length >= 50)) {
      out.push(cur)
      cur = []
      size = 0
    }
    cur.push(f)
    size += f.size
  }
  if (cur.length) out.push(cur)
  return out
}

export default function Upload() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ tone: 'ok' | 'bad'; text: string } | null>(null)
  const [drag, setDrag] = useState(false)
  const [changing, setChanging] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const camRef = useRef<HTMLInputElement>(null)
  const activity = useAsync(() => api.activity(id), [id])
  const papers = useAsync(() => api.submissions(id), [id])
  const all = useAsync(() => api.activities(), [])
  rememberActivity(id)

  async function upload(files: File[]) {
    if (!files.length) return
    const big = files.filter((f) => f.size > MAX_BYTES)
    if (big.length) {
      setMsg({ tone: 'bad', text: `${big.map((f) => f.name).join(', ')}: larger than 10 MB. Nothing was uploaded; remove ${big.length === 1 ? 'it' : 'them'} and try again.` })
      return
    }
    setBusy(true)
    setMsg(null)
    let added = 0
    try {
      for (const group of batches(files)) added += (await api.upload(id, group)).length
      setMsg({ tone: 'ok', text: `Uploaded ${added} paper${added === 1 ? '' : 's'}. TsekMate reads each student's name and ID while grading and matches them to the class roster.` })
    } catch (e) {
      const done = added ? ` ${added} paper${added === 1 ? ' was' : 's were'} uploaded before this error.` : ''
      setMsg({ tone: 'bad', text: (e as Error).message + done })
    } finally {
      papers.reload()
      setBusy(false)
    }
  }

  async function remove(p: UploadedPaper) {
    if (!confirm(`Delete the paper for ${p.student_name ?? p.student_id ?? 'this unidentified student'}? You can upload a retake afterwards.`)) return
    try {
      await api.deleteSubmission(p.id)
      papers.reload()
    } catch (e) {
      setMsg({ tone: 'bad', text: (e as Error).message })
    }
  }

  async function grade() {
    setBusy(true)
    try {
      await api.startGrading(id)
      navigate(`/activities/${id}/grading`)
    } catch (e) {
      setMsg({ tone: 'bad', text: (e as Error).message })
      setBusy(false)
    }
  }

  // Clear the input after reading it, so choosing the same file again (for example after deleting it) still works.
  const pick = (input: HTMLInputElement) => {
    const files = Array.from(input.files ?? [])
    input.value = ''
    upload(files)
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDrag(false)
    upload(Array.from(e.dataTransfer.files))
  }
  const list = (papers.data ?? []).filter((p) => !q || `${p.student_id ?? ''} ${p.student_name ?? ''}`.toLowerCase().includes(q.toLowerCase()))
  const ready = (papers.data ?? []).filter((p) => p.status === 'uploaded' || p.status === 'failed').length
  const rubricBlocked = (activity.data?.rubric_errors.length ?? 0) > 0

  return (
    <AppShell
      active="queue"
      topbar={<TopBar title="Upload work" search={{ placeholder: 'Search...', value: q, onChange: setQ }} />}
      footer={
        <>
          <p className="flex min-w-0 items-center gap-2 text-[14px] font-semibold sm:gap-3 sm:text-[16px]" aria-live="polite">
            <span className={`h-2.5 w-2.5 shrink-0 rounded-full sm:h-3 sm:w-3 ${ready ? 'bg-ok-bar' : 'bg-[#CBD2E1]'}`} aria-hidden />
            {ready} paper{ready === 1 ? '' : 's'} ready
          </p>
          <Button
            size="lg"
            className="shrink-0 px-4 sm:w-[270px]"
            onClick={grade}
            disabled={!ready || rubricBlocked}
            title={rubricBlocked ? 'Fix the rubric before grading' : undefined}
            loading={busy && ready > 0} iconRight={<Sparkles className="h-5 w-5" aria-hidden />}>
            <span className="sm:hidden">Grade</span>
            <span className="hidden sm:inline">Grade with TsekMate</span>
          </Button>
        </>
      }
    >
      <div className="mx-auto max-w-[936px]">
        {activity.error ? (
          <ErrorState message={activity.error} onRetry={activity.reload} />
        ) : !activity.data ? (
          <Loading />
        ) : (
          <>
            <p className="label-caps">Activity</p>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">
              {changing && all.data ? (
                <label className="flex min-w-0 flex-1 items-center gap-2 sm:flex-none">
                  <span className="sr-only">Choose activity</span>
                  <select
                    className="field h-11 w-full sm:w-[380px]"
                    value={id}
                    onChange={(e) => {
                      setChanging(false)
                      navigate(`/activities/${e.target.value}/upload`)
                    }}
                  >
                    {all.data.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.title} ({a.class_name})
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <div className="flex min-h-[44px] min-w-0 flex-wrap items-center gap-x-3 gap-y-1 rounded-ctl border border-line bg-white px-4 py-2 shadow-card">
                  <span className="min-w-0 text-[15px] font-semibold">{activity.data.title}</span>
                  <SubjectChip subject={activity.data.subject} size="sm" />
                </div>
              )}
              <button type="button" className="rounded px-1 text-[14px] font-semibold text-brand-dark hover:underline" aria-expanded={changing} onClick={() => setChanging((c) => !c)}>
                {changing ? 'Cancel' : 'Change'}
              </button>
            </div>
            <RubricCard activity={activity.data} onSaved={(a) => activity.setData(a)} />

            <div
              onDragOver={(e) => {
                e.preventDefault()
                setDrag(true)
              }}
              onDragLeave={() => setDrag(false)}
              onDrop={onDrop}
              className={`mt-6 flex flex-col items-center rounded-2xl border-2 border-dashed bg-white px-4 py-8 text-center transition-colors sm:mt-8 sm:px-6 sm:py-12 ${drag ? 'border-brand bg-brand-light/50' : 'border-[#CBD2E1] hover:border-brand-tint'}`}
            >
              <span className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-light text-brand sm:h-20 sm:w-20" aria-hidden>
                <Camera className="h-7 w-7" />
              </span>
              <h2 className="mt-5 text-[18px] font-bold sm:mt-6 sm:text-[20px]">
                <span className="hidden sm:inline">Drag photos here or take a photo</span>
                <span className="sm:hidden">Add photos of student work</span>
              </h2>
              <p className="mt-2 text-[14px] text-muted">JPG, PNG, WEBP or PDF files, up to 10 MB each.</p>
              <div className="mt-6 flex w-full flex-col gap-3 sm:mt-8 sm:w-auto sm:flex-row sm:gap-4">
                <Button size="lg" className="w-full sm:w-auto" onClick={() => fileRef.current?.click()} loading={busy && !ready}>
                  Choose files
                </Button>
                <Button size="lg" variant="secondary" className="w-full sm:w-auto" icon={<Camera className="h-4 w-4" aria-hidden />} onClick={() => camRef.current?.click()}>
                  Use camera
                </Button>
              </div>
              <input ref={fileRef} type="file" multiple accept={ACCEPT} className="hidden" aria-label="Choose files" onChange={(e) => pick(e.currentTarget)} />
              <input ref={camRef} type="file" accept="image/*" capture="environment" className="hidden" aria-label="Take a photo" onChange={(e) => pick(e.currentTarget)} />
            </div>

            {msg && (
              <Notice tone={msg.tone} className="mt-4">
                {msg.tone === 'bad' ? <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /> : <CircleCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}
                {msg.text}
              </Notice>
            )}

            <div className="mt-5 flex gap-3 rounded-card border border-brand-100 bg-brand-light px-4 py-4 sm:px-6">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden />
              <div>
              <p className="text-[14px] font-semibold text-navy">Tips for best results</p>
              <p className="mt-1 text-[14px] text-[#3B4260]">Use good lighting, keep the paper flat, and make sure the student&apos;s name and ID are readable.</p>
              </div>
            </div>

            <div className="mt-10 flex flex-wrap items-baseline justify-between gap-2 sm:mt-14">
              <h2 className="text-[17px] font-semibold">Uploaded papers</h2>
              <p className="text-[14px] text-muted">{papers.data?.length ?? 0} papers detected</p>
            </div>
            {papers.error ? (
              <ErrorState message={papers.error} onRetry={papers.reload} />
            ) : !papers.data ? (
              <Loading />
            ) : list.length === 0 ? (
              <p className="mt-6 rounded-card border border-dashed border-line bg-white px-6 py-10 text-center text-[15px] text-muted">No papers yet. Add photos above.</p>
            ) : (
              <ul className="mt-4 grid grid-cols-2 gap-3 sm:mt-5 sm:grid-cols-3 sm:gap-5 lg:grid-cols-4">
                {list.map((p) => (
                  <PaperCard key={p.id} p={p} onDelete={() => remove(p)} />
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </AppShell>
  )
}

function PaperCard({ p, onDelete }: { p: UploadedPaper; onDelete: () => void }) {
  const bad = p.quality && !p.quality.ok
  const isPdf = p.image_url?.includes('.pdf')
  return (
    <li>
      <div className={`lift relative aspect-[3/4] overflow-hidden rounded-card border bg-soft ${bad ? 'border-warn-border ring-2 ring-warn-border/60' : 'border-line'}`}>
        {p.image_url && !isPdf ? (
          <img src={p.image_url} alt={`Photo of the paper for ${p.student_name ?? p.student_id ?? 'an unidentified student'}`} loading="lazy" className="h-full w-full object-cover object-top" />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-[14px] text-[#8790A6]">
            {isPdf && <FileText className="h-8 w-8" aria-hidden />}
            {p.student_id ?? 'Paper'}
          </div>
        )}
        <span className={`absolute right-2.5 top-2.5 flex h-6 items-center gap-1 rounded-full px-2 text-[11px] font-semibold text-white ${bad ? 'bg-warn-text' : 'bg-ok-text'}`}>
          {bad ? <CircleAlert className="h-3.5 w-3.5" aria-hidden /> : <CircleCheck className="h-3.5 w-3.5" aria-hidden />}
          {bad ? 'Retake suggested' : 'Ready'}
        </span>
        {bad && <span className="absolute inset-x-2 bottom-2 rounded-ctl border border-line bg-white/95 px-2 py-1.5 text-[12px] font-semibold text-warn-text">{p.quality?.reason}</span>}
      </div>
      <div className="mt-2 flex min-w-0 items-center justify-between gap-1 px-1">
        {p.student_id ? (
          <StudentLabel id={p.student_id} name={p.student_name} size="sm" />
        ) : (
          <span className="text-[13px] font-medium text-muted">{p.status === 'uploaded' || p.status === 'grading' ? 'Name read when graded' : 'Not identified'}</span>
        )}
        {p.status !== 'approved' && (
          <button type="button" onClick={onDelete} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-ctl text-[#8790A6] transition-colors hover:bg-bad-bg hover:text-bad-strong" aria-label={`Delete paper ${p.student_name ?? p.student_id ?? 'not identified'}`}>
            <Trash2 className="h-4 w-4" aria-hidden />
          </button>
        )}
      </div>
    </li>
  )
}
