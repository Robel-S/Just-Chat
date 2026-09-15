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
                'chats': path.resolve(__dirname, './assets/pages/chats.jsx'),
                'friends': path.resolve(__dirname, './assets/pages/friends.jsx'),
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
        warmup: {
            clientFiles: [
                "./assets/pages/chats.jsx",
                "./assets/pages/friends.jsx",
            ],
        },
    },
    test: {
        include: ['assets/tests/**/*.{test,spec}.{js,jsx}'],
        environment: 'jsdom',
        globals: true,
        setupFiles: './assets/tests/setup.js',
        clearMocks: true,
        restoreMocks: true,
    },
});
