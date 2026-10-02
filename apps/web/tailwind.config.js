/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Poppins', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        hand: ['Caveat', 'cursive'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      colors: {
        // Neutrals: cool, light, so the navy + orange brand reads clearly.
        page: '#F6F7FB',
        soft: '#F3F5FA', // soft fields, table headers, inset panels
        rowhover: '#FFF8F3',
        ink: '#161B3D',
        muted: '#5B6478', // 5.9:1 on white
        line: '#E3E7F0',
        // Deep navy: sidebar, headings, wordmark.
        navy: { DEFAULT: '#1B2160', 950: '#0F1338', 900: '#161B4F', 800: '#1B2160', 700: '#262E7A', 600: '#323C96' },
        // Orange: the main brand color. Primary actions, selection, focus, links, active states.
        // `strong` keeps white text at 4.5:1; `dark` is for orange text on white or tinted backgrounds.
        brand: { DEFAULT: '#EA580C', strong: '#D2450C', dark: '#B23A0A', text: '#C2410C', light: '#FFF4EC', tint: '#FDBA74', 100: '#FFEDD5', bright: '#FB8A4C' },
        sky: { DEFAULT: '#3B82F6', light: '#93C5FD' },
        // Blue: the accent. Status highlights, badges, "you're in control" moments, charts.
        accent: { DEFAULT: '#3B82F6', strong: '#2563EB', dark: '#1D4ED8', text: '#1D4ED8', light: '#EFF6FF', tint: '#BFDBFE' },
        ok: { text: '#166534', bg: '#DCFCE7', border: '#86EFAC', bar: '#16A34A' },
        bad: { text: '#991B1B', bg: '#FEE2E2', border: '#FCA5A5', strong: '#DC2626' },
        warn: { text: '#92400E', bg: '#FEF3C7', border: '#FCD34D', bar: '#CA8A04' },
        subject: { math: '#3B82F6', science: '#22C55E', grammar: '#8B5CF6' },
      },
      borderRadius: { card: '14px', ctl: '10px' },
      spacing: { sidebar: '256px', topbar: '64px' },
      boxShadow: {
        card: '0 1px 2px rgba(22, 27, 61, 0.04), 0 1px 3px rgba(22, 27, 61, 0.04)',
        lift: '0 10px 28px -14px rgba(27, 33, 96, 0.28)',
        pop: '0 24px 56px -16px rgba(22, 27, 61, 0.28)',
        cta: '0 6px 16px -6px rgba(210, 69, 12, 0.45)',
      },
      keyframes: {},
    },
  },
  plugins: [],
}
