/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        display: ["Outfit", "sans-serif"],
      },
      colors: {
        cyber: {
          slate: "#0b0f19",
          slateLight: "#161d30",
          blue: "#3b82f6",
          emerald: "#10b981",
          amber: "#f59e0b",
          red: "#ef4444",
          violet: "#8b5cf6",
          teal: "#14b8a6",
        }
      },
      boxShadow: {
        cyberGlow: "0 0 15px rgba(59, 130, 246, 0.5)",
        redGlow: "0 0 15px rgba(239, 68, 68, 0.6)",
        emeraldGlow: "0 0 15px rgba(16, 185, 129, 0.5)",
        glass: "0 8px 32px 0 rgba(0, 0, 0, 0.37)",
      },
      animation: {
        pulseFast: "pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        scanline: "scan 6s linear infinite",
      },
      keyframes: {
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" }
        }
      }
    },
  },
  plugins: [],
}
