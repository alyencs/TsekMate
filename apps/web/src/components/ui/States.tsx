import type { ReactNode } from 'react'
import { AlertTriangle, Inbox } from 'lucide-react'
import { Button } from './Button'
import { LogoMark } from './Logo'

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="animate-fade flex flex-col items-center justify-center gap-3 py-16 text-muted sm:py-20">
      <span className="relative flex h-12 w-12 items-center justify-center">
        <span className="absolute inset-0 animate-spin rounded-full border-[3px] border-brand-light border-t-brand" aria-hidden />
        <LogoMark size={24} />
      </span>
      <span className="text-[14px] font-medium">{label}</span>
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="card animate-fade mx-auto my-8 flex max-w-lg flex-col items-center gap-3 px-6 py-8 text-center sm:p-8">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-bad-bg text-bad-text">
        <AlertTriangle className="h-6 w-6" aria-hidden />
      </span>
      <h2 className="text-lg font-semibold">Something went wrong</h2>
      <p className="text-[14px] text-muted">{message}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

export function EmptyState({ title, children, action, icon }: { title: string; children?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="animate-fade flex flex-col items-center gap-2 px-6 py-14 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-light text-brand">{icon ?? <Inbox className="h-6 w-6" aria-hidden />}</span>
      <h3 className="text-[16px] font-semibold">{title}</h3>
      {children && <p className="max-w-md text-[14px] text-muted">{children}</p>}
      {action}
    </div>
  )
}

/** Inline status/error banner. */
export function Notice({ tone, children, className = '' }: { tone: 'ok' | 'bad' | 'info'; children: ReactNode; className?: string }) {
  return (
    <p role={tone === 'bad' ? 'alert' : 'status'} className={`notice animate-fade notice-${tone} ${className}`}>
      {children}
    </p>
  )
}
