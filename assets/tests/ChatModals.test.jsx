import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ChatModal, EditModal } from '../pages/chats.jsx';

const user = { id: 1, username: 'alice' };
const friends = [
    { id: 10, user: 1, friend: 2, user_username: 'alice', friend_username: 'bob' },
    { id: 11, user: 1, friend: 3, user_username: 'alice', friend_username: 'carol' },
];

describe('ChatModal', () => {
    beforeEach(() => {
        document.cookie = 'csrftoken=test-token';
        global.fetch = vi.fn(async (url, options = {}) => {
            if (String(url).endsWith('/api/friends')) return { ok: true, json: async () => friends };
            if (String(url).endsWith('/api/chats/create')) return { ok: true, json: async () => ({ id: 9 }) };
            if (String(url).endsWith('/api/chats/9/members')) return { ok: true, json: async () => ({}) };
            throw new Error(`Unexpected request ${url} ${options.method}`);
        });
    });

    it('renders nothing while closed', () => {
        render(<ChatModal openModal={false} setOpenModal={vi.fn()} user={user} />);
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
        expect(fetch).not.toHaveBeenCalled();
    });

    it('requires at least one friend and restores the submit button', async () => {
        const interaction = userEvent.setup();
        render(<ChatModal openModal setOpenModal={vi.fn()} user={user} />);
        const submit = screen.getByRole('button', { name: 'Create Chat' });
        await interaction.click(submit);
        expect(screen.getByText('Please select at least one friend to create a chat.')).toBeInTheDocument();
        expect(submit).toBeEnabled();
    });

    it('creates a DM, adds its member, and reports completion', async () => {
        const interaction = userEvent.setup();
        const onSaved = vi.fn();
        const setOpenModal = vi.fn();
        render(<ChatModal openModal setOpenModal={setOpenModal} user={user} onSaved={onSaved} />);
        const dialog = screen.getByRole('dialog', { name: 'Create Chat' });

        await interaction.type(within(dialog).getByLabelText('Chat Name'), 'Bob chat');
        await interaction.click(await within(dialog).findByLabelText('bob'));
        await interaction.click(within(dialog).getByRole('button', { name: 'Create Chat' }));

        await waitFor(() => expect(fetch).toHaveBeenCalledWith(
            '/api/chats/create',
            expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({ name: 'Bob chat', chat_type: 'DM' }),
            }),
        ));
        expect(fetch).toHaveBeenCalledWith(
            '/api/chats/9/members',
            expect.objectContaining({ body: JSON.stringify({ members: [2] }) }),
        );
        expect(onSaved).toHaveBeenCalled();
        expect(setOpenModal).toHaveBeenCalledWith(false);
    });
});

describe('EditModal', () => {
    beforeEach(() => {
        document.cookie = 'csrftoken=test-token';
        global.fetch = vi.fn(async (url, options = {}) => {
            const path = String(url);
            if (path.endsWith('/api/friends')) return { ok: true, json: async () => friends };
            if (path.endsWith('/api/members/5/')) {
                return { ok: true, json: async () => [{ id: 1, user: 2, username: 'bob' }] };
            }
            if (path.endsWith('/api/chats/5/') && options.method === 'PATCH') {
                return { ok: true, json: async () => ({}) };
            }
            if (path.endsWith('/api/chats/5/members')) return { ok: true, json: async () => ({}) };
            throw new Error(`Unexpected request ${path}`);
        });
    });

    it('loads current members and excludes them from available friends', async () => {
        render(<EditModal openModal setOpenModal={vi.fn()} user={user} chatId={5} />);
        expect(await screen.findByLabelText('carol')).toBeInTheDocument();
        expect(screen.queryByLabelText('bob')).not.toBeInTheDocument();
    });

    it('allows renaming without requiring a new member', async () => {
        const interaction = userEvent.setup();
        const onSaved = vi.fn();
        render(<EditModal openModal setOpenModal={vi.fn()} user={user} chatId={5} onSaved={onSaved} />);

        await interaction.type(screen.getByLabelText('Chat Name'), 'Renamed');
        await interaction.click(screen.getByRole('button', { name: 'Edit Chat' }));

        await waitFor(() => expect(fetch).toHaveBeenCalledWith(
            '/api/chats/5/',
            expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ name: 'Renamed' }) }),
        ));
        expect(onSaved).toHaveBeenCalled();
    });

    it('requires either a new name or a new member', async () => {
        const interaction = userEvent.setup();
        render(<EditModal openModal setOpenModal={vi.fn()} user={user} chatId={5} />);
        await interaction.click(screen.getByRole('button', { name: 'Edit Chat' }));
        expect(screen.getByText('Enter a new name or select at least one friend.')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Edit Chat' })).toBeEnabled();
    });
});
