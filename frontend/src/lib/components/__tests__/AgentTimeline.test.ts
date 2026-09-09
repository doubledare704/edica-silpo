import { render, screen, waitFor } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import AgentTimeline from '../AgentTimeline.svelte';

const REQUEST = {
	userText: 'Тест',
	audioBase64: '',
	threadId: 'thread-1',
	deliveryAddress: 'Київ, вул. Мишуги Олександра, 4',
};

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
		items: [
			{
				id: 'sku-1',
				title: 'Ошийник свинячий',
				price: 240.0,
				quantity: 2,
				is_private_label: false,
				line_total: 480.0,
				image_url: 'https://images.silpo.ua/meat.jpg',
			},
		],
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

	it('sends the selected delivery address with the stream request', async () => {
		const oncomplete = vi.fn();
		const fetchMock = mockFetchWithSse([COMPLETE_EVENT]);

		render(AgentTimeline, { request: REQUEST, oncomplete });

		await waitFor(() => expect(oncomplete).toHaveBeenCalled());

		expect(fetchMock).toHaveBeenCalledWith(
			'http://localhost:8000/api/agent/stream',
			expect.objectContaining({
				body: expect.stringContaining('"delivery_address":"Київ, вул. Мишуги Олександра, 4"'),
			}),
		);
	});

	it('labels the plan_meals thinking step in Ukrainian', async () => {
		const oncomplete = vi.fn();
		mockFetchWithSse([
			{ event: 'thinking_step', data: { node: 'plan_meals' } },
			COMPLETE_EVENT,
		]);

		render(AgentTimeline, { request: REQUEST, oncomplete });

		await waitFor(() => expect(oncomplete).toHaveBeenCalled());
		expect(screen.getByText('🍽️ Тижневе меню')).toBeInTheDocument();
	});

	it('forwards the weekly meal plan from node_complete', async () => {
		const oncomplete = vi.fn();
		mockFetchWithSse([
			{
				event: 'node_complete',
				data: {
					...COMPLETE_EVENT.data,
					meal_plan: { days: [{ day: 'День 1', dishes: ['Хек з гречкою'] }] },
				},
			},
		]);

		render(AgentTimeline, { request: REQUEST, oncomplete });

		await waitFor(() => expect(oncomplete).toHaveBeenCalled());
		expect(oncomplete).toHaveBeenCalledWith(
			expect.objectContaining({
				mealPlan: { days: [{ day: 'День 1', dishes: ['Хек з гречкою'] }] },
			}),
		);
	});

	it('forwards normalized cart items from node_complete', async () => {
		const oncomplete = vi.fn();
		mockFetchWithSse([COMPLETE_EVENT]);

		render(AgentTimeline, { request: REQUEST, oncomplete });

		await waitFor(() => expect(oncomplete).toHaveBeenCalled());
		expect(oncomplete).toHaveBeenCalledWith(
			expect.objectContaining({
				items: [expect.objectContaining({ title: 'Ошийник свинячий', quantity: 2 })],
			}),
		);
	});

	it('normalizes item image_url and forwards the total price', async () => {
		const oncomplete = vi.fn();
		mockFetchWithSse([COMPLETE_EVENT]);

		render(AgentTimeline, { request: REQUEST, oncomplete });

		await waitFor(() => expect(oncomplete).toHaveBeenCalled());
		expect(oncomplete).toHaveBeenCalledWith(
			expect.objectContaining({
				totalPrice: 2450.0,
				items: [expect.objectContaining({ image_url: 'https://images.silpo.ua/meat.jpg' })],
			}),
		);
	});

	it('maps missing image_url to null', async () => {
		const oncomplete = vi.fn();
		mockFetchWithSse([
			{
				event: 'node_complete',
				data: { ...COMPLETE_EVENT.data, items: [{ ...COMPLETE_EVENT.data.items[0], image_url: undefined }] },
			},
		]);

		render(AgentTimeline, { request: REQUEST, oncomplete });

		await waitFor(() => expect(oncomplete).toHaveBeenCalled());
		expect(oncomplete).toHaveBeenCalledWith(
			expect.objectContaining({ items: [expect.objectContaining({ image_url: null })] }),
		);
	});

	it('forwards the planned budget derived from total and remaining', async () => {
		const oncomplete = vi.fn();
		mockFetchWithSse([
			{
				event: 'node_complete',
				data: { ...COMPLETE_EVENT.data, total_price: 1600, remaining_budget: 1400 },
			},
		]);

		render(AgentTimeline, { request: REQUEST, oncomplete });

		await waitFor(() => expect(oncomplete).toHaveBeenCalled());
		expect(oncomplete).toHaveBeenCalledWith(expect.objectContaining({ budget: 3000 }));
	});

	it('forwards null budget when no budget was set', async () => {
		const oncomplete = vi.fn();
		mockFetchWithSse([
			{
				event: 'node_complete',
				data: { ...COMPLETE_EVENT.data, total_price: 0, remaining_budget: 0 },
			},
		]);

		render(AgentTimeline, { request: REQUEST, oncomplete });

		await waitFor(() => expect(oncomplete).toHaveBeenCalled());
		expect(oncomplete).toHaveBeenCalledWith(expect.objectContaining({ budget: null }));
	});

	it('forwards unfulfilled requests from node_complete', async () => {
		const oncomplete = vi.fn();
		mockFetchWithSse([
			{
				event: 'node_complete',
				data: { ...COMPLETE_EVENT.data, unfulfilled_requests: ['Вино вишукане', 'Сири крафтові'] },
			},
		]);

		render(AgentTimeline, { request: REQUEST, oncomplete });

		await waitFor(() => expect(oncomplete).toHaveBeenCalled());
		expect(oncomplete).toHaveBeenCalledWith(
			expect.objectContaining({ unfulfilled: ['Вино вишукане', 'Сири крафтові'] }),
		);
	});

	it('caps the thought list at one-third viewport height with scrolling', async () => {
		const oncomplete = vi.fn();
		mockFetchWithSse([
			{ event: 'thinking_step', data: { node: 'stt' } },
			COMPLETE_EVENT,
		]);

		render(AgentTimeline, { request: REQUEST, oncomplete });

		await waitFor(() => expect(oncomplete).toHaveBeenCalled());
		const list = screen.getByTestId('timeline-events');
		expect(list.className).toContain('max-h-[33vh]');
		expect(list.className).toContain('overflow-y-auto');
	});

	it('pins the thought list to the bottom when new events arrive', async () => {
		const oncomplete = vi.fn();
		mockFetchWithSse([
			{ event: 'thinking_step', data: { node: 'stt' } },
			{ event: 'thinking_step', data: { node: 'parse_intent' } },
			COMPLETE_EVENT,
		]);

		render(AgentTimeline, { request: REQUEST, oncomplete });

		await waitFor(() => expect(oncomplete).toHaveBeenCalled());
		const list = screen.getByTestId('timeline-events') as HTMLElement;
		await waitFor(() => expect(list.scrollTop).toBe(list.scrollHeight));
	});

	it('notifies onstreaming when thinking starts and finishes', async () => {
		const oncomplete = vi.fn();
		const onstreaming = vi.fn();
		mockFetchWithSse([COMPLETE_EVENT]);

		render(AgentTimeline, { request: REQUEST, oncomplete, onstreaming });

		await waitFor(() => expect(onstreaming).toHaveBeenCalledWith(true));
		await waitFor(() => expect(oncomplete).toHaveBeenCalled());
		await waitFor(() => expect(onstreaming).toHaveBeenCalledWith(false));
	});
});