import { describe, it, expect } from 'vitest';
import { itemEmoji, itemsCountLabel, normalizeCartItems } from '../cart';

describe('cart helpers', () => {
	it('maps known product titles to emoji', () => {
		expect(itemEmoji('Ошийник свинячий')).toBe('🥩');
		expect(itemEmoji('Томати Премія')).toBe('🍅');
		expect(itemEmoji('Багет')).toBe('🥖');
		expect(itemEmoji('Молоко Премія 2.5%')).toBe('🥛');
	});

	it('falls back to a generic emoji for unknown titles', () => {
		expect(itemEmoji('Щось невідоме')).toBe('🛒');
	});

	it('pluralizes the items count label in Ukrainian', () => {
		expect(itemsCountLabel(1)).toBe('1 товар');
		expect(itemsCountLabel(3)).toBe('3 товари');
		expect(itemsCountLabel(12)).toBe('12 товарів');
	});

	it('normalizes raw SSE items into CartItem records', () => {
		const normalized = normalizeCartItems([
			{ id: 'sku-1', title: 'Ошийник свинячий', price: 240, quantity: 2, is_private_label: false },
		]);
		expect(normalized).toHaveLength(1);
		expect(normalized[0]).toMatchObject({ title: 'Ошийник свинячий', price: 240, quantity: 2 });
	});

	it('drops entries without a title and non-array payloads', () => {
		expect(normalizeCartItems(null)).toEqual([]);
		expect(normalizeCartItems([{ price: 10 }])).toEqual([]);
	});
});
