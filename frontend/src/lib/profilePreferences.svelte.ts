export type DeliveryPreference = 'DeliveryHome' | 'SelfPickup' | 'NovaPoshta' | string;

export interface ProfilePreferences {
	address: string;
	deliveryType: DeliveryPreference;
	preferredBranchIds: string[];
}

const STORAGE_KEY = 'edica:profile-preferences';

const DEFAULT_PREFERENCES: ProfilePreferences = {
	address: '',
	deliveryType: 'DeliveryHome',
	preferredBranchIds: [],
};

function loadInitial(): ProfilePreferences {
	if (typeof localStorage === 'undefined') return { ...DEFAULT_PREFERENCES };
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (!raw) return { ...DEFAULT_PREFERENCES };
		const parsed = JSON.parse(raw) as Partial<ProfilePreferences>;
		return {
			address: typeof parsed.address === 'string' ? parsed.address : '',
			deliveryType: typeof parsed.deliveryType === 'string' ? parsed.deliveryType : 'DeliveryHome',
			preferredBranchIds: Array.isArray(parsed.preferredBranchIds)
				? parsed.preferredBranchIds.filter((id): id is string => typeof id === 'string')
				: [],
		};
	} catch {
		return { ...DEFAULT_PREFERENCES };
	}
}

export const profilePreferences = $state<ProfilePreferences>(loadInitial());

export function saveProfilePreferences(next: Partial<ProfilePreferences>): void {
	profilePreferences.address = next.address ?? profilePreferences.address;
	profilePreferences.deliveryType = next.deliveryType ?? profilePreferences.deliveryType;
	profilePreferences.preferredBranchIds = [
		...(next.preferredBranchIds ?? profilePreferences.preferredBranchIds),
	];
	if (typeof localStorage === 'undefined') return;
	try {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(profilePreferences));
	} catch {
		// Storage unavailable (private mode) — keep the in-memory preference.
	}
}
