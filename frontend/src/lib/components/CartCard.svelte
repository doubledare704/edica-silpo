<script lang="ts">
	/**
	 * CartCard — finished-state basket hero (Stitch: "Поточний кошик").
	 *
	 * Props:
	 *   cartUrl      — Silpo cart share URL (or null if unavailable)
	 *   summary      — Ukrainian text summary from the agent
	 *   audioUrl     — path to TTS audio of the agent reply (or null)
	 *   totalPrice   — total cart price in UAH
	 *   isBudgetExceeded — whether the cart exceeded the requested budget
	 *   items        — picked products for the quick-preview list
	 */

	import CartItemsPreview from '$lib/components/CartItemsPreview.svelte';
	import type { CartItem } from '$lib/cart';

	interface Props {
		cartUrl: string | null;
		summary: string;
		audioUrl: string | null;
		totalPrice: number;
		isBudgetExceeded: boolean;
		items?: CartItem[];
	}

	let { cartUrl, summary, audioUrl, totalPrice, isBudgetExceeded, items = [] }: Props = $props();
	let audioElement = $state<HTMLAudioElement | null>(null);
	let autoplayBlocked = $state(false);

	function formatShort(value: number): string {
		if (value >= 1000) return `${(value / 1000).toFixed(2)}k`;
		return value.toFixed(0);
	}

	async function playAudio() {
		if (!audioElement) return;

		try {
			autoplayBlocked = false;
			await audioElement.play();
		} catch {
			autoplayBlocked = true;
		}
	}

	$effect(() => {
		if (audioUrl && audioElement) void playAudio();
	});
</script>

<section
	aria-label="Поточний кошик"
	class="w-full mx-auto bg-app-card rounded-[24px] p-6 border border-app-border shadow-bento flex flex-col"
>
	<div>
		<h3 class="text-[24px] leading-8 font-semibold text-on-surface mb-6">Поточний кошик</h3>
		<div class="flex items-center gap-4 mb-6">
			<div class="relative w-24 h-24 shrink-0">
				<svg class="w-full h-full transform -rotate-90" viewBox="0 0 36 36" aria-hidden="true">
					<path
						class="text-surface-variant stroke-current"
						d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
						fill="none"
						stroke-width="3"
					></path>
					<path
						class="text-app-primary stroke-current"
						d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
						fill="none"
						stroke-dasharray="100, 100"
						stroke-linecap="round"
						stroke-width="3"
					></path>
				</svg>
				<div class="absolute inset-0 flex flex-col items-center justify-center">
					<span class="text-xs text-on-surface-variant font-medium leading-tight">грн</span>
					<span class="text-lg font-bold text-on-surface leading-tight">{formatShort(totalPrice)}</span>
				</div>
			</div>
			<div>
				<p class="text-[16px] leading-6 text-on-surface-variant">Використання бюджету</p>
				<p class="text-[24px] leading-8 text-on-surface font-bold">
					<span data-testid="total-price">{totalPrice.toFixed(2)}</span>
					<span class="text-on-surface-variant font-normal text-[18px]">грн</span>
				</p>
				{#if isBudgetExceeded}
					<span
						data-testid="budget-warning"
						class="text-xs mt-1 font-medium bg-amber-50 border border-amber-200 text-amber-800 inline-flex items-center gap-1 px-2 py-0.5 rounded-full"
						>⚠️ Бюджет перевищено</span
					>
				{:else}
					<span
						data-testid="budget-ok"
						class="text-xs mt-1 font-medium bg-green-100 border border-green-200 text-green-700 inline-flex items-center gap-1 px-2 py-0.5 rounded-full"
					>
						<span class="material-symbols-outlined text-[14px]" aria-hidden="true"
							>check_circle</span
						>
						В межах бюджету
					</span>
				{/if}
			</div>
		</div>

		<p class="text-on-surface text-base leading-relaxed mb-6">{summary}</p>

		<CartItemsPreview {items} />

		{#if audioUrl}
			<div
				class="bg-surface-container-lowest border border-app-border rounded-xl p-4 mb-6 flex items-center gap-3"
			>
				<div
					class="w-8 h-8 rounded-full bg-tertiary-container text-on-tertiary flex items-center justify-center shrink-0"
				>
					<span class="material-symbols-outlined text-sm" aria-hidden="true">graphic_eq</span>
				</div>
				<div class="flex-1 min-w-0">
					<p
						class="text-xs text-on-surface-variant font-semibold uppercase tracking-wide mb-1"
					>
						Відповідь агента
					</p>
					<!-- svelte-ignore a11y_media_has_caption -->
					<audio
						bind:this={audioElement}
						data-testid="tts-audio"
						controls
						autoplay
						preload="auto"
						src={audioUrl}
						oncanplay={playAudio}
						class="w-full"
					></audio>
					{#if autoplayBlocked}
						<button
							type="button"
							onclick={playAudio}
							class="mt-2 text-sm font-semibold text-app-primary hover:underline"
						>
							▶ Відтворити відповідь
						</button>
					{/if}
				</div>
			</div>
		{/if}
	</div>

	{#if cartUrl}
		<a
			href={cartUrl}
			target="_blank"
			rel="noopener noreferrer"
			class="w-full bg-app-primary hover:bg-app-primary-dark text-white font-semibold text-base py-3.5 px-4 rounded-xl flex justify-center items-center gap-2 transition-colors active:scale-[0.98] shadow-md shadow-app-primary/20"
		>
			<span>Перейти до оформлення</span>
			<span class="material-symbols-outlined text-[20px]" aria-hidden="true">arrow_forward</span>
		</a>
	{/if}
</section>
