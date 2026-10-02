import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Bell, CheckCheck, CircleAlert, CircleCheck, FlagTriangleRight, Sparkles, Upload } from 'lucide-react'
import { api } from '../../lib/api'
import type { AppNotification, Notifications } from '../../lib/types'
import { timeAgo } from '../../lib/format'
import { useDismiss } from '../../lib/a11y'

export const NOTIFICATION_ICON: Record<AppNotification['kind'], { icon: JSX.Element; bg: string }> = {
  grading_done: { icon: <Sparkles className="h-4 w-4 text-brand" aria-hidden />, bg: 'bg-brand-light' },
  needs_review: { icon: <FlagTriangleRight className="h-4 w-4 text-warn-bar" aria-hidden />, bg: 'bg-warn-bg' },
  grading_failed: { icon: <CircleAlert className="h-4 w-4 text-bad-strong" aria-hidden />, bg: 'bg-bad-bg' },
  regrade_ok: { icon: <CircleCheck className="h-4 w-4 text-ok-bar" aria-hidden />, bg: 'bg-ok-bg' },
  upload_done: { icon: <Upload className="h-4 w-4 text-muted" aria-hidden />, bg: 'bg-soft' },
}

export function NotificationIcon({ kind }: { kind: AppNotification['kind'] }) {
  const k = NOTIFICATION_ICON[kind] ?? NOTIFICATION_ICON.grading_done
  return <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${k.bg}`}>{k.icon}</span>
}

export function NotificationBell() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<Notifications | null>(null)
  const [error, setError] = useState<string | null>(null)
  const box = useRef<HTMLDivElement>(null)
  const btn = useRef<HTMLButtonElement>(null)
  const close = useCallback(() => setOpen(false), [])
  useDismiss(open, close, box, btn)

  // Reads the existing notifications endpoint only (no AI calls).
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
    if (open) load()
  }, [open, load])

  function openItem(n: AppNotification) {
    setOpen(false)
    if (!n.read) api.readNotification(n.id).then(setData).catch(() => undefined)
    if (n.link) navigate(n.link)
  }

  const unread = data?.unread ?? 0
  return (
    <div className="relative" ref={box}>
      <button
        ref={btn}
        type="button"
        className={`relative flex h-10 w-10 items-center justify-center rounded-full transition-colors ${open ? 'bg-brand-light text-brand-dark' : 'text-muted hover:bg-soft hover:text-ink'}`}
        aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((o) => !o)}
      >
        <Bell className="h-5 w-5" aria-hidden />
        {unread > 0 && (
          <span className="absolute right-1 top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-accent-strong px-1 text-[10px] font-bold text-white ring-2 ring-white" aria-hidden>
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          className="animate-pop fixed inset-x-3 top-[68px] z-40 overflow-hidden rounded-card border border-line bg-white shadow-pop sm:absolute sm:inset-x-auto sm:right-0 sm:top-12 sm:w-[380px] sm:origin-top-right"
        >
          <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
            <p className="text-[15px] font-semibold">
              Notifications {unread > 0 && <span className="ml-1 rounded-full bg-accent-light px-2 py-0.5 text-[11px] font-semibold text-accent-text">{unread} new</span>}
            </p>
            {unread > 0 && (
              <button type="button" className="flex items-center gap-1 rounded px-1 text-[12px] font-semibold text-brand-dark hover:underline" onClick={() => api.readAllNotifications().then(setData).catch(() => undefined)}>
                <CheckCheck className="h-3.5 w-3.5" aria-hidden /> Mark all as read
              </button>
            )}
          </div>
          <div className="max-h-[min(60vh,420px)] overflow-y-auto overscroll-contain">
            {error ? (
              <p className="px-4 py-6 text-[13px] text-bad-text">{error}</p>
            ) : !data ? (
              <ul aria-label="Loading notifications">
                {[0, 1, 2].map((i) => (
                  <li key={i} className="flex gap-3 border-b border-line px-4 py-3 last:border-0">
                    <span className="skeleton h-9 w-9 rounded-full" />
                    <span className="flex-1 space-y-2 py-1">
                      <span className="skeleton block h-3 w-3/4 rounded" />
                      <span className="skeleton block h-3 w-1/2 rounded" />
                    </span>
                  </li>
                ))}
              </ul>
            ) : data.items.length === 0 ? (
              <div className="px-4 py-10 text-center">
                <Bell className="mx-auto h-6 w-6 text-[#B7C0D3]" aria-hidden />
                <p className="mt-2 text-[14px] font-semibold">You&apos;re all caught up</p>
                <p className="text-[13px] text-muted">Grading results and papers that need you will show up here.</p>
              </div>
            ) : (
              <ul>
                {data.items.slice(0, 8).map((n) => (
                  <li key={n.id}>
                    <NotificationRow n={n} onOpen={() => openItem(n)} />
                  </li>
                ))}
              </ul>
            )}
          </div>
          <Link to="/notifications" onClick={() => setOpen(false)} className="flex items-center justify-center gap-1.5 border-t border-line bg-soft px-4 py-3 text-[13px] font-semibold text-brand-dark transition-colors hover:bg-brand-light">
            View all notifications <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          </Link>
        </div>
      )}
    </div>
  )
}

export function NotificationRow({ n, onOpen }: { n: AppNotification; onOpen: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className={`flex w-full gap-3 border-b border-line px-4 py-3 text-left transition-colors last:border-0 hover:bg-rowhover ${n.read ? '' : 'bg-brand-light/50'}`}
    >
      <NotificationIcon kind={n.kind} />
      <span className="min-w-0 flex-1">
        <span className={`block text-[14px] ${n.read ? 'font-medium text-[#3B4260]' : 'font-semibold text-ink'}`}>{n.title}</span>
        {n.body && <span className="mt-0.5 block text-[13px] leading-snug text-muted">{n.body}</span>}
        <span className="mt-1 block text-[11px] text-muted">{timeAgo(n.created_at)}</span>
      </span>
      {!n.read && (
        <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent">
          <span className="sr-only">Unread</span>
        </span>
      )}
    </button>
  )
}
