import type { Config } from 'tailwindcss'

export default {
  content: [
    './components/**/*.{vue,js,ts}',
    './layouts/**/*.vue',
    './pages/**/*.vue',
    './app.vue',
  ],
  theme: {
    extend: {
      colors: {
        panel: '#111111',
        surface: '#1a1a1a',
        border: '#2a2a2a',
        accent: {
          DEFAULT: '#7c3aed',
          hover: '#6d28d9',
          muted: 'rgba(124,58,237,0.15)',
        },
        status: {
          done: '#10b981',
          active: '#3b82f6',
          failed: '#ef4444',
          pending: '#6b7280',
          warning: '#f59e0b',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      animation: {
        'spin-slow': 'spin 2s linear infinite',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
      },
    },
  },
  plugins: [],
} satisfies Config
