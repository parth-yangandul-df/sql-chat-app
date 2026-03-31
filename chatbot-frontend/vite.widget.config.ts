import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import cssInjectedByJs from 'vite-plugin-css-injected-by-js'
import path from 'path'

// Widget build — produces a single self-contained IIFE:
//   dist-widget/querywise-chat.js  (CSS inlined, no external deps)
//
// Angular integration:
//   <script src="https://your-host/querywise-chat.js"></script>
//   <querywise-chat connection-id="your-uuid"></querywise-chat>
export default defineConfig({
  plugins: [react(), cssInjectedByJs()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  define: {
    // Ensure React doesn't try to use process.env in the IIFE bundle
    'process.env.NODE_ENV': JSON.stringify('production'),
  },
  build: {
    lib: {
      entry: path.resolve(__dirname, 'src/widget.tsx'),
      name: 'QueryWiseChat',
      formats: ['iife'],
      fileName: () => 'querywise-chat.js',
    },
    // Inline all CSS into the JS bundle — Angular just needs one <script> tag
    cssCodeSplit: false,
    outDir: 'dist-widget',
    emptyOutDir: true,
    rollupOptions: {
      // Bundle everything — Angular doesn't have React loaded
      external: [],
      output: {
        // Inline dynamic imports so the output is truly a single file
        inlineDynamicImports: true,
      },
    },
  },
})
