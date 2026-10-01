import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, CheckCheck } from 'lucide-react'
import { api } from '../lib/api'
import type { AppNotification } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { rovingKeyDown } from '../lib/a11y'
import { AppShell, TopBar } from '../components/layout/AppShell'
import { NotificationRow } from '../components/layout/NotificationBell'
import { Button } from '../components/ui/Button'
import { EmptyState, ErrorState, Loading } from '../components/ui/States'

type Filter = 'all' | 'unread'

/** Full notifications list. Reads the existing notifications endpoints only (no AI calls). */
export default function Notifications() {
  const navigate = useNavigate()
  const data = useAsync(() => api.notifications(), [])
  const [filter, setFilter] = useState<Filter>('all')
  const [marking, setMarking] = useState(false)
  const items = (data.data?.items ?? []).filter((n) => filter === 'all' || !n.read)
  const unread = data.data?.unread ?? 0

  function open(n: AppNotification) {
    if (!n.read) api.readNotification(n.id).then(data.setData).catch(() => undefined)
    if (n.link) navigate(n.link)
  }

  async function markAll() {
    setMarking(true)
    try {
      data.setData(await api.readAllNotifications())
    } finally {
      setMarking(false)
    }
  }

  return (
    <AppShell active="notifications" topbar={<TopBar title="Notifications" subtitle="Grading results and papers that need your review" />}>
      <div className="mx-auto max-w-[760px]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div role="tablist" aria-label="Show" className="inline-flex rounded-full border border-line bg-white p-1 shadow-card" onKeyDown={(e) => rovingKeyDown(e, 'tab')}>
            {(
              [
                ['all', 'All'],
                ['unread', `Unread${unread ? ` (${unread})` : ''}`],
              ] as [Filter, string][]
            ).map(([k, l]) => (
              <button
                key={k}
                type="button"
                role="tab"
                id={`ntab-${k}`}
                aria-selected={filter === k}
                aria-controls="notifications-panel"
                tabIndex={filter === k ? 0 : -1}
                onClick={() => setFilter(k)}
                className={`h-9 rounded-full px-4 text-[14px] transition-colors ${filter === k ? 'bg-brand-strong font-semibold text-white' : 'text-muted hover:text-ink'}`}
              >
                {l}
              </button>
            ))}
          </div>
          <Button variant="secondary" size="sm" icon={<CheckCheck className="h-4 w-4" aria-hidden />} onClick={markAll} loading={marking} disabled={!unread}>
            Mark all as read
          </Button>
        </div>

        <section id="notifications-panel" role="tabpanel" aria-labelledby={`ntab-${filter}`} className="card mt-5 overflow-hidden">
          {data.error ? (
            <ErrorState message={data.error} onRetry={data.reload} />
          ) : !data.data ? (
            <Loading label="Loading notifications…" />
          ) : items.length === 0 ? (
            <EmptyState title={filter === 'unread' ? 'No unread notifications' : "You're all caught up"} icon={<Bell className="h-6 w-6" aria-hidden />}>
              Grading results and papers that need you will show up here.
            </EmptyState>
          ) : (
            <ul>
              {items.map((n) => (
                <li key={n.id}>
                  <NotificationRow n={n} onOpen={() => open(n)} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </AppShell>
  )
}
