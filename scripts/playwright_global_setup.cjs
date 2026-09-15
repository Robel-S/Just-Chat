const { execFileSync, spawn } = require('node:child_process');
const { rmSync, writeFileSync } = require('node:fs');
const { resolve } = require('node:path');

module.exports = async () => {
    const projectRoot = resolve(__dirname, '..');
    const databasePath = resolve(projectRoot, '.e2e.sqlite3');
    const pidPath = resolve(projectRoot, '.e2e-server.pid');

    rmSync(databasePath, { force: true });
    rmSync(pidPath, { force: true });
    execFileSync(
        resolve(projectRoot, '.venv', 'Scripts', 'python.exe'),
        ['manage.py', 'migrate', '--settings=just_chat.e2e_settings', '--noinput'],
        { cwd: projectRoot, stdio: 'inherit' },
    );

    const server = spawn(
        resolve(projectRoot, '.venv', 'Scripts', 'daphne.exe'),
        ['-b', '127.0.0.1', '-p', '8010', 'just_chat.asgi:application'],
        {
            cwd: projectRoot,
            env: {
                ...process.env,
                DJANGO_SETTINGS_MODULE: 'just_chat.e2e_settings',
            },
            stdio: 'ignore',
            windowsHide: true,
        },
    );
    writeFileSync(pidPath, String(server.pid));

    for (let attempt = 0; attempt < 100; attempt += 1) {
        try {
            const response = await fetch('http://127.0.0.1:8010/accounts/login/');
            if (response.ok) return;
        } catch {
            // The server is still starting.
        }
        await new Promise((resolveWait) => setTimeout(resolveWait, 100));
    }

    throw new Error('The disposable Django E2E server did not start on port 8010.');
};
