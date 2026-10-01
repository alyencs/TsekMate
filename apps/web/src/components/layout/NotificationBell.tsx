import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, CheckCheck, CircleAlert, CircleCheck, FlagTriangleRight, Sparkles, Upload } from 'lucide-react'
import { api } from '../../lib/api'
import type { AppNotification, Notifications } from '../../lib/types'
import { timeAgo } from '../../lib/format'

const ICON: Record<AppNotification['kind'], JSX.Element> = {
  grading_done: <Sparkles className="h-4 w-4 text-brand" aria-hidden />,
  needs_review: <FlagTriangleRight className="h-4 w-4 text-[#CA8A04]" aria-hidden />,
  grading_failed: <CircleAlert className="h-4 w-4 text-bad-strong" aria-hidden />,
  regrade_ok: <CircleCheck className="h-4 w-4 text-[#16A34A]" aria-hidden />,
  upload_done: <Upload className="h-4 w-4 text-muted" aria-hidden />,
}

export function NotificationBell() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<Notifications | null>(null)
  const [error, setError] = useState<string | null>(null)
  const box = useRef<HTMLDivElement>(null)

  const load = useCallback(() => {
    api
      .notifications()
      .then((d) => {
        setData(d)
        setError(null)
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  useEffect(() => {
    load()
    const t = window.setInterval(load, 20000) // picks up grading results that finish in the background
    return () => window.clearInterval(t)
  }, [load])

  useEffect(() => {
    if (!open) return
    load()
    const onDown = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false)
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, load])

  async function openItem(n: AppNotification) {
    setOpen(false)
    if (!n.read) api.readNotification(n.id).then(setData).catch(() => undefined)
    if (n.link) navigate(n.link)
  }

  const unread = data?.unread ?? 0
  return (
    <div className="relative" ref={box}>
      <button
        className="relative rounded-full p-2 text-gray-600 transition-colors hover:bg-gray-100 hover:text-ink"
        aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((o) => !o)}
      >
        <Bell className="h-5 w-5" aria-hidden />
        {unread > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-bad-strong px-1 text-[10px] font-bold text-white" aria-hidden>
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div role="dialog" aria-label="Notifications" className="animate-pop absolute right-0 top-12 z-40 w-[380px] origin-top-right overflow-hidden rounded-card border border-line bg-white shadow-pop">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <p className="text-[15px] font-semibold">Notifications</p>
            {unread > 0 && (
              <button className="flex items-center gap-1 text-[12px] font-semibold text-brand-dark hover:underline" onClick={() => api.readAllNotifications().then(setData)}>
                <CheckCheck className="h-3.5 w-3.5" aria-hidden /> Mark all as read
              </button>
            )}
          </div>
          <div className="max-h-[420px] overflow-y-auto">
            {error ? (
              <p className="px-4 py-6 text-[13px] text-bad-text">{error}</p>
            ) : !data ? (
              <p className="px-4 py-6 text-[13px] text-muted">Loading…</p>
            ) : data.items.length === 0 ? (
              <div className="px-4 py-10 text-center">
                <Bell className="mx-auto h-6 w-6 text-gray-300" aria-hidden />
                <p className="mt-2 text-[14px] font-semibold">You&apos;re all caught up</p>
                <p className="text-[13px] text-muted">Grading results and papers that need you will show up here.</p>
              </div>
            ) : (
              <ul>
                {data.items.map((n) => (
                  <li key={n.id}>
                    <button onClick={() => openItem(n)} className={`flex w-full gap-3 border-b border-line px-4 py-3 text-left transition-colors last:border-0 hover:bg-[#FFFBF7] ${n.read ? '' : 'bg-brand-light/40'}`}>
                      <span className="mt-0.5 shrink-0">{ICON[n.kind] ?? ICON.grading_done}</span>
                      <span className="min-w-0 flex-1">
                        <span className={`block text-[14px] ${n.read ? 'font-medium text-gray-700' : 'font-semibold text-ink'}`}>{n.title}</span>
                        {n.body && <span className="mt-0.5 block text-[13px] leading-snug text-muted">{n.body}</span>}
                        <span className="mt-1 block text-[11px] text-gray-400">{timeAgo(n.created_at)}</span>
                      </span>
                      {!n.read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-brand" aria-label="Unread" />}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
