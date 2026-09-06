import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import CartItemsPreview from '../CartItemsPreview.svelte';
import type { CartItem } from '$lib/cart';

const ITEMS: CartItem[] = [
	{ id: 'sku-1', title: 'Ошийник свинячий', price: 240, quantity: 2, is_private_label: false, line_total: 480, image_url: null },
	{ id: 'sku-2', title: 'Овочі для гриля Премія', price: 85, quantity: 1, is_private_label: true, line_total: 85, image_url: null },
	{ id: 'sku-3', title: 'Вода мінеральна', price: 22, quantity: 3, is_private_label: false, line_total: 66, image_url: 'https://images.silpo.ua/water.jpg' },
	{ id: 'sku-4', title: 'Багет', price: 28.5, quantity: 1, is_private_label: false, line_total: 28.5, image_url: null },
	{ id: 'sku-5', title: 'Молоко Премія', price: 36.9, quantity: 1, is_private_label: true, line_total: 36.9, image_url: null },
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

	it('does not crash on duplicate item ids (retry flow can re-accept the same product)', () => {
		const duplicated: CartItem[] = [ITEMS[0], { ...ITEMS[0], quantity: 1, line_total: 240 }];
		render(CartItemsPreview, { items: duplicated });
		expect(screen.getByTestId('cart-items-preview')).toBeInTheDocument();
	});

	it('renders the product image when image_url is present', () => {
		const { container } = render(CartItemsPreview, { items: ITEMS });
		const image = container.querySelector('img');
		expect(image).not.toBeNull();
		expect(image).toHaveAttribute('src', 'https://images.silpo.ua/water.jpg');
	});

	it('falls back to the emoji placeholder when image_url is missing', () => {
		const { container } = render(CartItemsPreview, { items: [ITEMS[3]] });
		expect(container.querySelector('img')).toBeNull();
	});
});
