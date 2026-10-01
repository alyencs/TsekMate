import type { ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { Search } from 'lucide-react'
import { Sidebar, type NavKey } from './Sidebar'
import { NotificationBell } from './NotificationBell'
import { ProfileMenu } from './ProfileMenu'

export function AppShell({
  active,
  variant = 'default',
  queueBadge,
  topbar,
  children,
  footer,
  contentClassName = 'px-8 py-8',
}: {
  active?: NavKey
  variant?: 'dashboard' | 'default'
  queueBadge?: number
  topbar?: ReactNode
  children: ReactNode
  footer?: ReactNode
  contentClassName?: string
}) {
  const { pathname } = useLocation()
  return (
    <div className="min-h-full">
      <a href="#main" className="sr-only-focusable fixed left-2 top-2 z-50 rounded bg-white px-3 py-2 text-sm font-semibold shadow">
        Skip to content
      </a>
      <Sidebar active={active} variant={variant} queueBadge={queueBadge} />
      <div className="ml-sidebar flex min-h-screen flex-col">
        {topbar && (
          <header className="sticky top-0 z-20 flex h-topbar shrink-0 items-center gap-4 border-b border-line bg-white px-8">{topbar}</header>
        )}
        <main id="main" key={pathname} className={`animate-page flex-1 ${contentClassName} ${footer ? 'pb-28' : ''}`}>
          {children}
        </main>
        {footer && (
          <div className="fixed bottom-0 left-sidebar right-0 z-20 flex h-20 items-center justify-between border-t border-line bg-white px-8">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

/** Standard top bar: title (+ optional subtitle), optional extra controls, search, initials. */
export function TopBar({
  title,
  subtitle,
  search,
  right,
}: {
  title: ReactNode
  subtitle?: ReactNode
  search?: { placeholder: string; value: string; onChange: (v: string) => void }
  right?: ReactNode
}) {
  return (
    <>
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[19px] font-semibold leading-tight">{title}</h1>
        {subtitle && <p className="mt-0.5 text-[11px] text-muted">{subtitle}</p>}
      </div>
      {right}
      {search && <SearchBox {...search} />}
      <TopBarActions />
    </>
  )
}

export function SearchBox({ placeholder, value, onChange, width = 'w-64' }: { placeholder: string; value: string; onChange: (v: string) => void; width?: string }) {
  return (
    <label className={`relative ${width}`}>
      <span className="sr-only">{placeholder}</span>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" aria-hidden />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-9 w-full rounded-ctl border border-line bg-[#F9F7F5] pl-9 pr-3 text-[14px] placeholder:text-gray-400 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
      />
    </label>
  )
}

/** Notifications + account menu, shown on every top bar. */
export function TopBarActions({ full = false }: { full?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <NotificationBell />
      {full && <span className="mx-1 h-8 w-px bg-line" aria-hidden />}
      <ProfileMenu variant={full ? 'full' : 'compact'} />
    </div>
  )
}
