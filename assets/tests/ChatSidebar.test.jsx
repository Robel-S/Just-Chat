import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ChatSidebar } from '../pages/chats.jsx';

const chats = [
    { id: 1, owner: 1, name: 'Owned chat', image: '/one.png' },
    { id: 2, owner: 2, name: 'Member chat', image: '/two.png' },
];

describe('ChatSidebar', () => {
    beforeEach(() => {
        global.fetch = vi.fn(async (url, options = {}) => {
            if (String(url).endsWith('/api/friends')) {
                return { ok: true, json: async () => [] };
            }
            if (!options.method || options.method === 'GET') {
                return { ok: true, json: async () => chats };
            }
            return { ok: true, json: async () => ({ chat_deleted: false }) };
        });
    });

    function renderSidebar(props = {}) {
        return render(
            <ChatSidebar
                chatId={null}
                onSetChat={vi.fn()}
                user={{ id: 1, username: 'alice' }}
                setChatOwner={vi.fn()}
                unreadCounts={{ 2: 3 }}
                {...props}
            />,
        );
    }

    it('renders chats and positive unread badges', async () => {
        renderSidebar();
        expect(await screen.findByText('Owned chat')).toBeInTheDocument();
        expect(screen.getByText('3')).toHaveClass('unread-badge');
    });

    it('selects a chat by mouse and keyboard', async () => {
        const onSetChat = vi.fn();
        const setChatOwner = vi.fn();
        const user = userEvent.setup();
        renderSidebar({ onSetChat, setChatOwner });
        const row = (await screen.findByText('Owned chat')).closest('[role="button"]');

        await user.click(row);
        await user.keyboard('{Enter}');

        expect(onSetChat).toHaveBeenCalledWith(1);
        expect(setChatOwner).toHaveBeenCalledWith(1);
    });

    it('shows owner actions only for chats owned by the user', async () => {
        const user = userEvent.setup();
        renderSidebar();

        await user.click(await screen.findByRole('button', { name: 'Open menu for Owned chat' }));
        expect(screen.getByText('Edit Chat')).toBeInTheDocument();
        expect(screen.getByText('Delete Chat')).toBeInTheDocument();

        await user.click(screen.getByRole('button', { name: 'Open menu for Member chat' }));
        expect(screen.queryByText('Edit Chat')).not.toBeInTheDocument();
        expect(screen.queryByText('Delete Chat')).not.toBeInTheDocument();
        expect(screen.getByText('Leave Chat')).toBeInTheDocument();
    });

    it('toggles the same menu closed without throwing', async () => {
        const user = userEvent.setup();
        renderSidebar();
        const button = await screen.findByRole('button', { name: 'Open menu for Owned chat' });
        await user.click(button);
        expect(screen.getByText('Edit Chat')).toBeInTheDocument();
        await user.click(button);
        expect(screen.queryByText('Edit Chat')).not.toBeInTheDocument();
    });

    it('deletes an owned chat and refreshes the list', async () => {
        const user = userEvent.setup();
        renderSidebar();
        await user.click(await screen.findByRole('button', { name: 'Open menu for Owned chat' }));
        await user.click(screen.getByText('Delete Chat'));

        await waitFor(() => expect(fetch).toHaveBeenCalledWith(
            '/api/chats/1/',
            expect.objectContaining({ method: 'DELETE' }),
        ));
    });

    it('opens the create dialog from an accessible button', async () => {
        const user = userEvent.setup();
        renderSidebar();
        await user.click(screen.getByRole('button', { name: 'Create chat' }));
        expect(await screen.findByRole('dialog', { name: 'Create Chat' })).toBeInTheDocument();
    });
});
