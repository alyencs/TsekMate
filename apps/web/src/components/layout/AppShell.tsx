import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { Menu, Search, X } from 'lucide-react'
import { Sidebar, type NavKey } from './Sidebar'
import { NotificationBell } from './NotificationBell'
import { ProfileMenu } from './ProfileMenu'
import { LogoMark } from '../ui/Logo'
import { useFocusTrap, useScrollLock } from '../../lib/a11y'

export function AppShell({
  active,
  variant = 'default',
  queueBadge,
  topbar,
  children,
  footer,
  contentClassName = 'px-4 py-6 sm:px-6 lg:px-8 lg:py-8',
}: {
  active?: NavKey
  variant?: 'dashboard' | 'default'
  queueBadge?: number
  topbar?: ReactNode
  children: ReactNode
  footer?: ReactNode
  contentClassName?: string
}) {
  const { pathname, key } = useLocation()
  const [navOpen, setNavOpen] = useState(false)
  const menuBtn = useRef<HTMLButtonElement>(null)
  const close = useCallback(() => setNavOpen(false), [])
  useEffect(() => setNavOpen(false), [key])

  return (
    <div className="min-h-full">
      <a href="#main" className="sr-only-focusable fixed left-2 top-2 z-[70] rounded-ctl bg-white px-3 py-2 text-sm font-semibold shadow-pop">
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-sidebar lg:flex" aria-label="Sidebar">
        <Sidebar active={active} variant={variant} queueBadge={queueBadge} />
      </aside>

      {/* Mobile / tablet drawer */}
      {navOpen && <MobileNav active={active} variant={variant} queueBadge={queueBadge} onClose={close} />}

      <div className="flex min-h-screen flex-col lg:pl-sidebar">
        <header className="sticky top-0 z-30 flex h-topbar shrink-0 items-center gap-2 border-b border-line bg-white px-3 sm:gap-3 sm:px-6 lg:px-8">
          <button
            ref={menuBtn}
            type="button"
            onClick={() => setNavOpen(true)}
            className="-ml-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-ctl text-navy transition-colors hover:bg-soft lg:hidden"
            aria-label="Open menu"
            aria-expanded={navOpen}
            aria-controls="mobile-nav"
          >
            <Menu className="h-5 w-5" aria-hidden />
          </button>
          {topbar ?? (
            <>
              <span className="flex min-w-0 flex-1 items-center gap-2 lg:hidden">
                <LogoMark size={28} />
                <span className="text-[17px] font-bold">
                  <span className="text-navy">Tsek</span>
                  <span className="text-accent">Mate</span>
                </span>
              </span>
              <span className="hidden flex-1 lg:block" />
              <TopBarActions />
            </>
          )}
        </header>
        <main id="main" tabIndex={-1} key={pathname} className={`animate-page min-w-0 flex-1 focus:outline-none ${contentClassName} ${footer ? 'pb-32' : ''}`}>
          {children}
        </main>
        {footer && (
          <div className="safe-bottom fixed bottom-0 left-0 right-0 z-20 flex min-h-[72px] items-center justify-between gap-3 border-t border-line bg-white/95 px-4 pt-3 shadow-[0_-8px_24px_-16px_rgba(22,27,61,0.25)] sm:px-6 lg:left-sidebar lg:px-8">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

function MobileNav({ onClose, ...rest }: { active?: NavKey; variant: 'dashboard' | 'default'; queueBadge?: number; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null)
  useFocusTrap(ref, true, onClose)
  useScrollLock(true)
  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <div className="animate-fade absolute inset-0 bg-navy-950/55" onClick={onClose} aria-hidden />
      <div ref={ref} id="mobile-nav" role="dialog" aria-modal="true" aria-label="Main menu" className="animate-drawer absolute inset-y-0 left-0 w-[min(86vw,300px)] shadow-pop">
        <Sidebar {...rest} onClose={onClose} />
      </div>
    </div>
  )
}

/** Standard top bar: title (+ optional subtitle), optional extra controls, search, notifications and account. */
export function TopBar({
  title,
  subtitle,
  search,
  right,
  fullActions = false,
}: {
  title: ReactNode
  subtitle?: ReactNode
  search?: { placeholder: string; value: string; onChange: (v: string) => void }
  right?: ReactNode
  fullActions?: boolean
}) {
  const [searchOpen, setSearchOpen] = useState(false)
  return (
    <>
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[16px] font-semibold leading-tight text-ink sm:text-[18px]">{title}</h1>
        {subtitle && <p className="mt-0.5 hidden truncate text-[12px] text-muted sm:block">{subtitle}</p>}
      </div>
      {right}
      {search && (
        <>
          <div className="hidden md:block">
            <SearchBox {...search} />
          </div>
          <button
            type="button"
            className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-soft hover:text-ink md:hidden"
            aria-label={search.placeholder.replace(/\.+$/, '')}
            aria-expanded={searchOpen}
            onClick={() => setSearchOpen(true)}
          >
            <Search className="h-5 w-5" aria-hidden />
            {search.value && <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-accent" aria-hidden />}
          </button>
          {searchOpen && (
            <div className="animate-fade absolute inset-0 z-10 flex items-center gap-2 bg-white px-3 sm:px-6 md:hidden">
              <SearchBox {...search} width="flex-1" autoFocus onEscape={() => setSearchOpen(false)} />
              <button type="button" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-muted hover:bg-soft hover:text-ink" aria-label="Close search" onClick={() => setSearchOpen(false)}>
                <X className="h-5 w-5" aria-hidden />
              </button>
            </div>
          )}
        </>
      )}
      <TopBarActions full={fullActions} />
    </>
  )
}

export function SearchBox({
  placeholder,
  value,
  onChange,
  width = 'w-56 xl:w-64',
  autoFocus,
  onEscape,
}: {
  placeholder: string
  value: string
  onChange: (v: string) => void
  width?: string
  autoFocus?: boolean
  onEscape?: () => void
}) {
  return (
    <label className={`relative block ${width}`}>
      <span className="sr-only">{placeholder}</span>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8790A6]" aria-hidden />
      <input
        type="search"
        value={value}
        autoFocus={autoFocus}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => e.key === 'Escape' && onEscape?.()}
        placeholder={placeholder}
        className="h-10 w-full rounded-full border border-line bg-soft pl-9 pr-4 text-[14px] transition-[border-color,box-shadow,background-color] placeholder:text-[#8790A6] focus:border-brand focus:bg-white focus:outline-none focus:ring-4 focus:ring-brand/15"
      />
    </label>
  )
}

/** Notifications + account menu, shown on every top bar. */
export function TopBarActions({ full = false }: { full?: boolean }) {
  return (
    <div className="flex shrink-0 items-center gap-1 sm:gap-2">
      <NotificationBell />
      {full && <span className="mx-1 hidden h-8 w-px bg-line md:block" aria-hidden />}
      <ProfileMenu variant={full ? 'full' : 'compact'} />
    </div>
  )
}
