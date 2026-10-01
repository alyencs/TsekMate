import { UserRoundX } from 'lucide-react'

/** Teacher-facing student identity: the name, with the student ID (the stable identifier) beside or under it. */
export function StudentLabel({ id, name, size = 'md', inline = false }: { id: string | null | undefined; name: string | null | undefined; size?: 'sm' | 'md' | 'lg'; inline?: boolean }) {
  if (!id)
    return (
      <span className={`inline-flex items-center gap-1.5 font-semibold text-warn-text ${size === 'lg' ? 'text-[17px]' : 'text-[14px]'}`}>
        <UserRoundX className="h-4 w-4" aria-hidden />
        Not identified
      </span>
    )
  const nameCls = size === 'lg' ? 'text-[18px] font-bold' : size === 'sm' ? 'text-[13px] font-semibold' : 'text-[15px] font-semibold'
  return (
    <span className={inline ? 'inline-flex items-baseline gap-2' : 'flex flex-col leading-tight'}>
      <span className={`${nameCls} text-ink`}>{name || id}</span>
      {name && <span className="text-[12px] tabular-nums text-muted">{id}</span>}
    </span>
  )
}
