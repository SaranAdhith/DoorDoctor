/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Sampled from the DoorDoctor logo.
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
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(0, 38, 67, 0.06), 0 8px 24px -12px rgba(0, 38, 67, 0.18)',
        lifted: '0 2px 4px rgba(0, 38, 67, 0.06), 0 16px 40px -16px rgba(0, 38, 67, 0.28)',
      },
      borderRadius: {
        xl: '0.875rem',
        '2xl': '1.125rem',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'none' },
        },
      },
      animation: {
        'fade-in': 'fade-in 180ms ease-out',
      },
    },
  },
  plugins: [],
}
