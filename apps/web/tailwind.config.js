/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        hand: ['Caveat', 'cursive'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      colors: {
        page: '#FAF8F6',
        ink: '#1F2937',
        muted: '#6B7280',
        line: '#E5E7EB',
        brand: { DEFAULT: '#F97316', dark: '#EA580C', light: '#FFF1E6', tint: '#FDBA74' },
        ok: { text: '#166534', bg: '#DCFCE7', border: '#86EFAC', bar: '#16A34A' },
        bad: { text: '#991B1B', bg: '#FEE2E2', border: '#FCA5A5', strong: '#DC2626' },
        warn: { text: '#92400E', bg: '#FEF3C7', border: '#FCD34D', bar: '#CA8A04' },
        subject: { math: '#3B82F6', science: '#22C55E', grammar: '#8B5CF6' },
      },
      borderRadius: { card: '12px', ctl: '8px' },
      spacing: { sidebar: '240px', topbar: '64px' },
      boxShadow: { card: '0 1px 2px rgba(16,24,40,0.04)', pop: '0 20px 50px -12px rgba(16,24,40,0.18)' },
    },
  },
  plugins: [],
}
