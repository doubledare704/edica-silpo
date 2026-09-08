import { render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import DiscountsPage from '../+page.svelte';

describe('discounts page', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('loads and renders MCP offers', async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: async () => ({
				loyalty: { card_number: '123', status: 'sribnyi', bonus_balance: 125.5, bonus_earned: 8.4 },
				promotions: [
					{
						id: 'promo-1',
						title: 'Ціна тижня: Яйця С1',
						description: 'Знижка 12%',
						discount_percent: 12,
						price_from: 54.9,
						price_to: 62,
						ends_at: null,
						is_price_of_week: true,
						image_url: null,
					},
				],
				promo_products: [],
				personal_promos: [],
				coupons: [],
				promo_codes: [],
			}),
		});
		vi.stubGlobal('fetch', fetchMock);

		render(DiscountsPage);

		await waitFor(() => expect(screen.getByText('Ціна тижня: Яйця С1')).toBeInTheDocument());
		expect(screen.getByText('125.50')).toBeInTheDocument();
		expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/offers?delivery_address='));
	});
});
