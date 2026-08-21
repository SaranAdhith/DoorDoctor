/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // --- Brand palette, sampled from the DoorDoctor logo. Do not change without sign-off. ---
        navy: {
          50: '#eef4f9',
          100: '#d7e5f0',
          200: '#aac6dd',
          300: '#75a1c5',
          400: '#3d72a2',
          500: '#134974',
          600: '#083A5E',
          700: '#013256',
          800: '#002643',
          900: '#001B31',
        },
        brand: {
          50: '#eefaf0',
          100: '#d5f3da',
          200: '#ade6b8',
          300: '#79d48c',
          400: '#4cc466',
          500: '#32B641',
          600: '#249432',
          700: '#1d7529',
          800: '#1a5c24',
          900: '#164c20',
        },
        critical: {
          50: '#fef2f2',
          100: '#fee2e2',
          200: '#fecaca',
          500: '#ef4444',
          600: '#dc2626',
          700: '#b91c1c',
        },
        warning: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
        },

        // --- Semantic tokens layered on top of the brand palette. ---
        // Every foreground below is verified at >= 4.5:1 against the worst-case
        // surface it is used on (surface-sunken, or its own status tint).
        surface: '#f8fafc',
        'surface-raised': '#ffffff',
        'surface-sunken': '#f1f5f9',
        'surface-inverted': '#002643',

        'border-subtle': '#e2e8f0',
        'border-strong': '#cbd5e1',

        'text-primary': '#002643',
        'text-secondary': '#475569',
        // Not slate-400: that measured 3.39:1 on white and fails AA for the
        // caption sizes this token is used at.
        'text-muted': '#5f7186',
        'text-inverted': '#ffffff',

        // Clinical status. Four bands, each with a tint for fills and a border
        // for edges. These carry meaning — never use them decoratively.
        // status-good is brand-700, not brand-500/600: the lighter greens fail
        // AA as text (3.65:1 on their own tint).
        'status-good': '#1d7529',
        'status-good-bg': '#eefaf0',
        'status-good-border': '#ade6b8',
        'status-watch': '#b45309',
        'status-watch-bg': '#fffbeb',
        'status-watch-border': '#fde68a',
        'status-attention': '#c2410c',
        'status-attention-bg': '#fff7ed',
        'status-attention-border': '#fed7aa',
        'status-critical': '#b91c1c',
        'status-critical-bg': '#fef2f2',
        'status-critical-border': '#fecaca',
      },

      // One type scale. Every size is paired with its line-height so vertical
      // rhythm cannot drift screen to screen.
      fontSize: {
        display: ['2rem', { lineHeight: '2.5rem', letterSpacing: '-0.02em' }],
        h1: ['1.5rem', { lineHeight: '2rem', letterSpacing: '-0.015em' }],
        h2: ['1.25rem', { lineHeight: '1.75rem', letterSpacing: '-0.01em' }],
        body: ['0.9375rem', { lineHeight: '1.5rem' }],
        small: ['0.8125rem', { lineHeight: '1.25rem' }],
        caption: ['0.75rem', { lineHeight: '1rem' }],
      },

      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },

      // Exactly two elevations: resting and overlay. Nothing else.
      boxShadow: {
        card: '0 1px 2px rgba(0, 38, 67, 0.05), 0 1px 3px rgba(0, 38, 67, 0.07)',
        raised: '0 4px 12px -2px rgba(0, 38, 67, 0.12), 0 2px 6px -2px rgba(0, 38, 67, 0.08)',
      },

      // One radius family.
      borderRadius: {
        sm: '0.375rem',
        md: '0.5rem',
        lg: '0.75rem',
        xl: '0.875rem',
        '2xl': '1.125rem',
      },

      // Minimum comfortable hit target for touch.
      minHeight: { control: '2.75rem' },
      minWidth: { control: '2.75rem' },

      zIndex: {
        sidebar: '40',
        header: '30',
        overlay: '50',
        toast: '60',
      },

      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'none' },
        },
        'slide-in-right': {
          from: { transform: 'translateX(100%)' },
          to: { transform: 'none' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.97)' },
          to: { opacity: '1', transform: 'none' },
        },
      },
      animation: {
        'fade-in': 'fade-in 180ms ease-out',
        'slide-in-right': 'slide-in-right 220ms cubic-bezier(0.22, 1, 0.36, 1)',
        'scale-in': 'scale-in 160ms ease-out',
      },
    },
  },
  plugins: [],
}
