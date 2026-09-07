<script lang="ts">
	import { itemEmoji, itemKey, type CartItem } from '$lib/cart';

	/**
	 * CartDetailList — full cart contents for the `/cart` page.
	 * Larger product images and per-item details (quantity, unit price, line total).
	 *
	 * Props:
	 *   items — picked products from the shared cart store
	 */

	interface Props {
		items: CartItem[];
	}

	let { items }: Props = $props();
</script>

<ul data-testid="cart-detail-list" class="flex flex-col gap-3">
	{#each items as item, index (itemKey(item, index))}
		<li
			data-testid="cart-detail-item"
			class="flex items-center gap-4 rounded-2xl border border-app-border bg-surface-container-lowest p-4"
		>
			<div
				class="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-surface-container text-4xl"
				aria-hidden="true"
			>
				{#if item.image_url}
					<img src={item.image_url} alt="" loading="lazy" class="h-full w-full object-cover" />
				{:else}
					{itemEmoji(item.title)}
				{/if}
			</div>
			<div class="min-w-0 flex-1">
				<div class="flex items-center gap-2">
					<p class="truncate text-base font-semibold text-on-surface">{item.title}</p>
					{#if item.is_private_label}
						<span
							class="shrink-0 rounded-full bg-secondary px-1.5 py-0.5 text-[9px] font-bold text-white"
							>ЗАМІНА</span
						>
					{/if}
				</div>
				<p class="mt-1 text-sm text-on-surface-variant">
					Кількість: {item.quantity} × {item.price.toFixed(2)} грн
				</p>
				<p class="mt-0.5 text-sm font-bold text-on-surface">
					Сума: {item.line_total.toFixed(2)} грн
				</p>
			</div>
		</li>
	{/each}
</ul>
