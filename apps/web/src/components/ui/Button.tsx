import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Loader2 } from 'lucide-react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'link' | 'soft'
type Size = 'sm' | 'md' | 'lg'

const variants: Record<Variant, string> = {
  primary: 'bg-brand text-white hover:bg-brand-dark shadow-sm disabled:bg-brand/50',
  secondary: 'bg-white text-ink border border-line hover:bg-gray-50 disabled:text-muted',
  ghost: 'text-muted hover:bg-gray-100 hover:text-ink',
  link: 'text-brand-dark hover:underline px-0 h-auto',
  soft: 'bg-white text-brand-dark border border-white hover:border-brand-tint shadow-sm',
}
const sizes: Record<Size, string> = {
  sm: 'h-8 px-3 text-[13px] rounded-ctl',
  md: 'h-10 px-4 text-[15px] rounded-ctl',
  lg: 'h-14 px-6 text-[17px] rounded-[10px]',
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  icon?: ReactNode
  iconRight?: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading,
  icon,
  iconRight,
  className = '',
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 whitespace-nowrap font-semibold transition-[background-color,color,border-color,transform] duration-150 active:scale-[0.98] disabled:active:scale-100 disabled:cursor-not-allowed ${
        variant === 'link' ? '' : sizes[size]
      } ${variants[variant]} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : icon}
      {children}
      {iconRight}
    </button>
  )
}
