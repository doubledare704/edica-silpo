<script lang="ts">
	import CartDetailList from '$lib/components/CartDetailList.svelte';
	import { cartStore } from '$lib/cartStore.svelte';
	import { itemsCountLabel } from '$lib/cart';

	let itemCount = $derived(cartStore.items.reduce((sum, item) => sum + item.quantity, 0));
</script>

<svelte:head>
	<title>Кошик — Edica @ Сільпо</title>
</svelte:head>

<main class="flex-1 max-w-[1280px] mx-auto w-full px-4 md:px-10 py-6 flex flex-col gap-4">
	{#if cartStore.items.length === 0}
		<section
			data-testid="cart-empty"
			class="w-full mx-auto bg-app-card rounded-[24px] p-6 border border-app-border shadow-bento flex flex-col items-center text-center"
		>
			<span class="material-symbols-outlined text-5xl text-on-surface-variant/50" aria-hidden="true"
				>shopping_bag</span
			>
			<h1 class="mt-4 text-[20px] leading-7 font-semibold text-on-surface">Кошик порожній</h1>
			<p class="mt-2 text-sm text-on-surface-variant">
				Попросіть Edica зібрати кошик — і товари з'являться тут.
			</p>
			<a
				href="/"
				class="mt-6 inline-flex items-center gap-2 bg-app-primary hover:bg-app-primary-dark text-white font-semibold text-base py-3 px-6 rounded-xl transition-colors active:scale-[0.98]"
			>
				<span class="material-symbols-outlined text-[20px]" aria-hidden="true">auto_awesome</span>
				<span>До асистента</span>
			</a>
		</section>
	{:else}
		<section
			aria-label="Кошик"
			data-testid="cart-page"
			class="w-full mx-auto bg-app-card rounded-[24px] p-6 border border-app-border shadow-bento flex flex-col"
		>
			<h1 class="text-[24px] leading-8 font-semibold text-on-surface">Кошик</h1>
			<p data-testid="cart-count" class="mt-1 text-sm text-on-surface-variant">
				{itemsCountLabel(itemCount)}
			</p>
			{#if cartStore.summary}
				<p class="mt-3 text-on-surface text-base leading-relaxed">{cartStore.summary}</p>
			{/if}

			<div class="mt-4">
				<CartDetailList items={cartStore.items} />
			</div>

			<div class="mt-4 flex items-center justify-between border-t border-app-border pt-4">
				<span class="text-on-surface-variant text-base">Разом</span>
				<span class="text-[24px] leading-8 font-bold text-on-surface">
					<span data-testid="cart-total">{cartStore.totalPrice.toFixed(2)}</span>
					<span class="font-normal text-[18px] text-on-surface-variant">грн</span>
				</span>
			</div>

			{#if cartStore.cartUrl}
				<a
					href={cartStore.cartUrl}
					target="_blank"
					rel="noopener noreferrer"
					data-testid="checkout-link"
					class="mt-4 w-full bg-app-primary hover:bg-app-primary-dark text-white font-semibold text-base py-3.5 px-4 rounded-xl flex justify-center items-center gap-2 transition-colors active:scale-[0.98] shadow-md shadow-app-primary/20"
				>
					<span>Перейти до оформлення</span>
					<span class="material-symbols-outlined text-[20px]" aria-hidden="true"
						>arrow_forward</span
					>
				</a>
			{/if}
		</section>
	{/if}
</main>
