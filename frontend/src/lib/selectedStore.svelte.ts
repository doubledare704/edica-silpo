export interface SelectedStore {
	branchId: string | null;
	name: string;
	address: string;
}

const STORAGE_KEY = 'edica:selected-store';

export const DEFAULT_STORE: SelectedStore = {
	branchId: null,
	name: 'Сільпо',
	address: 'Київ, Дніпровська набережна, 14',
};

function loadInitial(): SelectedStore {
	if (typeof localStorage === 'undefined') return { ...DEFAULT_STORE };
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (raw) {
			const parsed = JSON.parse(raw) as Partial<SelectedStore>;
			if (parsed.address) {
				return {
					branchId: parsed.branchId ?? null,
					name: parsed.name ?? 'Сільпо',
					address: parsed.address,
				};
			}
		}
	} catch {
		// Corrupted storage — fall through to the default store.
	}
	return { ...DEFAULT_STORE };
}

export const selectedStore = $state<SelectedStore>(loadInitial());

export function formatStoreLabel(name: string, address: string): string {
	const cleanName = name.trim();
	const cleanAddress = address.trim();
	if (!cleanName) return cleanAddress;
	if (!cleanAddress) return cleanName;
	if (cleanAddress.toLowerCase().startsWith(cleanName.toLowerCase())) return cleanAddress;
	return `${cleanName}: ${cleanAddress}`;
}

export function selectStore(store: SelectedStore): void {
	selectedStore.branchId = store.branchId;
	selectedStore.name = store.name;
	selectedStore.address = store.address;
	if (typeof localStorage === 'undefined') return;
	try {
		localStorage.setItem(
			STORAGE_KEY,
			JSON.stringify({
				branchId: selectedStore.branchId,
				name: selectedStore.name,
				address: selectedStore.address,
			}),
		);
	} catch {
		// Storage unavailable (private mode) — keep the in-memory selection.
	}
}
