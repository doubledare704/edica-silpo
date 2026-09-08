import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import QueryInProgress from '../QueryInProgress.svelte';

describe('QueryInProgress', () => {
	it('renders the user query text being processed', () => {
		render(QueryInProgress, { query: 'Продукти на тиждень до 2000 грн' });
		expect(screen.getByTestId('query-in-progress')).toBeInTheDocument();
		expect(screen.getByTestId('query-in-progress-text')).toHaveTextContent(
			'Продукти на тиждень до 2000 грн',
		);
	});

	it('falls back to a voice label when the query is empty', () => {
		render(QueryInProgress, { query: '' });
		expect(screen.getByTestId('query-in-progress-text')).toHaveTextContent(/голосовий/i);
	});

	it('exposes a polite live region for assistive tech', () => {
		render(QueryInProgress, { query: 'Хліб' });
		const region = screen.getByTestId('query-in-progress');
		expect(region).toHaveAttribute('role', 'status');
	});
});
