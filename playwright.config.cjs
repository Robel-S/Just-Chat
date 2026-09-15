const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
    testDir: './assets/e2e',
    globalSetup: require.resolve('./scripts/playwright_global_setup.cjs'),
    globalTeardown: require.resolve('./scripts/playwright_global_teardown.cjs'),
    timeout: 30_000,
    retries: 0,
    use: {
        baseURL: 'http://127.0.0.1:8010',
        trace: 'retain-on-failure',
    },
    webServer: [
        {
            command: 'npm run dev -- --host 127.0.0.1',
            url: 'http://127.0.0.1:5173/static/@vite/client',
            reuseExistingServer: true,
            timeout: 120_000,
        },
    ],
    projects: [
        {
            name: 'chromium',
            use: { browserName: 'chromium' },
        },
    ],
});
