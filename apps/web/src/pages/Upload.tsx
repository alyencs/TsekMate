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
import { ErrorState, Loading } from '../components/ui/States'
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
          <p className="flex items-center gap-3 text-[16px] font-semibold" aria-live="polite">
            <span className={`h-3 w-3 rounded-full ${ready ? 'bg-[#16A34A]' : 'bg-gray-300'}`} aria-hidden />
            {ready} paper{ready === 1 ? '' : 's'} ready
          </p>
          <Button
            size="lg"
            className="w-[270px]"
            onClick={grade}
            disabled={!ready || rubricBlocked}
            title={rubricBlocked ? 'Fix the rubric before grading' : undefined}
            loading={busy && ready > 0} iconRight={<Sparkles className="h-5 w-5" aria-hidden />}>
            Grade with TsekMate
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
            <div className="mt-2 flex items-center gap-3">
              {changing && all.data ? (
                <label className="flex items-center gap-2">
                  <span className="sr-only">Choose activity</span>
                  <select
                    className="field h-[42px] w-[360px]"
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
                <div className="flex h-[42px] items-center gap-3 rounded-ctl border border-line bg-white px-4 shadow-card">
                  <span className="text-[15px] font-semibold">{activity.data.title}</span>
                  <SubjectChip subject={activity.data.subject} size="sm" />
                </div>
              )}
              <button className="text-[15px] font-semibold text-brand-dark hover:underline" onClick={() => setChanging((c) => !c)}>
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
              className={`mt-8 flex flex-col items-center rounded-2xl border-2 border-dashed bg-white px-6 py-12 text-center transition-colors ${drag ? 'border-brand bg-brand-light/40' : 'border-line'}`}
            >
              <span className="flex h-20 w-20 items-center justify-center rounded-full bg-brand-light text-brand" aria-hidden>
                <Camera className="h-7 w-7" />
              </span>
              <h2 className="mt-6 text-[20px] font-bold">Drag photos here or take a photo</h2>
              <p className="mt-2 text-[14px] text-muted">JPG, PNG, WEBP or PDF files, up to 10 MB each.</p>
              <div className="mt-8 flex gap-4">
                <Button size="lg" className="h-11 px-6 text-[16px]" onClick={() => fileRef.current?.click()} loading={busy && !ready}>
                  Choose files
                </Button>
                <Button size="lg" variant="secondary" className="h-11 px-6 text-[16px]" onClick={() => camRef.current?.click()}>
                  Use camera
                </Button>
              </div>
              <input ref={fileRef} type="file" multiple accept={ACCEPT} className="hidden" aria-label="Choose files" onChange={(e) => pick(e.currentTarget)} />
              <input ref={camRef} type="file" accept="image/*" capture="environment" className="hidden" aria-label="Take a photo" onChange={(e) => pick(e.currentTarget)} />
            </div>

            {msg && (
              <p role={msg.tone === 'bad' ? 'alert' : 'status'} className={`mt-4 flex items-center gap-2 rounded-ctl border px-4 py-3 text-[14px] ${msg.tone === 'bad' ? 'border-bad-border bg-bad-bg text-bad-text' : 'border-ok-border bg-ok-bg text-ok-text'}`}>
                {msg.tone === 'bad' ? <CircleAlert className="h-4 w-4 shrink-0" aria-hidden /> : <CircleCheck className="h-4 w-4 shrink-0" aria-hidden />}
                {msg.text}
              </p>
            )}

            <div className="mt-6 rounded-card bg-[#FFF1E6] px-6 py-4">
              <p className="text-[14px] font-semibold text-brand-dark">Tips for best results</p>
              <p className="mt-1.5 text-[15px] text-gray-700">Use good lighting, keep the paper flat, and make sure the student&apos;s name and ID are readable.</p>
            </div>

            <div className="mt-14 flex items-center justify-between">
              <h2 className="text-[17px] font-semibold">Uploaded papers</h2>
              <p className="text-[15px] text-gray-600">{papers.data?.length ?? 0} papers detected</p>
            </div>
            {papers.error ? (
              <ErrorState message={papers.error} onRetry={papers.reload} />
            ) : !papers.data ? (
              <Loading />
            ) : list.length === 0 ? (
              <p className="mt-6 rounded-card border border-dashed border-line bg-white px-6 py-10 text-center text-[15px] text-muted">No papers yet. Add photos above.</p>
            ) : (
              <ul className="mt-5 grid grid-cols-2 gap-6 lg:grid-cols-4">
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
      <div className={`lift relative aspect-[3/4] overflow-hidden rounded-card border bg-[#F9F7F5] ${bad ? 'border-warn-border ring-2 ring-warn-border/60' : 'border-line'}`}>
        {p.image_url && !isPdf ? (
          <img src={p.image_url} alt={`Photo of the paper for ${p.student_name ?? p.student_id ?? 'an unidentified student'}`} loading="lazy" className="h-full w-full object-cover object-top" />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-[14px] text-gray-400">
            {isPdf && <FileText className="h-8 w-8" aria-hidden />}
            {p.student_id ?? 'Paper'}
          </div>
        )}
        <span className={`absolute right-2.5 top-2.5 flex h-6 items-center gap-1 rounded-full px-2 text-[11px] font-semibold text-white ${bad ? 'bg-[#CA8A04]' : 'bg-[#16A34A]'}`}>
          {bad ? <CircleAlert className="h-3.5 w-3.5" aria-hidden /> : <CircleCheck className="h-3.5 w-3.5" aria-hidden />}
          {bad ? 'Retake suggested' : 'Ready'}
        </span>
        {bad && <span className="absolute inset-x-2 bottom-2 rounded-ctl border border-line bg-white/95 px-2 py-1.5 text-[12px] font-semibold text-warn-text">{p.quality?.reason}</span>}
      </div>
      <div className="mt-2 flex items-center justify-between gap-2 px-1">
        {p.student_id ? (
          <StudentLabel id={p.student_id} name={p.student_name} size="sm" />
        ) : (
          <span className="text-[13px] font-medium text-muted">{p.status === 'uploaded' || p.status === 'grading' ? 'Name read when graded' : 'Not identified'}</span>
        )}
        {p.status !== 'approved' && (
          <button onClick={onDelete} className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-bad-strong" aria-label={`Delete paper ${p.student_name ?? p.student_id ?? 'not identified'}`}>
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>
    </li>
  )
}
