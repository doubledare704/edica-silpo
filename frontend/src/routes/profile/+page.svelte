<script lang="ts">
	import { onMount } from 'svelte';
	import { getBackendUrl } from '$lib/config';
	import { profilePreferences, saveProfilePreferences } from '$lib/profilePreferences.svelte';
	import { formatStoreLabel, selectedStore, selectStore } from '$lib/selectedStore.svelte';

	interface Profile {
		name: string | null;
		phone: string | null;
		email: string | null;
	}

	interface Loyalty {
		bonus_balance: number;
		bonus_earned: number;
	}

	interface Address {
		address_id: string;
		label: string | null;
		text: string;
	}

	interface DeliveryType {
		type: string;
		description: string | null;
		min_order: number | null;
	}

	interface Branch {
		branch_id: string;
		name: string;
		display_address: string;
		latitude: number | null;
		longitude: number | null;
		has_pickup: boolean;
		has_nova_poshta: boolean;
	}

	interface ProfileOverview {
		profile: Profile;
		loyalty: Loyalty;
		addresses: Address[];
		delivery_types: DeliveryType[];
		branches: Branch[];
	}

	let overview: ProfileOverview | null = $state(null);
	let address = $state('');
	let deliveryType = $state('DeliveryHome');
	let preferredBranchIds = $state<string[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let saved = $state(false);
	let searchingBranches = $state(false);

	function formatPrice(value: number): string {
		return new Intl.NumberFormat('uk-UA', {
			style: 'currency',
			currency: 'UAH',
			maximumFractionDigits: 0,
		}).format(value);
	}

	function selectSavedAddress(savedAddress: Address): void {
		address = savedAddress.text;
	}

	function toggleBranch(branchId: string): void {
		preferredBranchIds = preferredBranchIds.includes(branchId)
			? preferredBranchIds.filter((id) => id !== branchId)
			: [...preferredBranchIds, branchId];
	}

	function markerStyle(branch: Branch, index: number): string {
		const branches = overview?.branches ?? [];
		const latitudes = branches.map((entry) => entry.latitude).filter((value): value is number => value !== null);
		const longitudes = branches.map((entry) => entry.longitude).filter((value): value is number => value !== null);
		if (!latitudes.length || !longitudes.length || branch.latitude === null || branch.longitude === null) {
			return `left: ${25 + (index % 3) * 25}%; top: ${28 + (index % 2) * 34}%;`;
		}
		const minLat = Math.min(...latitudes);
		const maxLat = Math.max(...latitudes);
		const minLng = Math.min(...longitudes);
		const maxLng = Math.max(...longitudes);
		const x = maxLng === minLng ? 50 : 15 + ((branch.longitude - minLng) / (maxLng - minLng)) * 70;
		const y = maxLat === minLat ? 50 : 78 - ((branch.latitude - minLat) / (maxLat - minLat)) * 56;
		return `left: ${x}%; top: ${y}%;`;
	}

	async function loadProfile(): Promise<void> {
		loading = true;
		error = null;
		try {
			const queryAddress = profilePreferences.address || selectedStore.address;
			const response = await fetch(
				`${getBackendUrl()}/api/profile?delivery_address=${encodeURIComponent(queryAddress)}`,
			);
			if (!response.ok) throw new Error(`HTTP ${response.status}`);
			overview = (await response.json()) as ProfileOverview;
			const mcpAddress = overview.addresses[0]?.text ?? '';
			address = profilePreferences.address || mcpAddress || selectedStore.address;
			deliveryType = profilePreferences.deliveryType || overview.delivery_types[0]?.type || 'DeliveryHome';
			preferredBranchIds = [...profilePreferences.preferredBranchIds];
		} catch {
			error = 'Не вдалося завантажити профіль. Перевірте з’єднання.';
		} finally {
			loading = false;
		}
	}

	async function searchBranches(): Promise<void> {
		const query = address.trim();
		if (!query || searchingBranches) return;
		searchingBranches = true;
		try {
			const response = await fetch(
				`${getBackendUrl()}/api/stores/nearest?address=${encodeURIComponent(query)}&limit=10`,
			);
			if (!response.ok) throw new Error(`HTTP ${response.status}`);
			const data = (await response.json()) as { stores?: Branch[] };
			if (overview) overview.branches = data.stores ?? [];
		} catch {
			error = 'Не вдалося оновити список магазинів поруч.';
		} finally {
			searchingBranches = false;
		}
	}

	function saveSettings(): void {
		saveProfilePreferences({ address: address.trim(), deliveryType, preferredBranchIds });
		const preferredBranch = overview?.branches.find((branch) => branch.branch_id === preferredBranchIds[0]);
		selectStore({
			branchId: preferredBranch?.branch_id ?? selectedStore.branchId,
			name: preferredBranch?.name ?? selectedStore.name,
			address: address.trim() || selectedStore.address,
		});
		saved = true;
		window.setTimeout(() => (saved = false), 2400);
	}

	onMount(() => {
		void loadProfile();
	});
</script>

<svelte:head>
	<title>Профіль — Edica @ Сільпо</title>
</svelte:head>

<main class="w-full max-w-[1280px] mx-auto px-4 md:px-10 py-8 md:py-10 space-y-8">
	{#if loading}
		<div class="space-y-4" data-testid="profile-loading">
			<div class="h-36 rounded-[28px] bg-white border border-app-border animate-pulse"></div>
			<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
				<div class="h-96 rounded-[28px] bg-white border border-app-border animate-pulse"></div>
				<div class="h-96 rounded-[28px] bg-white border border-app-border animate-pulse"></div>
			</div>
		</div>
	{:else if error && !overview}
		<section class="rounded-[28px] bg-white border border-app-border p-8 text-center" data-testid="profile-error">
			<div class="mx-auto w-12 h-12 rounded-full bg-orange-100 text-app-primary flex items-center justify-center">
				<span class="material-symbols-outlined" aria-hidden="true">person_off</span>
			</div>
			<h1 class="mt-4 text-xl font-semibold">Профіль недоступний</h1>
			<p class="mt-2 text-sm text-[#6e6e73]">{error}</p>
			<button
				type="button"
				onclick={() => void loadProfile()}
				class="mt-5 rounded-full bg-app-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-app-primary-dark"
				>Спробувати ще</button>
		</section>
	{:else if overview}
		<div class="flex items-end justify-between gap-4">
			<div>
				<p class="text-sm font-semibold text-app-primary uppercase tracking-[0.16em]">Мій простір</p>
				<h1 class="mt-2 text-3xl md:text-4xl font-semibold tracking-tight text-app-text">Профіль</h1>
				<p class="mt-2 text-sm md:text-base text-[#6e6e73]">Налаштуйте адресу, доставку та магазини для перевірки асортименту.</p>
			</div>
			{#if saved}
				<p class="rounded-full bg-green-100 px-4 py-2 text-sm font-semibold text-green-800" data-testid="profile-saved">Налаштування збережено</p>
			{/if}
		</div>

		<section class="grid grid-cols-1 md:grid-cols-12 gap-4">
			<div class="md:col-span-8 rounded-[28px] bg-white border border-app-border p-6 shadow-bento">
				<div class="flex items-start gap-4">
					<div class="w-14 h-14 rounded-full bg-app-primary-soft text-app-primary flex items-center justify-center shrink-0">
						<span class="material-symbols-outlined text-3xl" aria-hidden="true">person</span>
					</div>
					<div class="min-w-0">
						<h2 class="text-2xl font-semibold truncate">{overview.profile.name || 'Покупець'}</h2>
						<p class="mt-1 text-sm text-[#6e6e73]">{overview.profile.phone || 'Телефон не вказано'} · {overview.profile.email || 'Email не вказано'}</p>
					</div>
				</div>
				<div class="mt-6 grid grid-cols-2 gap-3">
					<div class="rounded-2xl bg-[#fff8f1] p-4">
						<p class="text-xs font-semibold uppercase tracking-wide text-[#8b8b91]">Балабонуси</p>
						<p class="mt-2 text-2xl font-semibold text-app-primary">{overview.loyalty.bonus_balance.toFixed(2)}</p>
					</div>
					<div class="rounded-2xl bg-[#f8f7f2] p-4">
						<p class="text-xs font-semibold uppercase tracking-wide text-[#8b8b91]">Нараховано</p>
						<p class="mt-2 text-2xl font-semibold">{overview.loyalty.bonus_earned.toFixed(2)}</p>
					</div>
				</div>
			</div>
			<div class="md:col-span-4 rounded-[28px] bg-gradient-to-br from-[#ff6b00] to-[#ffb800] text-white p-6 shadow-bento flex flex-col justify-between">
				<div class="flex justify-between gap-3">
					<div>
						<p class="text-sm text-white/80">Поточний магазин</p>
						<h2 class="mt-2 text-xl font-semibold">{selectedStore.name}</h2>
					</div>
					<span class="material-symbols-outlined text-3xl" aria-hidden="true">storefront</span>
				</div>
				<p class="mt-8 text-sm leading-5 text-white/90">{formatStoreLabel(selectedStore.name, selectedStore.address)}</p>
			</div>
		</section>

		<section class="grid grid-cols-1 lg:grid-cols-2 gap-4">
			<div class="rounded-[28px] bg-white border border-app-border p-6 shadow-bento space-y-6">
				<div>
					<p class="text-sm text-[#6e6e73]">Доставка</p>
					<h2 class="text-2xl font-semibold">Ваші налаштування</h2>
				</div>
				<div class="space-y-2">
					<label for="profile-address" class="text-sm font-semibold">Адреса доставки</label>
					<div class="flex gap-2">
						<input
							id="profile-address"
							data-testid="profile-address-input"
							bind:value={address}
							placeholder="Київ, вул. Анни Ахматової, 9"
							class="min-w-0 flex-1 rounded-full border border-app-border bg-[#faf9f5] px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-app-primary"
						/>
						<button
							type="button"
							onclick={() => void searchBranches()}
							disabled={!address.trim() || searchingBranches}
							class="shrink-0 rounded-full bg-app-primary px-4 py-3 text-sm font-semibold text-white hover:bg-app-primary-dark disabled:opacity-50"
							>{searchingBranches ? 'Пошук…' : 'Знайти'}</button>
					</div>
					{#if overview.addresses.length > 0}
						<div class="space-y-1">
							<p class="text-xs font-semibold uppercase tracking-wide text-[#8b8b91]">Збережені в Сільпо</p>
							{#each overview.addresses as savedAddress (savedAddress.address_id)}
								<button type="button" onclick={() => selectSavedAddress(savedAddress)} class="block w-full rounded-xl px-3 py-2 text-left text-sm hover:bg-[#fff8f1]">
									{#if savedAddress.label}<span class="font-semibold">{savedAddress.label} · </span>{/if}{savedAddress.text}
								</button>
							{/each}
						</div>
					{/if}
				</div>

				<div class="space-y-3">
					<p class="text-sm font-semibold">Спосіб отримання</p>
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
						{#each overview.delivery_types as option (option.type)}
							<label class="flex cursor-pointer items-start gap-3 rounded-2xl border px-3 py-3 transition-colors {deliveryType === option.type ? 'border-app-primary bg-[#fff8f1]' : 'border-app-border hover:border-app-primary/50'}">
								<input type="radio" bind:group={deliveryType} value={option.type} class="mt-1 accent-[#ff6b00]" />
								<span>
									<span class="block text-sm font-semibold">{option.description || option.type}</span>
									{#if option.min_order !== null}<span class="block mt-1 text-xs text-[#6e6e73]">Від {formatPrice(option.min_order)}</span>{/if}
								</span>
							</label>
						{/each}
					</div>
				</div>

				<button type="button" onclick={saveSettings} class="w-full rounded-full bg-app-primary px-5 py-3 text-sm font-semibold text-white hover:bg-app-primary-dark" aria-label="Зберегти налаштування">
					<span class="material-symbols-outlined align-middle text-[18px]" aria-hidden="true">save</span>
					Зберегти налаштування
				</button>
			</div>

			<div class="rounded-[28px] bg-white border border-app-border p-6 shadow-bento space-y-5">
				<div>
					<p class="text-sm text-[#6e6e73]">Асортимент поруч</p>
					<h2 class="text-2xl font-semibold">Улюблені магазини</h2>
					<p class="mt-1 text-sm text-[#6e6e73]">Виберіть кілька — асистент зможе врахувати їх для замін.</p>
				</div>
				<div class="relative h-48 overflow-hidden rounded-2xl border border-[#eadfd5] bg-[#fff8f1]" data-testid="branches-map" aria-label="Карта магазинів Сільпо">
					<div class="absolute inset-0 opacity-40" style="background-image: linear-gradient(#e8cdb8 1px, transparent 1px), linear-gradient(90deg, #e8cdb8 1px, transparent 1px); background-size: 32px 32px;"></div>
					<div class="absolute inset-0 opacity-30" style="background: radial-gradient(circle at 25% 70%, #ffb800 0 1px, transparent 2px), radial-gradient(circle at 75% 25%, #ff6b00 0 1px, transparent 2px); background-size: 20px 20px;"></div>
					{#each overview.branches as branch, index (branch.branch_id)}
						<button
							type="button"
							aria-label="{branch.name}, {preferredBranchIds.includes(branch.branch_id) ? 'обрано' : 'не обрано'}"
							aria-pressed={preferredBranchIds.includes(branch.branch_id)}
							onclick={() => toggleBranch(branch.branch_id)}
							style={markerStyle(branch, index)}
							class="absolute z-10 flex h-8 w-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-4 border-white shadow-md transition-transform hover:scale-110 {preferredBranchIds.includes(branch.branch_id) ? 'bg-app-primary text-white' : 'bg-white text-app-primary'}"
						>
							<span class="material-symbols-outlined text-[17px]" aria-hidden="true">storefront</span>
						</button>
					{/each}
					<div class="absolute bottom-3 left-3 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-app-primary">{preferredBranchIds.length} обрано</div>
				</div>
				<div class="max-h-52 space-y-2 overflow-y-auto pr-1">
					{#each overview.branches as branch (branch.branch_id)}
						<button type="button" onclick={() => toggleBranch(branch.branch_id)} aria-pressed={preferredBranchIds.includes(branch.branch_id)} class="flex w-full items-center gap-3 rounded-2xl border px-3 py-3 text-left transition-colors {preferredBranchIds.includes(branch.branch_id) ? 'border-app-primary bg-[#fff8f1]' : 'border-app-border hover:border-app-primary/50'}">
							<span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full {preferredBranchIds.includes(branch.branch_id) ? 'bg-app-primary text-white' : 'bg-[#f8f7f2] text-app-primary'}">
								<span class="material-symbols-outlined text-[18px]" aria-hidden="true">storefront</span>
							</span>
							<span class="min-w-0 flex-1"><span class="block truncate text-sm font-semibold">{branch.name}</span><span class="block truncate text-xs text-[#6e6e73]">{branch.display_address}</span></span>
							<span class="material-symbols-outlined text-app-primary" aria-hidden="true">{preferredBranchIds.includes(branch.branch_id) ? 'check_circle' : 'add_circle'}</span>
						</button>
					{/each}
				</div>
			</div>
		</section>
	{/if}
</main>
