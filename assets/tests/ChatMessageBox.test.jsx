import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ChatMessageBox } from '../pages/chats.jsx';

describe('ChatMessageBox', () => {
    beforeEach(() => {
        document.cookie = 'csrftoken=test-token';
        global.fetch = vi.fn();
    });

    it('disables message entry when no chat is selected', () => {
        render(<ChatMessageBox chatId={null} send={vi.fn()} />);
        expect(screen.getByLabelText('Message')).toBeDisabled();
        expect(screen.queryByRole('button', { name: 'Send' })).not.toBeInTheDocument();
    });

    it('does not send an empty or whitespace-only message', async () => {
        const send = vi.fn();
        const user = userEvent.setup();
        render(<ChatMessageBox chatId={1} send={send} />);

        await user.type(screen.getByLabelText('Message'), '   ');
        await user.click(screen.getByRole('button', { name: 'Send' }));

        expect(send).not.toHaveBeenCalled();
    });

    it('trims and sends text, then clears the draft', async () => {
        const send = vi.fn(() => true);
        const user = userEvent.setup();
        render(<ChatMessageBox chatId={1} send={send} />);

        const textbox = screen.getByLabelText('Message');
        await user.type(textbox, '  Hello  ');
        await user.click(screen.getByRole('button', { name: 'Send' }));

        expect(send).toHaveBeenCalledWith({ text: 'Hello', attachments: [] });
        expect(textbox).toHaveValue('');
    });

    it('sends on Enter but not Shift+Enter', async () => {
        const send = vi.fn(() => true);
        const user = userEvent.setup();
        render(<ChatMessageBox chatId={1} send={send} />);
        const textbox = screen.getByLabelText('Message');

        await user.type(textbox, 'line one{shift>}{enter}{/shift}line two');
        expect(send).not.toHaveBeenCalled();
        await user.type(textbox, '{enter}');

        expect(send).toHaveBeenCalledOnce();
    });

    it('adds and removes a selected attachment', async () => {
        const user = userEvent.setup();
        const { container } = render(<ChatMessageBox chatId={1} send={vi.fn()} />);
        const file = new File(['hello'], 'notes.txt', { type: 'text/plain' });

        await user.upload(container.querySelector('#file-input'), file);
        expect(screen.getByText('notes.txt')).toBeInTheDocument();
        await user.click(screen.getByRole('button', { name: 'Remove notes.txt' }));
        expect(screen.queryByText('notes.txt')).not.toBeInTheDocument();
    });

    it('uploads attachments before sending their metadata', async () => {
        const uploaded = [{ id: 7, name: 'notes.txt', file: '/media/notes.txt', size: 5 }];
        fetch.mockResolvedValue({ ok: true, json: async () => ({ attachments: uploaded }) });
        const send = vi.fn(() => true);
        const user = userEvent.setup();
        const { container } = render(<ChatMessageBox chatId={1} send={send} />);

        await user.upload(
            container.querySelector('#file-input'),
            new File(['hello'], 'notes.txt', { type: 'text/plain' }),
        );
        await user.click(screen.getByRole('button', { name: 'Send' }));

        await waitFor(() => expect(send).toHaveBeenCalledWith({ text: '', attachments: uploaded }));
        expect(fetch).toHaveBeenCalledWith(
            '/api/attachments/create/',
            expect.objectContaining({ method: 'POST', body: expect.any(FormData) }),
        );
    });

    it('preserves the draft and file when upload fails', async () => {
        fetch.mockResolvedValue({ ok: false, status: 500 });
        const send = vi.fn();
        const user = userEvent.setup();
        const { container } = render(<ChatMessageBox chatId={1} send={send} />);

        await user.type(screen.getByLabelText('Message'), 'important');
        await user.upload(
            container.querySelector('#file-input'),
            new File(['hello'], 'notes.txt', { type: 'text/plain' }),
        );
        await user.click(screen.getByRole('button', { name: 'Send' }));

        expect(await screen.findByRole('alert')).toHaveTextContent('Attachment upload failed');
        expect(send).not.toHaveBeenCalled();
        expect(screen.getByLabelText('Message')).toHaveValue('important');
        expect(screen.getByText('notes.txt')).toBeInTheDocument();
    });

    it('preserves the draft when the chat connection is unavailable', async () => {
        const user = userEvent.setup();
        render(<ChatMessageBox chatId={1} send={() => false} />);
        await user.type(screen.getByLabelText('Message'), 'retry me');
        await user.click(screen.getByRole('button', { name: 'Send' }));

        expect(await screen.findByRole('alert')).toHaveTextContent('not ready');
        expect(screen.getByLabelText('Message')).toHaveValue('retry me');
    });
});
