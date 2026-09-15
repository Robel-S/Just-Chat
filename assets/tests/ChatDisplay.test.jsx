import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ChatDisplay } from '../pages/chats.jsx';

const baseMessage = {
    id: 1,
    username: 'alice',
    prof_pic: '/alice.png',
    text: 'Hello world',
    timestamp: '2026-01-01T12:00:00Z',
    attachments: [],
};

describe('ChatDisplay', () => {
    it('renders a skeleton when no chat is selected', () => {
        const { container } = render(<ChatDisplay chatId={null} messages={[]} />);
        expect(container.querySelector('.chat-skeleton')).toBeInTheDocument();
    });

    it('renders message identity, text, and profile image', () => {
        render(<ChatDisplay chatId={1} messages={[baseMessage]} />);
        expect(screen.getByText('alice')).toBeInTheDocument();
        expect(screen.getByText('Hello world')).toBeInTheDocument();
        expect(screen.getByRole('img', { name: "alice's profile" })).toHaveAttribute('src', '/alice.png');
    });

    it('renders image attachments with case-insensitive extensions and query strings', () => {
        const message = {
            ...baseMessage,
            attachments: [{ id: 4, name: 'PHOTO.JPG', file: '/media/PHOTO.JPG?token=abc' }],
        };
        render(<ChatDisplay chatId={1} messages={[message]} />);
        expect(screen.getByRole('img', { name: 'Attachment' })).toHaveAttribute(
            'src', '/media/PHOTO.JPG?token=abc',
        );
    });

    it('does not misclassify a non-image extension containing .jpg', () => {
        const message = {
            ...baseMessage,
            attachments: [{ id: 5, name: 'report.jpg.pdf', file: '/media/report.jpg.pdf' }],
        };
        render(<ChatDisplay chatId={1} messages={[message]} />);
        expect(screen.getByRole('link', { name: '↓' })).toHaveAttribute('href', '/media/report.jpg.pdf');
    });

    it('renders attachment-only messages', () => {
        const message = {
            ...baseMessage,
            text: '',
            attachments: [{ id: 6, name: 'notes.txt', file: '/media/notes.txt' }],
        };
        render(<ChatDisplay chatId={1} messages={[message]} />);
        expect(screen.getByText('notes.txt')).toBeInTheDocument();
    });
});
