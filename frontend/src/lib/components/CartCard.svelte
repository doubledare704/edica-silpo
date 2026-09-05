<script lang="ts">
	/**
	 * CartCard — displays the final agent result.
	 *
	 * Props:
	 *   cartUrl      — Silpo cart share URL (or null if unavailable)
	 *   summary      — Ukrainian text summary from the agent
	 *   audioUrl     — path to Respeecher TTS audio (or null)
	 *   totalPrice   — total cart price in UAH
	 *   isBudgetExceeded — whether the cart exceeded the requested budget
	 */

	interface Props {
		cartUrl: string | null;
		summary: string;
		audioUrl: string | null;
		totalPrice: number;
		isBudgetExceeded: boolean;
	}

	let { cartUrl, summary, audioUrl, totalPrice, isBudgetExceeded }: Props = $props();
</script>

<div
	class="w-full mx-auto rounded-[24px] border border-app-border bg-app-card shadow-bento p-6 space-y-4"
>
	<p class="text-on-surface text-base leading-relaxed">{summary}</p>

	{#if isBudgetExceeded}
		<div
			data-testid="budget-warning"
			class="flex items-center gap-2 rounded-full bg-amber-50 border border-amber-200 px-4 py-2 text-sm text-amber-800"
		>
			⚠️ Бюджет перевищено — кошик оптимізовано за максимально можливою точністю.
		</div>
	{/if}

	<div class="flex items-center justify-between text-sm text-on-surface-variant">
		<span>Загальна сума:</span>
		<span data-testid="total-price" class="font-semibold text-on-surface">
			{totalPrice.toFixed(2)} грн
		</span>
	</div>

	{#if audioUrl}
		<div class="space-y-1">
			<p class="text-xs text-on-surface-variant font-semibold uppercase tracking-wide">
				Відповідь агента
			</p>
			<!-- svelte-ignore a11y_media_has_caption -->
			<audio controls src={audioUrl} class="w-full rounded-full"></audio>
		</div>
	{/if}

	{#if cartUrl}
		<a
			href={cartUrl}
			target="_blank"
			rel="noopener noreferrer"
			class="flex items-center justify-center gap-2 w-full rounded-full bg-app-primary px-4 py-3 text-sm font-semibold text-white hover:bg-app-primary-dark active:scale-[0.99] transition-all"
		>
			<span class="material-symbols-outlined text-[20px]" aria-hidden="true">shopping_bag</span>
			Відкрити кошик у Silpo
		</a>
	{/if}
</div>
