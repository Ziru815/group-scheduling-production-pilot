import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const demo = mode === 'demo'
  // Mocks run on the dev server (unless VITE_USE_MOCKS=false) and in the demo
  // build. Normal production builds never include them.
  const mocks = demo || (command === 'serve' && env.VITE_USE_MOCKS !== 'false')

  return {
    plugins: [react()],
    define: {
      __MOCKS_ENABLED__: JSON.stringify(mocks),
      __DEMO__: JSON.stringify(demo),
    },
    // The demo is one self-contained file (see scripts/inline-demo.mjs).
    base: demo ? './' : '/',
    build: demo
      ? { outDir: 'dist-demo', rolldownOptions: { output: { codeSplitting: false } } }
      : undefined,
    server: {
      // When mocks are off (VITE_USE_MOCKS=false), /api goes to the FastAPI backend.
      // While mocks are on, the API client answers /api in-page and never gets here.
      proxy: {
        '/api': {
          target: env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
