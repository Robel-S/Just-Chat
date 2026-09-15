import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MembersSidebar } from '../pages/chats.jsx';

const members = [
    { id: 1, user: 1, username: 'alice', prof_pic: '/alice.png' },
    { id: 2, user: 2, username: 'bob', prof_pic: '/bob.png' },
];

describe('MembersSidebar', () => {
    beforeEach(() => {
        global.fetch = vi.fn(async (_url, options = {}) => {
            if (options.method === 'DELETE') return { ok: true, json: async () => ({}) };
            return { ok: true, json: async () => members };
        });
        vi.spyOn(window, 'confirm').mockReturnValue(true);
    });

    it('shows an empty state without a selected chat', () => {
        render(<MembersSidebar chatId={null} user={{ id: 1 }} chatOwner={1} />);
        expect(screen.getByText('No chat selected')).toBeInTheDocument();
        expect(fetch).not.toHaveBeenCalled();
    });

    it('loads and renders members for the selected chat', async () => {
        render(<MembersSidebar chatId={4} user={{ id: 1 }} chatOwner={1} />);
        expect(await screen.findByText('alice')).toBeInTheDocument();
        expect(screen.getByText('bob')).toBeInTheDocument();
        expect(fetch).toHaveBeenCalledWith('/api/members/4');
    });

    it('shows kick only for an owner and never for the current user', async () => {
        render(<MembersSidebar chatId={4} user={{ id: 1 }} chatOwner={1} />);
        await screen.findByText('bob');
        expect(screen.getAllByRole('button', { name: 'Kick' })).toHaveLength(1);
    });

    it('does not show kick controls to a non-owner', async () => {
        render(<MembersSidebar chatId={4} user={{ id: 2 }} chatOwner={1} />);
        await screen.findByText('bob');
        expect(screen.queryByRole('button', { name: 'Kick' })).not.toBeInTheDocument();
    });

    it('does not call the API when removal is cancelled', async () => {
        window.confirm.mockReturnValue(false);
        const interaction = userEvent.setup();
        render(<MembersSidebar chatId={4} user={{ id: 1 }} chatOwner={1} />);
        await interaction.click(await screen.findByRole('button', { name: 'Kick' }));
        expect(fetch).toHaveBeenCalledTimes(1);
    });

    it('removes a member only after a successful response', async () => {
        const interaction = userEvent.setup();
        render(<MembersSidebar chatId={4} user={{ id: 1 }} chatOwner={1} />);
        await interaction.click(await screen.findByRole('button', { name: 'Kick' }));
        await waitFor(() => expect(screen.queryByText('bob')).not.toBeInTheDocument());
    });

    it('preserves the member and displays an error when removal fails', async () => {
        fetch.mockImplementation(async (_url, options = {}) => {
            if (options.method === 'DELETE') return { ok: false, status: 403 };
            return { ok: true, json: async () => members };
        });
        const interaction = userEvent.setup();
        render(<MembersSidebar chatId={4} user={{ id: 1 }} chatOwner={1} />);
        await interaction.click(await screen.findByRole('button', { name: 'Kick' }));
        expect(await screen.findByRole('alert')).toHaveTextContent('Failed to remove member');
        expect(screen.getByText('bob')).toBeInTheDocument();
    });
});
