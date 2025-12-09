/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bank-blue': {
          50: '#e3eaf7',
          100: '#c5d4ef',
          200: '#a3bde5',
          300: '#7da5db',
          400: '#5b8fd3',
          500: '#3d7acb',
          600: '#356db8',
          700: '#2b5da3',
          800: '#224d8f',
          900: '#003366',
        }
      }
    },
  },
  plugins: [],
}

