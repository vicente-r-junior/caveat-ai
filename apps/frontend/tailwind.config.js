/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#ffffff',
        'bg-soft': '#fafaf9',
        'bg-tint': '#f5f3ee',
        ink: '#18181b',
        'ink-soft': '#3f3f46',
        'ink-muted': '#71717a',
        line: '#e4e4e7',
        'line-soft': '#f4f4f5',
        burgundy: '#7a1f2b',
        'burgundy-soft': '#faf2f3',
        danger: '#b91c1c',
        'danger-soft': '#fef2f2',
        warn: '#c2410c',
        'warn-soft': '#fff7ed',
        safe: '#15803d',
        'safe-soft': '#f0fdf4',
        gold: '#a16207',
      },
      fontFamily: {
        serif: ['Fraunces', 'Georgia', 'serif'],
        sans: ['Geist', '-apple-system', 'sans-serif'],
        mono: ['"Geist Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
};
