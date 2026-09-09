import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import EmptyCart from '../EmptyCart.svelte';

const baseProps = {
	summary: 'Я підібрала гурманський кошик із нуль сирів та вин на суму нуль гривень.',
	audioUrl: null as string | null,
	unfulfilled: ['Вино вишукане', 'Сири крафтові'],
	onnew: () => {},
};

describe('EmptyCart', () => {
	beforeEach(() => {
		vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('renders an honest nothing-found heading instead of success copy', () => {
		render(EmptyCart, baseProps);
		expect(screen.getByTestId('empty-cart')).toBeInTheDocument();
		expect(screen.getByText('Нічого не знайдено')).toBeInTheDocument();
		expect(screen.queryByText(/кошик готовий/i)).not.toBeInTheDocument();
	});

	it('shows the agent summary', () => {
		render(EmptyCart, baseProps);
		expect(screen.getByText(baseProps.summary)).toBeInTheDocument();
	});

	it('lists the requests that could not be fulfilled', () => {
		render(EmptyCart, baseProps);
		expect(screen.getByText('Вино вишукане')).toBeInTheDocument();
		expect(screen.getByText('Сири крафтові')).toBeInTheDocument();
	});

	it('hides the missing list when everything was covered', () => {
		render(EmptyCart, { ...baseProps, unfulfilled: [] });
		expect(screen.queryByTestId('empty-cart-missing')).not.toBeInTheDocument();
	});

	it('offers no checkout link', () => {
		render(EmptyCart, baseProps);
		expect(screen.queryByRole('link', { name: /оформлення/i })).not.toBeInTheDocument();
	});

	it('calls back when starting a new request', async () => {
		const onnew = vi.fn();
		render(EmptyCart, { ...baseProps, onnew });
		await fireEvent.click(screen.getByTestId('empty-cart-retry'));
		expect(onnew).toHaveBeenCalledOnce();
	});
});
