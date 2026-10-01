export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <span
      className="inline-flex items-center justify-center rounded-[8px] bg-brand text-white"
      style={{ width: size, height: size }}
      aria-hidden
    >
      <svg viewBox="0 0 24 24" width={size * 0.5} height={size * 0.5} fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="4" y="4" width="16" height="16" rx="2" />
        <path d="M8.5 15.5l3-3 2 2 2.5-3" />
      </svg>
    </span>
  )
}

export function Logo() {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark />
      <span className="text-[19px] font-bold tracking-tight">
        <span className="text-ink">Tsek</span>
        <span className="text-brand">Mate</span>
      </span>
    </span>
  )
}

export function Avatar({ size = 32 }: { size?: number }) {
  // Illustrated placeholder avatar (no real photo of a person).
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden className="shrink-0 rounded-full">
      <circle cx="20" cy="20" r="20" fill="#E7D3C4" />
      <path d="M8 34c1-9 6-13 12-13s11 4 12 13" fill="#7C4A2D" />
      <path d="M10 22c-1-10 4-15 10-15s11 5 10 15c-1 4-3 7-5 8H15c-2-1-4-4-5-8z" fill="#4A2B1A" />
      <circle cx="20" cy="18" r="7" fill="#F2C9A8" />
      <path d="M12.5 16c1-5 5-7 8-7s6 2 7 6c-3-1-6-3-8-5-1 3-4 5-7 6z" fill="#4A2B1A" />
      <path d="M11 40c1-6 4-9 9-9s8 3 9 9z" fill="#FAF8F6" />
    </svg>
  )
}
