import { render, screen } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import CartCard from '../CartCard.svelte';

const baseProps = {
	cartUrl: 'https://silpo.ua/cart/share/mock_123',
	summary: 'Я зібрала кошик для пікніка на шість осіб.',
	audioUrl: '/static/audio/mock_response.wav',
	totalPrice: 2450.0,
	isBudgetExceeded: false,
	items: [
		{
			id: 'sku-1',
			title: 'Ошийник свинячий',
			price: 240.0,
			quantity: 2,
			is_private_label: false,
			line_total: 480.0,
		},
		{
			id: 'sku-2',
			title: 'Овочі для гриля Премія',
			price: 85.0,
			quantity: 1,
			is_private_label: true,
			line_total: 85.0,
		},
	],
};

describe('CartCard', () => {
	beforeEach(() => {
		vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('renders the summary text', () => {
		render(CartCard, baseProps);
		expect(screen.getByText('Я зібрала кошик для пікніка на шість осіб.')).toBeInTheDocument();
	});

	it('renders a checkout link with correct href', () => {
		render(CartCard, baseProps);
		const link = screen.getByRole('link', { name: /оформлення/i });
		expect(link).toHaveAttribute('href', 'https://silpo.ua/cart/share/mock_123');
	});

	it('renders an audio player when audioUrl is provided', () => {
		render(CartCard, baseProps);
		const audio = document.querySelector('audio');
		expect(audio).toBeInTheDocument();
		expect(audio).toHaveAttribute('src', '/static/audio/mock_response.wav');
	});

	it('starts playing generated audio as soon as the player is ready', async () => {
		render(CartCard, baseProps);

		const audio = document.querySelector('audio');
		expect(audio).toBeInTheDocument();
		await vi.waitFor(() => expect(HTMLMediaElement.prototype.play).toHaveBeenCalled());
	});

	it('does not render audio player when audioUrl is null', () => {
		render(CartCard, { ...baseProps, audioUrl: null });
		expect(document.querySelector('audio')).not.toBeInTheDocument();
	});

	it('displays total price', () => {
		render(CartCard, baseProps);
		expect(screen.getByTestId('total-price')).toHaveTextContent('2450');
	});

	it('shows budget exceeded warning when isBudgetExceeded is true', () => {
		render(CartCard, { ...baseProps, isBudgetExceeded: true });
		expect(screen.getByTestId('budget-warning')).toBeInTheDocument();
	});

	it('does not show budget warning when budget is within limits', () => {
		render(CartCard, baseProps);
		expect(screen.queryByTestId('budget-warning')).not.toBeInTheDocument();
	});

	it('shows within-budget badge when budget is within limits', () => {
		render(CartCard, baseProps);
		expect(screen.getByTestId('budget-ok')).toHaveTextContent('В межах бюджету');
	});

	it('formats large totals in the ring label', () => {
		render(CartCard, baseProps);
		expect(screen.getByText('2.45k')).toBeInTheDocument();
	});

	it('renders the quick preview of picked items', () => {
		render(CartCard, baseProps);
		expect(screen.getByTestId('cart-items-preview')).toBeInTheDocument();
		expect(screen.getByText('Ошийник свинячий')).toBeInTheDocument();
	});

	it('hides the preview when no items were picked', () => {
		render(CartCard, { ...baseProps, items: [] });
		expect(screen.queryByTestId('cart-items-preview')).not.toBeInTheDocument();
	});
});
