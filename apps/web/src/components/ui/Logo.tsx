export const TAGLINE = 'Grade less. Know more.'

/** TsekMate mark: the logo image from apps/web/public/logo-mark.png. */
   export function LogoMark({ size = 36, tile = false, className = '' }: { size?: number; tile?: boolean; className?: string }) {
     const img = <img src="/logo-mark.png" alt="" width={tile ? size * 0.74 : size} height={tile ? size * 0.74 : size} className="object-contain" draggable={false} />
     if (!tile)
       return (
         <span className={`inline-flex shrink-0 ${className}`} aria-hidden>
           {img}
         </span>
       )
     return (
       <span className={`inline-flex shrink-0 items-center justify-center rounded-[28%] bg-white shadow-[0_1px_2px_rgba(15,19,56,0.12)] ${className}`} style={{ width: size, height: size }} aria-hidden>
         {img}
       </span>
     )
}

/** Mark + wordmark ("Tsek" navy, "Mate" orange), optionally with the tagline. `tone="light"` for dark backgrounds. */
export function Logo({
  size = 36,
  tagline = false,
  tone = 'dark',
  tile,
  className = '',
}: {
  size?: number
  tagline?: boolean
  tone?: 'dark' | 'light'
  tile?: boolean
  className?: string
}) {
  const light = tone === 'light'
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <LogoMark size={size} tile={tile ?? light} />
      <span className="flex flex-col leading-none">
        <span className="font-bold tracking-tight" style={{ fontSize: Math.round(size * 0.6) }}>
          <span className={light ? 'text-white' : 'text-navy'}>Tsek</span>
          <span className="text-accent">Mate</span>
        </span>
        {tagline && (
          <span className={`mt-1 font-medium ${light ? 'text-[#C7D2FE]' : 'text-navy-700'}`} style={{ fontSize: Math.max(11, Math.round(size * 0.3)) }}>
            {TAGLINE}
          </span>
        )}
      </span>
    </span>
  )
}

export function Avatar({ size = 32, initials }: { size?: number; initials?: string }) {
  if (initials)
    return (
      <span
        className="inline-flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand to-navy-700 font-semibold text-white"
        style={{ width: size, height: size, fontSize: Math.round(size * 0.38) }}
        aria-hidden
      >
        {initials}
      </span>
    )
  // Illustrated placeholder avatar (no real photo of a person).
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden className="shrink-0 rounded-full">
      <circle cx="20" cy="20" r="20" fill="#E0E7FF" />
      <path d="M8 34c1-9 6-13 12-13s11 4 12 13" fill="#4338CA" />
      <path d="M10 22c-1-10 4-15 10-15s11 5 10 15c-1 4-3 7-5 8H15c-2-1-4-4-5-8z" fill="#3B2A22" />
      <circle cx="20" cy="18" r="7" fill="#F2C9A8" />
      <path d="M12.5 16c1-5 5-7 8-7s6 2 7 6c-3-1-6-3-8-5-1 3-4 5-7 6z" fill="#3B2A22" />
      <path d="M11 40c1-6 4-9 9-9s8 3 9 9z" fill="#F6F7FB" />
    </svg>
  )
}

export function initialsOf(name: string) {
  const parts = name.replace(/^(Prof|Dr|Ms|Mr|Mrs)\.?\s+/i, '').split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '') + (parts[parts.length - 1]?.[0] ?? '')).toUpperCase() || 'T'
}
