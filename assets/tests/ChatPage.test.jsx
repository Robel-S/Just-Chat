import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ChatPage } from '../pages/chats.jsx';
import { MockWebSocket } from './MockWebSocket.js';

const chats = [
    { id: 1, owner: 1, name: 'General', image: '/general.png', unread_count: 0 },
    { id: 2, owner: 2, name: 'Project', image: '/project.png', unread_count: 2 },
];

function jsonResponse(data, ok = true) {
    return Promise.resolve({ ok, status: ok ? 200 : 500, json: async () => data });
}

describe('ChatPage', () => {
    beforeEach(() => {
        MockWebSocket.reset();
        global.WebSocket = MockWebSocket;
        document.cookie = 'csrftoken=test-token';
        global.fetch = vi.fn((url) => {
            const path = String(url);
            if (path.endsWith('/api/me')) return jsonResponse({ id: 1, username: 'alice' });
            if (path.endsWith('/api/chats')) return jsonResponse(chats);
            if (path.includes('/api/1/messages')) return jsonResponse([]);
            if (path.includes('/api/2/messages')) return jsonResponse([]);
            if (path.includes('/read/')) return jsonResponse({ unread_count: 0 });
            if (path.includes('/api/members/')) return jsonResponse([]);
            throw new Error(`Unexpected request: ${path}`);
        });
    });

    it('loads chats, initial unread counts, and one notification socket', async () => {
        render(<ChatPage />);

        expect(await screen.findByText('Project')).toBeInTheDocument();
        expect(screen.getByText('2')).toHaveClass('unread-badge');
        expect(MockWebSocket.instances).toHaveLength(1);
        expect(MockWebSocket.instances[0].url).toContain('/ws/notifications/');
    });

    it('updates only inactive chat badges from notifications', async () => {
        const user = userEvent.setup();
        render(<ChatPage />);
        await screen.findByText('General');
        await user.click(screen.getByText('General').closest('[role="button"]'));
        await waitFor(() => expect(MockWebSocket.instances).toHaveLength(2));

        act(() => MockWebSocket.instances[0].receive({
            type: 'unread_update', chat_id: 2, unread_count: 4,
        }));
        expect(screen.getByText('4')).toHaveClass('unread-badge');

        act(() => MockWebSocket.instances[0].receive({
            type: 'unread_update', chat_id: 1, unread_count: 3,
        }));
        expect(screen.queryByText('3')).not.toBeInTheDocument();
    });

    it('marks a selected chat read and opens its message socket', async () => {
        const user = userEvent.setup();
        render(<ChatPage />);
        await user.click((await screen.findByText('Project')).closest('[role="button"]'));

        await waitFor(() => expect(fetch).toHaveBeenCalledWith(
            '/api/chats/2/read/',
            expect.objectContaining({ method: 'POST', credentials: 'same-origin' }),
        ));
        await waitFor(() => expect(screen.queryByText('2')).not.toBeInTheDocument());
        expect(MockWebSocket.instances[1].url).toContain('/ws/chat/2/');
    });

    it('appends live messages and keeps the open chat read', async () => {
        const user = userEvent.setup();
        render(<ChatPage />);
        await user.click((await screen.findByText('General')).closest('[role="button"]'));
        await waitFor(() => expect(MockWebSocket.instances).toHaveLength(2));

        act(() => MockWebSocket.instances[1].receive({
            id: 10,
            username: 'bob',
            prof_pic: '/bob.png',
            text: 'Live hello',
            timestamp: '2026-01-01T12:00:00Z',
            attachments: [],
        }));

        expect(await screen.findByText('Live hello')).toBeInTheDocument();
        expect(fetch).toHaveBeenCalledWith(
            '/api/chats/1/read/',
            expect.objectContaining({ method: 'POST' }),
        );
    });

    it('closes the old chat socket when switching chats and all sockets on unmount', async () => {
        const user = userEvent.setup();
        const { unmount } = render(<ChatPage />);
        await user.click((await screen.findByText('General')).closest('[role="button"]'));
        await waitFor(() => expect(MockWebSocket.instances).toHaveLength(2));
        const firstChatSocket = MockWebSocket.instances[1];

        await user.click(screen.getByText('Project').closest('[role="button"]'));
        await waitFor(() => expect(MockWebSocket.instances).toHaveLength(3));
        expect(firstChatSocket.close).toHaveBeenCalled();

        unmount();
        expect(MockWebSocket.instances[0].close).toHaveBeenCalled();
        expect(MockWebSocket.instances[2].close).toHaveBeenCalled();
    });
});
