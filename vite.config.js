import { defineConfig } from 'vite';
import path from 'path';
import react from '@vitejs/plugin-react';

export default defineConfig({
    plugins: [react()],
    base: '/static', // This should match Django's settings.STATIC_URL
    build: {
        // Where Vite will save its output files.
        // This should be something in your settings.STATICFILES_DIRS
        outDir: path.resolve(__dirname, './static'),
        emptyOutDir: false, // Preserve the outDir to not clobber Django's other files.
        manifest: "manifest.json",
        rollupOptions: {
            input: {
                'index': path.resolve(__dirname, './assets/index.js'),
                'hello': path.resolve(__dirname, './assets/chats.jsx'),
            },
            output: {
                // Output JS bundles to js/ directory with -bundle suffix
                entryFileNames: `js/[name]-bundle.js`,
            },
        },
    },
    server: {
        host: '0.0.0.0',
        port: 5173,
        watch: {
            usePolling: true,
        },
    },
});
