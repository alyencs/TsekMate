import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { Loader2 } from 'lucide-react'

type Variant = 'primary' | 'dark' | 'secondary' | 'ghost' | 'link' | 'soft'
type Size = 'sm' | 'md' | 'lg'

const variants: Record<Variant, string> = {
  // Orange = the call to action. `accent-strong` keeps white text at 4.5:1.
  primary: 'bg-accent-strong text-white shadow-cta hover:bg-accent-dark hover:shadow-[0_8px_20px_-8px_rgba(210,69,12,0.55)] disabled:bg-[#E9A27F] disabled:shadow-none',
  dark: 'bg-navy text-white shadow-sm hover:bg-navy-700 disabled:bg-navy/40',
  secondary: 'bg-white text-ink border border-line shadow-card hover:border-[#CBD2E1] hover:bg-soft disabled:text-muted disabled:bg-soft',
  ghost: 'text-muted hover:bg-soft hover:text-ink',
  link: 'text-brand-dark underline-offset-4 hover:underline px-0 h-auto',
  soft: 'bg-white text-brand-dark border border-brand-tint shadow-sm hover:bg-brand-light',
}
const sizes: Record<Size, string> = {
  sm: 'h-9 px-3.5 text-[13px] rounded-ctl',
  md: 'h-10 px-4 text-[14px] rounded-ctl',
  lg: 'h-12 px-6 text-[15px] rounded-[12px]',
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  icon?: ReactNode
  iconRight?: ReactNode
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button({
  variant = 'primary',
  size = 'md',
  loading,
  icon,
  iconRight,
  className = '',
  children,
  disabled,
  type = 'button',
  ...rest
}, ref) {
  return (
    <button
      ref={ref}
      type={type}
      className={`inline-flex items-center justify-center gap-2 whitespace-nowrap font-semibold transition-[background-color,color,border-color,box-shadow,transform] duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:active:scale-100 ${
        variant === 'link' ? 'text-[14px]' : sizes[size]
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
})
