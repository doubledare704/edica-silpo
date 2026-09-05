import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import CartCard from '../CartCard.svelte';

const baseProps = {
	cartUrl: 'https://silpo.ua/cart/share/mock_123',
	summary: 'Я зібрав кошик для пікніка на шість осіб.',
	audioUrl: '/static/audio/mock_response.mp3',
	totalPrice: 2450.0,
	isBudgetExceeded: false,
};

describe('CartCard', () => {
	it('renders the summary text', () => {
		render(CartCard, baseProps);
		expect(screen.getByText('Я зібрав кошик для пікніка на шість осіб.')).toBeInTheDocument();
	});

	it('renders a cart link with correct href', () => {
		render(CartCard, baseProps);
		const link = screen.getByRole('link', { name: /кошик|cart|відкрити/i });
		expect(link).toHaveAttribute('href', 'https://silpo.ua/cart/share/mock_123');
	});

	it('renders an audio player when audioUrl is provided', () => {
		render(CartCard, baseProps);
		const audio = document.querySelector('audio');
		expect(audio).toBeInTheDocument();
		expect(audio).toHaveAttribute('src', '/static/audio/mock_response.mp3');
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
});

