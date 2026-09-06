import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import CartItemsPreview from '../CartItemsPreview.svelte';
import type { CartItem } from '$lib/cart';

const ITEMS: CartItem[] = [
	{ id: 'sku-1', title: 'Ошийник свинячий', price: 240, quantity: 2, is_private_label: false, line_total: 480 },
	{ id: 'sku-2', title: 'Овочі для гриля Премія', price: 85, quantity: 1, is_private_label: true, line_total: 85 },
	{ id: 'sku-3', title: 'Вода мінеральна', price: 22, quantity: 3, is_private_label: false, line_total: 66 },
	{ id: 'sku-4', title: 'Багет', price: 28.5, quantity: 1, is_private_label: false, line_total: 28.5 },
	{ id: 'sku-5', title: 'Молоко Премія', price: 36.9, quantity: 1, is_private_label: true, line_total: 36.9 },
];

describe('CartItemsPreview', () => {
	it('renders the quick-preview header with the items count', () => {
		render(CartItemsPreview, { items: ITEMS });
		expect(screen.getByTestId('cart-items-preview')).toBeInTheDocument();
		expect(screen.getByText(/Швидкий перегляд \(5 товарів\)/)).toBeInTheDocument();
	});

	it('shows the ЗАМІНА badge for private-label replacements', () => {
		render(CartItemsPreview, { items: ITEMS });
		expect(screen.getAllByText('ЗАМІНА').length).toBeGreaterThan(0);
	});

	it('expands to the full viewing list when "Усі" is pressed', async () => {
		render(CartItemsPreview, { items: ITEMS });
		expect(screen.queryByTestId('cart-items-full')).not.toBeInTheDocument();

		await fireEvent.click(screen.getByTestId('cart-items-toggle'));

		const full = screen.getByTestId('cart-items-full');
		expect(full).toBeInTheDocument();
		expect(full).toHaveTextContent('Молоко Премія');
	});

	it('renders nothing when the cart is empty', () => {
		render(CartItemsPreview, { items: [] });
		expect(screen.queryByTestId('cart-items-preview')).not.toBeInTheDocument();
	});
});
