<script lang="ts">
	import '../app.css';
	import StoreSelector from '$lib/components/StoreSelector.svelte';
	import { cartStore } from '$lib/cartStore.svelte';
	import { page } from '$app/state';

	const { children } = $props();

	let cartCount = $derived(cartStore.items.reduce((sum, item) => sum + item.quantity, 0));
	let isCartPage = $derived(page.url.pathname === '/cart');
	let isAssistantPage = $derived(!isCartPage);
</script>

<div class="min-h-screen bg-app-bg text-app-text antialiased flex flex-col pb-24">
	<header class="bg-surface-container-lowest shadow-sm sticky top-0 z-40 w-full">
		<div
			class="flex justify-between items-center w-full px-4 md:px-10 py-4 max-w-[1280px] mx-auto"
		>
			<div class="text-[24px] leading-8 font-semibold text-primary flex items-center gap-1">
				<span
					class="material-symbols-outlined"
					aria-hidden="true"
					style="font-variation-settings: 'FILL' 1;">auto_awesome</span
				>
				Edica @ Сільпо
			</div>
			<div class="hidden md:block md:w-105">
				<StoreSelector />
			</div>
			<div class="text-[14px] leading-5 font-semibold text-on-surface-variant flex items-center gap-2">
				<span
					class="bg-surface-container p-2 rounded-full inline-flex"
					aria-hidden="true"
				>
					<span class="material-symbols-outlined text-primary">mic</span>
				</span>
			</div>
		</div>
		<div class="md:hidden px-4 pb-3">
			<StoreSelector />
		</div>
	</header>

	{@render children()}

	<nav
		class="fixed bottom-0 left-0 w-full h-16 bg-white border-t border-app-border shadow-[0_-2px_10px_rgba(0,0,0,0.04)] z-50 flex items-center"
		aria-label="Основна навігація"
	>
		<div class="w-full max-w-lg mx-auto grid grid-cols-4 h-full">
			<a
				href="/"
				data-testid="nav-assistant"
				aria-current={isAssistantPage ? 'page' : undefined}
				class="flex flex-col items-center justify-center gap-0.5 h-full focus:outline-none {isAssistantPage
					? 'text-app-primary'
					: 'text-[#6E6E73] hover:text-app-primary'} transition-colors"
			>
				<span
					class="flex items-center justify-center px-3 py-1 rounded-full {isAssistantPage
						? 'bg-app-primary-soft'
						: ''}"
				>
					<span
						class="material-symbols-outlined text-[22px]"
						aria-hidden="true"
						style="font-variation-settings: 'FILL' 1;">auto_awesome</span
					>
				</span>
				<span class="text-[11px] {isAssistantPage ? 'font-semibold' : 'font-medium'}">Асистент</span>
			</a>
			{#if cartCount > 0}
				<a
					href="/cart"
					data-testid="nav-cart"
					aria-current={isCartPage ? 'page' : undefined}
					aria-label="Кошик, {cartCount} товарів"
					class="flex flex-col items-center justify-center gap-0.5 h-full focus:outline-none {isCartPage
						? 'text-app-primary'
						: 'text-[#6E6E73] hover:text-app-primary'} transition-colors"
				>
					<span class="relative">
						<span class="material-symbols-outlined text-[22px]" aria-hidden="true"
							>shopping_bag</span
						>
						<span
							data-testid="cart-badge"
							class="absolute -top-1 -right-1.5 bg-app-primary text-white text-[10px] font-bold rounded-full h-4 min-w-4 px-0.5 flex items-center justify-center border-2 border-white leading-none"
							>{cartCount}</span
						>
					</span>
					<span class="text-[11px] {isCartPage ? 'font-semibold' : 'font-medium'}">Кошик</span>
				</a>
			{:else}
				<span
					data-testid="nav-cart"
					aria-disabled="true"
					aria-label="Кошик порожній"
					title="Кошик порожній"
					class="flex flex-col items-center justify-center gap-0.5 h-full text-[#6E6E73] opacity-40 cursor-not-allowed"
				>
					<span class="relative">
						<span class="material-symbols-outlined text-[22px]" aria-hidden="true"
							>shopping_bag</span
						>
					</span>
					<span class="text-[11px] font-medium">Кошик</span>
				</span>
			{/if}
			<button
				type="button"
				class="flex flex-col items-center justify-center gap-0.5 h-full text-[#6E6E73] hover:text-app-primary transition-colors focus:outline-none"
			>
				<span class="material-symbols-outlined text-[22px]" aria-hidden="true">sell</span>
				<span class="text-[11px] font-medium">Знижки</span>
			</button>
			<button
				type="button"
				class="flex flex-col items-center justify-center gap-0.5 h-full text-[#6E6E73] hover:text-app-primary transition-colors focus:outline-none"
			>
				<span class="material-symbols-outlined text-[22px]" aria-hidden="true">person</span>
				<span class="text-[11px] font-medium">Профіль</span>
			</button>
		</div>
	</nav>
</div>
