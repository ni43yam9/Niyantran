/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Sage Serenity (Light) & Forest Glass (Dark) Palettes
        sage: {
          bg: '#E4EEE7',
          gradient1: '#C9DFD1',
          gradient2: '#DDE9E0',
          primary: '#568B75',
          'primary-hover': '#467360',
          accent: '#A3C9A8',
          text: '#243C32',
          muted: '#718579',
          card: 'rgba(255, 255, 255, 0.52)',
          border: 'rgba(255, 255, 255, 0.70)',
        },
        forest: {
          bg: '#101C18',
          gradient1: '#1C3930',
          gradient2: '#172B25',
          primary: '#75B798',
          'primary-hover': '#86c4a6',
          accent: '#A3D9B1',
          text: '#E8F3EC',
          muted: '#9BB3A5',
          card: 'rgba(255, 255, 255, 0.065)',
          border: 'rgba(255, 255, 255, 0.12)',
        },
        // Shared Semantic Colors
        semantic: {
          completed: {
            light: '#568B75',
            dark: '#75B798',
          },
          high: {
            light: '#DC6B6B',
            dark: '#F08080',
          },
          medium: {
            light: '#D69A50',
            dark: '#E8B76C',
          },
          low: {
            light: '#7295B5',
            dark: '#82B4D8',
          },
          success: {
            light: '#4D9673',
            dark: '#75C69A',
          },
          warning: {
            light: '#C58A42',
            dark: '#E8B76C',
          },
        },
        // Remap brand and indigo to the exact Sage Serenity / Forest spectrum
        brand: {
          50: '#F0F6F2',
          100: '#E4EEE7',
          200: '#C9DFD1',
          300: '#A3C9A8',
          400: '#75B798',
          500: '#568B75',
          600: '#467360',
          700: '#385C4D',
          800: '#2C473C',
          900: '#243C32',
          950: '#101C18',
        },
        indigo: {
          50: '#F2F7F4',
          100: '#E4EEE7',
          200: '#C9DFD1',
          300: '#A3C9A8',
          400: '#75B798',
          500: '#568B75',
          600: '#487663',
          700: '#3B6051',
          800: '#2F4D40',
          900: '#243C32',
          950: '#101C18',
        },
        // Harmonize slate to Sage Serenity (light) and Forest Glass (dark) tones
        slate: {
          50: '#E4EEE7',
          100: '#DCE8E0',
          200: '#CBDCD1',
          300: '#B8CFC2',
          400: '#9BB3A5',
          500: '#718579',
          600: '#536A5E',
          700: '#384E43',
          800: '#1E352C',
          900: '#243C32',
          950: '#101C18',
        },
        dark: {
          bg: '#101C18',
          surface: '#152520',
          card: 'rgba(255, 255, 255, 0.065)',
          border: 'rgba(255, 255, 255, 0.12)',
          muted: '#9BB3A5',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
        sora: ['Sora', 'Inter', 'sans-serif'],
      },
      boxShadow: {
        'subtle': '0 1px 2px 0 rgba(36, 60, 50, 0.04)',
        'glass': '0 8px 32px 0 rgba(36, 60, 50, 0.06), 0 2px 8px 0 rgba(36, 60, 50, 0.04)',
        'glass-hover': '0 12px 40px 0 rgba(36, 60, 50, 0.1), 0 4px 12px 0 rgba(36, 60, 50, 0.06)',
        'glass-dark': '0 8px 32px 0 rgba(0, 0, 0, 0.4), 0 2px 8px 0 rgba(0, 0, 0, 0.3)',
        'glass-dark-hover': '0 12px 40px 0 rgba(0, 0, 0, 0.55), 0 4px 12px 0 rgba(0, 0, 0, 0.4)',
        'card': '0 4px 20px -2px rgba(36, 60, 50, 0.05)',
        'card-hover': '0 12px 28px -4px rgba(36, 60, 50, 0.09)',
        'modal': '0 24px 60px 0 rgba(36, 60, 50, 0.18)',
      },
      backdropBlur: {
        'glass': '20px',
        'glass-lg': '24px',
      }
    },
  },
  plugins: [],
}
