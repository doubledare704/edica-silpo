import { describe, it, expect, beforeEach } from 'vitest';
import { cartStore, setCart, clearCart, cartItemsCount } from '../cartStore.svelte';

const PAYLOAD = {
	cartUrl: 'https://silpo.ua/cart/share/mock_123',
	summary: 'Кошик зібрано.',
	totalPrice: 565.0,
	isBudgetExceeded: false,
	items: [
		{
			id: 'sku-1',
			title: 'Ошийник свинячий',
			price: 240.0,
			quantity: 2,
			is_private_label: false,
			line_total: 480.0,
			image_url: null,
		},
		{
			id: 'sku-2',
			title: 'Молоко Премія 2.5%',
			price: 85.0,
			quantity: 1,
			is_private_label: false,
			line_total: 85.0,
			image_url: null,
		},
	],
};

describe('cartStore', () => {
	beforeEach(() => {
		clearCart();
	});

	it('starts empty with zero count', () => {
		expect(cartStore.items).toEqual([]);
		expect(cartItemsCount()).toBe(0);
	});

	it('stores picked items and sums quantities for the badge', () => {
		setCart(PAYLOAD);
		expect(cartStore.items).toHaveLength(2);
		expect(cartItemsCount()).toBe(3);
		expect(cartStore.cartUrl).toBe('https://silpo.ua/cart/share/mock_123');
	});

	it('clears the cart back to empty', () => {
		setCart(PAYLOAD);
		clearCart();
		expect(cartStore.items).toEqual([]);
		expect(cartStore.cartUrl).toBeNull();
		expect(cartItemsCount()).toBe(0);
	});
});
