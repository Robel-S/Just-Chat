export class MockWebSocket {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;
    static instances = [];

    constructor(url) {
        this.url = url;
        this.readyState = MockWebSocket.OPEN;
        this.sent = [];
        this.close = vi.fn(() => {
            this.readyState = MockWebSocket.CLOSED;
        });
        MockWebSocket.instances.push(this);
    }

    send(data) {
        if (this.readyState !== MockWebSocket.OPEN) {
            throw new DOMException('WebSocket is not open', 'InvalidStateError');
        }
        this.sent.push(data);
    }

    receive(data) {
        this.onmessage?.({ data: JSON.stringify(data) });
    }

    static reset() {
        MockWebSocket.instances = [];
    }
}
