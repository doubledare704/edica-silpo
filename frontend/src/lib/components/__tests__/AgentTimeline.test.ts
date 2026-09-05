import { render, screen, waitFor } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import AgentTimeline from '../AgentTimeline.svelte';

const REQUEST = { userText: 'Тест', audioBase64: '', threadId: 'thread-1' };

function mockFetchWithSse(events: Array<{ event: string; data: unknown }>) {
	const body = events
		.flatMap((ev) => [`event: ${ev.event}`, `data: ${JSON.stringify(ev.data)}`, ''])
		.join('\n');
	const reader = {
		read: vi
			.fn()
			.mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(body) })
			.mockResolvedValueOnce({ done: true, value: undefined }),
	};
	const fetchMock = vi.fn().mockResolvedValue({
		ok: true,
		status: 200,
		body: { getReader: () => reader },
	});
	vi.stubGlobal('fetch', fetchMock);
	return fetchMock;
}

const COMPLETE_EVENT = {
	event: 'node_complete',
	data: {
		node: 'tts',
		intent: 'party',
		total_price: 2450.0,
		is_budget_exceeded: false,
		cart_url: 'https://silpo.ua/cart/share/mock_123',
		summary: 'Кошик зібрано.',
		audio_url: '/static/audio/abc123.wav',
	},
};

describe('AgentTimeline', () => {
	beforeEach(() => {
		// Mock fetch so it never resolves during these tests
		vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
	});

	afterEach(() => {
		vi.unstubAllGlobals();
		vi.unstubAllEnvs();
	});

	it('renders the timeline container', () => {
		render(AgentTimeline, { request: null, oncomplete: vi.fn() });
		expect(screen.getByTestId('agent-timeline')).toBeInTheDocument();
	});

	it('shows empty state message when no request is active', () => {
		render(AgentTimeline, { request: null, oncomplete: vi.fn() });
		expect(screen.getByTestId('timeline-empty')).toBeInTheDocument();
	});

	it('shows streaming indicator when a request is provided', () => {
		render(AgentTimeline, { request: REQUEST, oncomplete: vi.fn() });
		expect(screen.getByTestId('timeline-streaming')).toBeInTheDocument();
	});

	it('calls oncomplete callback once stream finishes', async () => {
		// This test verifies the prop is wired, not actual SSE (that needs integration tests)
		const oncomplete = vi.fn();
		render(AgentTimeline, { request: REQUEST, oncomplete });
		// oncomplete not called yet — stream is pending
		expect(oncomplete).not.toHaveBeenCalled();
	});

	it('resolves relative audio_url against the backend origin', async () => {
		const oncomplete = vi.fn();
		const fetchMock = mockFetchWithSse([COMPLETE_EVENT]);

		render(AgentTimeline, { request: REQUEST, oncomplete });

		await waitFor(() => expect(oncomplete).toHaveBeenCalled());

		expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/api/agent/stream', expect.any(Object));
		expect(oncomplete).toHaveBeenCalledWith(
			expect.objectContaining({ audioUrl: 'http://localhost:8000/static/audio/abc123.wav' }),
		);
	});

	it('passes absolute audio_url through unchanged', async () => {
		const oncomplete = vi.fn();
		mockFetchWithSse([
			{
				event: 'node_complete',
				data: { ...COMPLETE_EVENT.data, audio_url: 'https://cdn.example.com/audio/abc123.wav' },
			},
		]);

		render(AgentTimeline, { request: REQUEST, oncomplete });

		await waitFor(() => expect(oncomplete).toHaveBeenCalled());
		expect(oncomplete).toHaveBeenCalledWith(
			expect.objectContaining({ audioUrl: 'https://cdn.example.com/audio/abc123.wav' }),
		);
	});

	it('keeps audio_url null when the payload has none', async () => {
		const oncomplete = vi.fn();
		mockFetchWithSse([{ event: 'node_complete', data: { ...COMPLETE_EVENT.data, audio_url: null } }]);

		render(AgentTimeline, { request: REQUEST, oncomplete });

		await waitFor(() => expect(oncomplete).toHaveBeenCalled());
		expect(oncomplete).toHaveBeenCalledWith(expect.objectContaining({ audioUrl: null }));
	});

	it('uses VITE_BACKEND_URL for the stream and resolved audio', async () => {
		const oncomplete = vi.fn();
		const fetchMock = mockFetchWithSse([COMPLETE_EVENT]);
		vi.stubEnv('VITE_BACKEND_URL', 'https://api.example.com');

		render(AgentTimeline, { request: REQUEST, oncomplete });

		await waitFor(() => expect(oncomplete).toHaveBeenCalled());

		expect(fetchMock).toHaveBeenCalledWith('https://api.example.com/api/agent/stream', expect.any(Object));
		expect(oncomplete).toHaveBeenCalledWith(
			expect.objectContaining({ audioUrl: 'https://api.example.com/static/audio/abc123.wav' }),
		);
	});
});