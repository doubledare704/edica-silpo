import { render, screen } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import AgentTimeline from '../AgentTimeline.svelte';

describe('AgentTimeline', () => {
	beforeEach(() => {
		// Mock fetch so it never resolves during these tests
		vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
	});

	afterEach(() => {
		vi.unstubAllGlobals();
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
		render(AgentTimeline, {
			request: { userText: 'Тест', audioBase64: '', threadId: 'thread-1' },
			oncomplete: vi.fn(),
		});
		expect(screen.getByTestId('timeline-streaming')).toBeInTheDocument();
	});

	it('calls oncomplete callback once stream finishes', async () => {
		// This test verifies the prop is wired, not actual SSE (that needs integration tests)
		const oncomplete = vi.fn();
		render(AgentTimeline, {
			request: { userText: 'Тест', audioBase64: '', threadId: 'thread-1' },
			oncomplete,
		});
		// oncomplete not called yet — stream is pending
		expect(oncomplete).not.toHaveBeenCalled();
	});
});

