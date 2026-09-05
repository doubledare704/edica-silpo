<script lang="ts">
	/**
	 * StoreSelector — picks the Silpo branch nearest to the user's address.
	 *
	 * Behaviour:
	 *   • Toggle button shows the currently selected store.
	 *   • Dropdown panel has an address input; search queries
	 *     GET /api/stores/nearest and lists up to 10 nearest branches.
	 *   • Choosing a branch persists it to localStorage via shared state.
	 */

	import { formatStoreLabel, selectedStore, selectStore } from '$lib/selectedStore.svelte';

	const BACKEND_URL = 'http://localhost:8000';
	const SEARCH_LIMIT = 10;

	interface StoreOption {
		branch_id: string;
		name: string;
		city: string | null;
		address: string | null;
		display_address: string;
		distance_km: number | null;
		has_pickup: boolean;
	}

	interface SavedAddress {
		address_id: string;
		label: string | null;
		text: string;
	}

	let open = $state(false);
	let query = $state('');
	let options: StoreOption[] = $state([]);
	let savedAddresses: SavedAddress[] = $state([]);
	let savedLoaded = false;
	let searching = $state(false);
	let searchError: string | null = $state(null);
	let searched = $state(false);
	let resolvedAddress: string | null = $state(null);

	async function loadSaved() {
		if (savedLoaded) return;
		savedLoaded = true;
		try {
			const response = await fetch(`${BACKEND_URL}/api/stores/saved-addresses`);
			if (!response.ok) return;
			savedAddresses = (await response.json()) as SavedAddress[];
		} catch {
			savedAddresses = [];
		}
	}

	function toggle() {
		open = !open;
		if (open) void loadSaved();
	}

	async function search() {
		const text = query.trim();
		if (!text || searching) return;
		searching = true;
		searchError = null;
		resolvedAddress = null;
		try {
			const response = await fetch(
				`${BACKEND_URL}/api/stores/nearest?address=${encodeURIComponent(text)}&limit=${SEARCH_LIMIT}`,
			);
			if (!response.ok) throw new Error(`HTTP ${response.status}`);
			const data = (await response.json()) as {
				resolved_address?: string;
				stores?: StoreOption[];
			};
			options = data.stores ?? [];
			resolvedAddress = data.resolved_address ?? null;
			searched = true;
		} catch {
			searchError = "Не вдалося знайти магазини. Перевірте з'єднання.";
		} finally {
			searching = false;
		}
	}

	function searchSaved(address: SavedAddress) {
		query = address.text;
		void search();
	}

	function choose(option: StoreOption) {
		selectStore({
			branchId: option.branch_id || null,
			name: option.name,
			address: option.display_address || option.name,
		});
		open = false;
	}

	function handleWindowKeyDown(e: KeyboardEvent) {
		if (e.key === 'Escape') open = false;
	}
</script>

<svelte:window onkeydown={handleWindowKeyDown} />

<div class="relative w-full">
	<button
		data-testid="store-selector-toggle"
		type="button"
		onclick={() => toggle()}
		aria-expanded={open}
		aria-haspopup="listbox"
		title={formatStoreLabel(selectedStore.name, selectedStore.address)}
		class="w-full bg-surface-container-low border border-app-border rounded-full px-3 py-1.5 flex justify-between items-center gap-1.5 cursor-pointer hover:bg-surface-container transition-colors active:scale-[0.99]"
	>
		<span class="flex items-center gap-1.5 overflow-hidden">
			<span aria-hidden="true">📍</span>
			<span class="text-[12px] leading-4 font-medium text-on-surface truncate">
				{formatStoreLabel(selectedStore.name, selectedStore.address)}
			</span>
		</span>
		<span
			class="material-symbols-outlined text-[16px] text-on-surface-variant shrink-0 transition-transform {open
				? 'rotate-180'
				: ''}"
			aria-hidden="true">arrow_drop_down</span
		>
	</button>

	{#if open}
		<div
			data-testid="store-selector-panel"
			class="absolute left-0 right-0 md:left-auto md:right-0 md:w-96 top-full mt-2 z-50 bg-app-card border border-app-border rounded-[24px] shadow-bento-hover p-4 space-y-3"
		>
			<div class="flex gap-2">
				<input
					data-testid="store-search-input"
					type="text"
					bind:value={query}
					onkeydown={(e) => {
						if (e.key === 'Enter') void search();
					}}
					placeholder="Введіть вашу адресу…"
					aria-label="Ваша адреса для пошуку найближчого Сільпо"
					class="flex-1 min-w-0 bg-surface border border-app-border rounded-full px-4 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-app-primary focus:border-transparent placeholder:text-on-surface-variant/70"
				/>
				<button
					data-testid="store-search-button"
					type="button"
					onclick={() => void search()}
					disabled={!query.trim() || searching}
					class="shrink-0 rounded-full bg-app-primary px-4 py-2 text-sm font-semibold text-white hover:bg-app-primary-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed active:scale-95"
				>
					{searching ? 'Пошук…' : 'Знайти'}
				</button>
			</div>

			{#if savedAddresses.length > 0}
				<div class="space-y-1">
					<p class="text-xs text-on-surface-variant font-semibold uppercase tracking-wide">
						Мої адреси в Сільпо
					</p>
					{#each savedAddresses as saved (saved.address_id)}
						<button
							data-testid="saved-address-option"
							type="button"
							onclick={() => searchSaved(saved)}
							class="w-full text-left rounded-2xl px-3 py-2 hover:bg-surface-container-low transition-colors"
						>
							<span class="block text-sm font-semibold text-on-surface truncate">
								{#if saved.label}{saved.label} · {/if}{saved.text}
							</span>
						</button>
					{/each}
				</div>
			{/if}

			{#if searchError}
				<p data-testid="store-search-error" class="text-error text-sm">⚠️ {searchError}</p>
			{:else if searching}
				<p class="text-on-surface-variant text-sm text-center">Шукаємо найближчі магазини…</p>
			{:else if searched && options.length === 0}
				<p class="text-on-surface-variant text-sm text-center">Поруч нічого не знайдено.</p>
			{:else if options.length > 0}
				{#if resolvedAddress}
					<p data-testid="resolved-address" class="text-on-surface-variant text-xs truncate">
						Поруч з: {resolvedAddress}
					</p>
				{/if}
				<ul class="max-h-72 overflow-y-auto space-y-1" role="listbox" aria-label="Найближчі магазини">
					{#each options as option (option.branch_id)}
						<li>
							<button
								data-testid="store-option"
								type="button"
								role="option"
								aria-selected={option.branch_id === selectedStore.branchId}
								onclick={() => choose(option)}
								class="w-full text-left rounded-2xl px-3 py-2 hover:bg-surface-container-low transition-colors flex items-center justify-between gap-2"
							>
								<span class="min-w-0">
									<span class="block text-sm font-semibold text-on-surface truncate">
										{option.name}
									</span>
									<span class="block text-xs text-on-surface-variant truncate">
										{option.display_address}
										{#if option.has_pickup}
											· Самовивіз
										{/if}
									</span>
								</span>
								{#if option.distance_km !== null}
									<span class="shrink-0 text-xs font-semibold text-primary">
										{option.distance_km} км
									</span>
								{/if}
							</button>
						</li>
					{/each}
				</ul>
			{:else if !searched}
				<p class="text-on-surface-variant/70 text-xs text-center">
					Введіть адресу, щоб побачити до {SEARCH_LIMIT} найближчих Сільпо.
				</p>
			{/if}
		</div>
	{/if}
</div>
