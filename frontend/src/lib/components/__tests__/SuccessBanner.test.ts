import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect, vi } from 'vitest';
import SuccessBanner from '../SuccessBanner.svelte';

describe('SuccessBanner', () => {
	it('renders the completion title and subtitle', () => {
		render(SuccessBanner, { onnew: vi.fn() });
		expect(screen.getByTestId('success-banner')).toHaveTextContent('Розрахунок завершено');
		expect(screen.getByTestId('success-banner')).toHaveTextContent(
			'Ваш розумний кошик готовий до оформлення.',
		);
	});

	it('calls onnew when the history button is clicked', async () => {
		const onnew = vi.fn();
		render(SuccessBanner, { onnew });
		await fireEvent.click(screen.getByTestId('new-request-button'));
		expect(onnew).toHaveBeenCalledOnce();
	});
});
