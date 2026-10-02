export function Toggle({
  checked,
  onChange,
  label,
  description,
  id,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
  description?: string
  id: string
}) {
  return (
    <div className="flex items-start justify-between gap-4 sm:items-center sm:gap-6">
      <div className="min-w-0">
        <label htmlFor={id} className="text-[15px] font-semibold text-ink">
          {label}
        </label>
        {description && (
          <p id={`${id}-desc`} className="mt-0.5 text-[13px] text-muted">
            {description}
          </p>
        )}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-describedby={description ? `${id}-desc` : undefined}
        onClick={() => onChange(!checked)}
        className={`relative mt-0.5 h-7 w-12 shrink-0 rounded-full transition-colors duration-200 sm:mt-0 ${checked ? 'bg-brand' : 'bg-[#CBD2E1] hover:bg-[#B7C0D3]'}`}
      >
        <span className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition-all duration-200 ${checked ? 'left-[22px]' : 'left-0.5'}`} />
      </button>
    </div>
  )
}
