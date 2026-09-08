import { render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { saveProfilePreferences } from '$lib/profilePreferences.svelte';
import ProfilePage from '../+page.svelte';

describe('profile page', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('loads MCP profile data and lets the user save delivery preferences', async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: async () => ({
				profile: { name: 'Олексій', phone: '+380501112233', email: 'oleksii@example.com' },
				loyalty: { card_number: '123', status: 'sribnyi', bonus_balance: 125.5, bonus_earned: 8.4 },
				addresses: [{ address_id: 'addr-1', label: 'Дім', text: 'Київ, вул. Анни Ахматової, 9' }],
				delivery_types: [{ type: 'DeliveryHome', description: 'Regular delivery (groceries, fresh products)', min_order: 400 }],
				branches: [
					{
						branch_id: 'bran-1',
						name: 'Сільпо Київ',
						display_address: 'Київ, вул. Анни Ахматової, 9',
						latitude: 50.3957,
						longitude: 30.6217,
						has_pickup: true,
					},
				],
			}),
		});
		vi.stubGlobal('fetch', fetchMock);

		render(ProfilePage);

		await waitFor(() => expect(screen.getByText('Олексій')).toBeInTheDocument());
		expect(screen.getByDisplayValue('Київ, вул. Анни Ахматової, 9')).toBeInTheDocument();
		expect(screen.getByText('Сільпо Київ')).toBeInTheDocument();
		expect(screen.getByText('Регулярна доставка (продукти та свіжі товари)')).toBeInTheDocument();
		expect(screen.getByRole('radio')).toHaveAttribute('value', 'DeliveryHome');

		await screen.getByRole('button', { name: 'Зберегти налаштування' }).click();
		expect(screen.getByText('Налаштування збережено')).toBeInTheDocument();
		expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/profile?delivery_address='));
	});

	it('filters branches to a 15 km radius around the browser location', async () => {
		saveProfilePreferences({ address: '', preferredBranchIds: [] });
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: async () => ({
				profile: { name: 'Олексій', phone: null, email: null },
				loyalty: { bonus_balance: 0, bonus_earned: 0 },
				addresses: [],
				delivery_types: [],
				branches: [
					{
						branch_id: 'nearby',
						name: 'Сільпо поруч',
						display_address: 'Київ',
						latitude: 50.45,
						longitude: 30.52,
						has_pickup: true,
					},
					{
						branch_id: 'far-away',
						name: 'Сільпо далеко',
						display_address: 'Львів',
						latitude: 49.84,
						longitude: 24.03,
						has_pickup: true,
					},
				],
			}),
		});
		vi.stubGlobal('fetch', fetchMock);
		vi.stubGlobal('navigator', {
			geolocation: {
				getCurrentPosition: (success: PositionCallback) =>
					success({ coords: { latitude: 50.45, longitude: 30.52 } } as GeolocationPosition),
			},
		});

		render(ProfilePage);

		await waitFor(() => expect(screen.getByText('Сільпо поруч')).toBeInTheDocument());
		expect(screen.queryByText('Сільпо далеко')).not.toBeInTheDocument();
	});
});
