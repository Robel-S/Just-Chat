const { execFileSync } = require('node:child_process');
const { existsSync, readFileSync, rmSync } = require('node:fs');
const { resolve } = require('node:path');

module.exports = async () => {
    const projectRoot = resolve(__dirname, '..');
    const pidPath = resolve(projectRoot, '.e2e-server.pid');

    if (existsSync(pidPath)) {
        const pid = readFileSync(pidPath, 'utf8').trim();
        try {
            execFileSync('taskkill.exe', ['/pid', pid, '/T', '/F'], { stdio: 'ignore' });
        } catch {
            // The server may already have stopped after a test failure.
        }
    }

    rmSync(pidPath, { force: true });
    rmSync(resolve(projectRoot, '.e2e.sqlite3'), { force: true });
};
