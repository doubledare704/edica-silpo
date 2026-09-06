<script lang="ts">
	import { itemEmoji, itemsCountLabel, type CartItem } from '$lib/cart';

	/**
	 * CartItemsPreview — fast preview of picked items (Stitch: "Швидкий перегляд").
	 * Horizontal scroll of item cards + expandable full list via the "Усі" tile.
	 *
	 * Props:
	 *   items — normalized cart items from SSE `node_complete`
	 */

	interface Props {
		items: CartItem[];
	}

	let { items }: Props = $props();

	let expanded = $state(false);
	const PREVIEW_LIMIT = 4;

	let previewItems = $derived(items.slice(0, PREVIEW_LIMIT));
	let hasMore = $derived(items.length > PREVIEW_LIMIT);

	function toggle() {
		expanded = !expanded;
	}
</script>

{#if items.length > 0}
	<div data-testid="cart-items-preview" class="mb-6">
		<h4 class="text-[14px] leading-5 font-semibold text-on-surface-variant mb-3">
			Швидкий перегляд ({itemsCountLabel(items.length)})
		</h4>

		<div class="flex gap-3 overflow-x-auto hide-scrollbar pt-2.5 pb-2 px-1">
			{#each previewItems as item (item.id ?? item.title)}
				<div
					class="relative flex w-20 shrink-0 flex-col items-center gap-2 rounded-xl border border-app-border bg-surface-container-lowest p-2"
				>
					{#if item.is_private_label}
						<span
							class="absolute -top-2 -right-1 z-10 rounded-full bg-secondary px-1.5 py-0.5 text-[9px] font-bold text-white shadow-sm"
							>ЗАМІНА</span
						>
					{/if}
					<div
						class="flex h-12 w-12 items-center justify-center rounded-lg bg-surface-container text-2xl"
						aria-hidden="true"
					>
						{itemEmoji(item.title)}
					</div>
					<span class="w-full truncate text-center text-[12px] leading-4 font-medium text-on-surface">
						{item.title}
					</span>
					<span class="text-center text-[11px] leading-4 text-on-surface-variant">
						{item.quantity} × {item.price.toFixed(2)}
					</span>
				</div>
			{/each}

			{#if hasMore || items.length > 0}
				<button
					type="button"
					data-testid="cart-items-toggle"
					onclick={toggle}
					aria-expanded={expanded}
					aria-label={expanded ? 'Згорнути список товарів' : 'Переглянути усі товари'}
					class="flex w-20 shrink-0 cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-app-border bg-surface-container-low p-2 text-on-surface-variant transition-colors hover:bg-surface-container"
				>
					<span class="material-symbols-outlined" aria-hidden="true">
						{expanded ? 'expand_less' : 'more_horiz'}
					</span>
					<span class="text-center text-[12px] leading-4 font-medium">
						{expanded ? 'Сховати' : 'Усі'}
					</span>
				</button>
			{/if}
		</div>

		{#if expanded}
			<ul data-testid="cart-items-full" class="mt-2 flex flex-col gap-2">
				{#each items as item (item.id ?? item.title)}
					<li
						class="flex items-center gap-3 rounded-xl border border-app-border bg-surface-container-lowest px-3 py-2.5"
					>
						<div
							class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface-container text-xl"
							aria-hidden="true"
						>
							{itemEmoji(item.title)}
						</div>
						<div class="min-w-0 flex-1">
							<div class="flex items-center gap-2">
								<p class="truncate text-sm font-semibold text-on-surface">{item.title}</p>
								{#if item.is_private_label}
									<span
										class="shrink-0 rounded-full bg-secondary px-1.5 py-0.5 text-[9px] font-bold text-white"
										>ЗАМІНА</span
									>
								{/if}
							</div>
							<p class="text-xs text-on-surface-variant">
								{item.quantity} × {item.price.toFixed(2)} грн
							</p>
						</div>
						<span class="shrink-0 text-sm font-bold text-on-surface">
							{item.line_total.toFixed(2)}
						</span>
					</li>
				{/each}
			</ul>
		{/if}
	</div>
{/if}
