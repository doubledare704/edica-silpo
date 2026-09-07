import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import CartDetailList from '../CartDetailList.svelte';

const ITEMS = [
	{
		id: 'sku-1',
		title: 'Ошийник свинячий',
		price: 240.0,
		quantity: 2,
		is_private_label: false,
		line_total: 480.0,
		image_url: 'https://images.silpo.ua/meat.jpg',
	},
	{
		id: 'sku-2',
		title: 'Молоко Премія 2.5%',
		price: 85.0,
		quantity: 1,
		is_private_label: true,
		line_total: 85.0,
		image_url: null,
	},
];

describe('CartDetailList', () => {
	it('renders one row per picked item', () => {
		render(CartDetailList, { items: ITEMS });
		expect(screen.getByTestId('cart-detail-list')).toBeInTheDocument();
		expect(screen.getAllByTestId('cart-detail-item')).toHaveLength(2);
	});

	it('shows quantity, unit price and line total for each item', () => {
		render(CartDetailList, { items: ITEMS });
		expect(screen.getByText('Кількість: 2 × 240.00 грн')).toBeInTheDocument();
		expect(screen.getByText('Сума: 480.00 грн')).toBeInTheDocument();
	});

	it('renders product images when available', () => {
		render(CartDetailList, { items: ITEMS });
		const images = document.querySelectorAll('img');
		expect(images).toHaveLength(1);
		expect(images[0]).toHaveAttribute('src', 'https://images.silpo.ua/meat.jpg');
	});

	it('marks private-label replacements', () => {
		render(CartDetailList, { items: ITEMS });
		expect(screen.getByText('ЗАМІНА')).toBeInTheDocument();
	});
});
