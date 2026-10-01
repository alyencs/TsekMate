import type { ReactNode } from 'react'
import { AlertTriangle, Inbox, Loader2 } from 'lucide-react'
import { Button } from './Button'

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="animate-fade flex items-center justify-center gap-3 py-20 text-muted">
      <Loader2 className="h-5 w-5 animate-spin text-brand" aria-hidden />
      <span className="text-[15px]">{label}</span>
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="card mx-auto my-10 flex max-w-lg flex-col items-center gap-3 p-8 text-center">
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

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="animate-fade flex flex-col items-center gap-2 px-6 py-14 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-light text-brand">
        <Inbox className="h-6 w-6" aria-hidden />
      </span>
      <h3 className="text-[16px] font-semibold">{title}</h3>
      {children && <p className="max-w-md text-[14px] text-muted">{children}</p>}
      {action}
    </div>
  )
}
