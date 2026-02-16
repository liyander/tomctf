/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./assets/**/*.{js,ts,jsx,tsx,vue,scss}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // TomCTF Brand Colors - Dark Red Cyberpunk palette
        wmctf: {
          primary: '#ec1313',    // TomCTF Red
          secondary: '#8b0000',  // Dark Red
          accent: '#ff4444',     // Bright Red
          success: '#34C759',    // Green
          warning: '#FF9500',    // Orange
          danger: '#FF3B30',     // Red
        },
        // Dark mode colors
        dark: {
          bg: '#050303',
          surface: '#1a0a0a',
          card: '#1a0a0a',
          border: '#8b0000',
          text: '#FFFFFF',
          muted: '#8E8E93',
        },
        // Light mode colors (forced dark)
        light: {
          bg: '#050303',
          surface: '#1a0a0a',
          card: '#1a0a0a',
          border: '#8b0000',
          text: '#FFFFFF',
          muted: '#8E8E93',
        }
      },
      fontFamily: {
        'sf-pro': ['-apple-system', 'SF Pro Display', 'system-ui', 'sans-serif'],
        'inter': ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'xs': ['0.75rem', { lineHeight: '1rem' }],
        'sm': ['0.875rem', { lineHeight: '1.25rem' }],
        'base': ['1rem', { lineHeight: '1.5rem' }],
        'lg': ['1.125rem', { lineHeight: '1.75rem' }],
        'xl': ['1.25rem', { lineHeight: '1.75rem' }],
        '2xl': ['1.5rem', { lineHeight: '2rem' }],
        '3xl': ['1.875rem', { lineHeight: '2.25rem' }],
        '4xl': ['2.25rem', { lineHeight: '2.5rem' }],
        '5xl': ['3rem', { lineHeight: '1' }],
        '6xl': ['3.75rem', { lineHeight: '1' }],
        '7xl': ['4.5rem', { lineHeight: '1' }],
        '8xl': ['6rem', { lineHeight: '1' }],
        '9xl': ['8rem', { lineHeight: '1' }],
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
        '128': '32rem',
      },
      borderRadius: {
        'xl': '0.75rem',
        '2xl': '1rem',
        '3xl': '1.5rem',
        '4xl': '2rem',
      },
      boxShadow: {
        'apple': '0 4px 16px rgba(0, 0, 0, 0.3)',
        'apple-lg': '0 8px 32px rgba(0, 0, 0, 0.4)',
        'apple-xl': '0 12px 48px rgba(0, 0, 0, 0.5)',
        'glow': '0 0 20px rgba(236, 19, 19, 0.3)',
        'glow-red': '0 0 20px rgba(139, 0, 0, 0.4)',
      },
      backdropBlur: {
        'apple': '20px',
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
        'bounce-gentle': 'bounceGentle 2s infinite',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        scaleIn: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        bounceGentle: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-5px)' },
        },
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 20px rgba(236, 19, 19, 0.3)' },
          '50%': { boxShadow: '0 0 40px rgba(236, 19, 19, 0.6)' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
    require('@tailwindcss/aspect-ratio'),
  ],
}
