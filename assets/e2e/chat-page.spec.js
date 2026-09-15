const { test, expect } = require('@playwright/test');

test('Django authenticates the user and mounts the React chat page', async ({ page }) => {
    const username = `e2e_chat_${Date.now()}`;
    const password = 'E2ePassword-48291';
    const sockets = [];
    page.on('websocket', (socket) => sockets.push(socket.url()));

    await page.goto('/accounts/signup/');
    await page.getByLabel(/username/i).fill(username);
    await page.getByLabel(/^password:/i).fill(password);
    await page.getByLabel(/password confirmation/i).fill(password);
    await page.getByRole('button', { name: /sign up/i }).click();

    await expect(page).toHaveURL(/\/accounts\/login\//);
    await page.getByLabel(/username/i).fill(username);
    await page.getByLabel(/password/i).fill(password);
    await page.getByRole('button', { name: /log in/i }).click();

    await expect(page).toHaveURL(/\/chats$/);
    await expect(page.getByRole('heading', { name: 'Chats' })).toBeVisible();
    await expect(page.getByText('No chat selected')).toBeVisible();
    await expect.poll(() => sockets.some((url) => url.endsWith('/ws/notifications/'))).toBe(true);
});
