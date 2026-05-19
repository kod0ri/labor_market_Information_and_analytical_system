/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#fff5ed',
          100: '#ffe7d1',
          200: '#ffc89c',
          300: '#ffa05e',
          400: '#ff7a36',
          500: '#f95514',
          DEFAULT: '#f95514',
          600: '#e23d08',
          700: '#bb2c09',
          800: '#94250f',
          900: '#791f10',
        },
        accent: {
          400: '#22d3ee',
          500: '#06b6d4',
          600: '#0891b2',
        },
        surface: {
          DEFAULT: '#0b0d12',
          card: '#11141b',
          border: '#1c2230',
          muted: '#9aa3b2',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(249,85,20,0.35), 0 8px 32px -8px rgba(249,85,20,0.35)',
      },
    },
  },
  plugins: [],
}
