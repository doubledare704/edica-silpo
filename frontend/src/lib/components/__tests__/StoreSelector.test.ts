import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import StoreSelector from '../StoreSelector.svelte';
import { DEFAULT_STORE, selectStore } from '$lib/selectedStore.svelte';

const MOCK_STORES = [
	{
		branch_id: 'bran-2',
		name: 'Сільпо Київ (позняки)',
		city: 'Київ',
		address: 'вул. Анни Ахматової, 9',
		display_address: 'Київ, вул. Анни Ахматової, 9',
		distance_km: 0.0,
		has_pickup: true,
	},
	{
		branch_id: 'bran-1',
		name: 'Сільпо Львів (центр)',
		city: 'Львів',
		address: 'вул. Степана Бандери, 3',
		display_address: 'Львів, вул. Степана Бандери, 3',
		distance_km: 467.8,
		has_pickup: true,
	},
];

function mockFetchOk() {
	return vi.fn(async () => ({
		ok: true,
		json: async () => ({ stores: MOCK_STORES }),
	}));
}

const MOCK_SAVED = [{ address_id: 'addr-1', label: 'Дім', text: 'Київ, вул. Анни Ахматової, 9' }];

function mockFetchRouter() {
	return vi.fn(async (url: unknown) => {
		if (String(url).includes('/api/stores/saved-addresses')) {
			return { ok: true, json: async () => MOCK_SAVED };
		}
		return {
			ok: true,
			json: async () => ({
				resolved_address: 'Київ, вул. Анни Ахматової, 9',
				stores: MOCK_STORES,
			}),
		};
	});
}

function stubMemoryStorage() {
	let store: Record<string, string> = {};
	vi.stubGlobal('localStorage', {
		getItem: (key: string) => store[key] ?? null,
		setItem: (key: string, value: string) => {
			store[key] = value;
		},
		removeItem: (key: string) => {
			delete store[key];
		},
		clear: () => {
			store = {};
		},
	});
}

function readStored() {
	return JSON.parse(
		(globalThis as { localStorage: Storage }).localStorage.getItem('edica:selected-store') ?? '{}',
	);
}

describe('StoreSelector', () => {
	beforeEach(() => {
		stubMemoryStorage();
		(globalThis as { localStorage: Storage }).localStorage.clear();
		selectStore({ ...DEFAULT_STORE });
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('renders the currently selected store in the toggle', () => {
		render(StoreSelector);
		expect(screen.getByTestId('store-selector-toggle')).toHaveTextContent(
			'Київ, Дніпровська набережна, 14',
		);
		expect(screen.queryByTestId('store-selector-panel')).not.toBeInTheDocument();
	});

	it('searches by address and lists the nearest stores', async () => {
		render(StoreSelector);
		await fireEvent.click(screen.getByTestId('store-selector-toggle'));
		expect(screen.getByTestId('store-selector-panel')).toBeInTheDocument();

		vi.stubGlobal('fetch', mockFetchOk());
		await fireEvent.input(screen.getByTestId('store-search-input'), {
			target: { value: 'Київ, Ахматової 9' },
		});
		await fireEvent.click(screen.getByTestId('store-search-button'));

		await vi.waitFor(() => {
			expect(screen.getAllByTestId('store-option')).toHaveLength(2);
		});
		const fetchMock = fetch as ReturnType<typeof vi.fn>;
		expect(fetchMock).toHaveBeenCalledOnce();
		expect(String(fetchMock.mock.calls[0][0])).toContain('/api/stores/nearest');
		expect(String(fetchMock.mock.calls[0][0])).toContain('limit=10');
	});

	it('selecting a store updates the toggle and persists it', async () => {
		render(StoreSelector);
		await fireEvent.click(screen.getByTestId('store-selector-toggle'));

		vi.stubGlobal('fetch', mockFetchOk());
		await fireEvent.input(screen.getByTestId('store-search-input'), {
			target: { value: 'Київ' },
		});
		await fireEvent.click(screen.getByTestId('store-search-button'));

		await vi.waitFor(() => {
			expect(screen.getAllByTestId('store-option')).toHaveLength(2);
		});
		await fireEvent.click(screen.getAllByTestId('store-option')[0]);

		expect(screen.getByTestId('store-selector-toggle')).toHaveTextContent(
			'вул. Анни Ахматової, 9',
		);
		expect(readStored()).toMatchObject({ branchId: 'bran-2' });
	});

	it('loads saved addresses on open and searches from one', async () => {
		render(StoreSelector);
		const fetchMock = mockFetchRouter();
		vi.stubGlobal('fetch', fetchMock);
		await fireEvent.click(screen.getByTestId('store-selector-toggle'));

		await vi.waitFor(() => {
			expect(screen.getByTestId('saved-address-option')).toHaveTextContent('Дім');
		});
		await fireEvent.click(screen.getByTestId('saved-address-option'));

		await vi.waitFor(() => {
			expect(screen.getAllByTestId('store-option')).toHaveLength(2);
		});
		expect(screen.getByTestId('resolved-address')).toHaveTextContent(
			'Київ, вул. Анни Ахматової, 9',
		);
		const nearestCall = fetchMock.mock.calls.find((call) =>
			String(call[0]).includes('/api/stores/nearest'),
		);
		expect(nearestCall).toBeDefined();
	});

	it('does not duplicate the label when name already contains the address', async () => {
		render(StoreSelector);
		const duplicate = {
			branch_id: 'b-dup',
			name: 'Київ, вул. Мишуги Олександра, 4',
			city: 'Київ',
			address: 'вул. Мишуги Олександра, 4',
			display_address: 'Київ, вул. Мишуги Олександра, 4',
			distance_km: 1.2,
			has_pickup: false,
		};
		vi.stubGlobal('fetch', async () => ({ ok: true, json: async () => ({ stores: [duplicate] }) }));
		await fireEvent.click(screen.getByTestId('store-selector-toggle'));
		await fireEvent.input(screen.getByTestId('store-search-input'), {
			target: { value: 'Мишуги' },
		});
		await fireEvent.click(screen.getByTestId('store-search-button'));

		await vi.waitFor(() => {
			expect(screen.getAllByTestId('store-option')).toHaveLength(1);
		});
		await fireEvent.click(screen.getByTestId('store-option'));

		const toggle = screen.getByTestId('store-selector-toggle');
		expect(toggle).toHaveTextContent('Київ, вул. Мишуги Олександра, 4');
		expect(toggle.textContent?.match(/Мишуги/g)).toHaveLength(1);
	});

	it('shows an error message when the search fails', async () => {
		render(StoreSelector);
		await fireEvent.click(screen.getByTestId('store-selector-toggle'));

		vi.stubGlobal(
			'fetch',
			vi.fn(async () => {
				throw new Error('offline');
			}),
		);
		await fireEvent.input(screen.getByTestId('store-search-input'), {
			target: { value: 'Київ' },
		});
		await fireEvent.click(screen.getByTestId('store-search-button'));

		await vi.waitFor(() => {
			expect(screen.getByTestId('store-search-error')).toBeInTheDocument();
		});
	});
});
