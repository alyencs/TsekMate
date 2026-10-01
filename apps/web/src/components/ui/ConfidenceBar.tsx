import { pct } from '../../lib/format'
import { useThreshold } from '../../lib/appSettings'

/** Green at or above the confidence threshold (Settings, default 75 %), amber below. Text label always shown. */
export function ConfidenceBar({ value, width = 'w-20' }: { value: number; width?: string }) {
  const threshold = useThreshold()
  const high = value >= threshold
  const t = Math.round(threshold * 100)
  return (
    <span className="inline-flex items-center gap-2" title={high ? `Confidence at or above ${t}%` : `Low confidence, below ${t}%`}>
      <span
        className={`relative h-1.5 ${width} overflow-hidden rounded-full bg-gray-200`}
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(value * 100)}
        aria-label="AI confidence"
      >
        <span
          className={`absolute inset-y-0 left-0 rounded-full transition-[width,background-color] duration-500 ${high ? 'bg-ok-bar' : 'bg-warn-bar'}`}
          style={{ width: `${Math.max(2, Math.min(100, value * 100))}%` }}
        />
      </span>
      <span className={`text-[11px] font-semibold ${high ? 'text-ok-bar' : 'text-warn-bar'}`}>{pct(value)}</span>
    </span>
  )
}
