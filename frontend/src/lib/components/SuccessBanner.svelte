<script lang="ts">
	/**
	 * SuccessBanner — green confirmation shown when calculation finishes.
	 * Replaces the voice input hero (Stitch: "Розрахунок завершено").
	 *
	 * Props:
	 *   onnew() — called when the user taps the history button to start over
	 */

	interface Props {
		onnew: () => void;
	}

	let { onnew }: Props = $props();
</script>

<section
	data-testid="success-banner"
	aria-label="Розрахунок завершено"
	class="bg-[#E6F4EA] rounded-[24px] p-4 border border-[#CEEAD6] flex items-center gap-3"
>
	<div
		class="w-10 h-10 rounded-full bg-[#34A853] text-white flex items-center justify-center shrink-0"
	>
		<span class="material-symbols-outlined" aria-hidden="true">check</span>
	</div>
	<div class="flex-1 min-w-0">
		<h2 class="text-[14px] leading-5 font-semibold text-[#137333]">Розрахунок завершено</h2>
		<p class="text-[12px] leading-4 font-medium text-[#137333]/80">
			Ваш розумний кошик готовий до оформлення.
		</p>
	</div>
	<button
		data-testid="new-request-button"
		type="button"
		onclick={onnew}
		title="Новий запит"
		aria-label="Новий запит"
		class="text-[#137333] hover:bg-[#CEEAD6] p-2 rounded-full transition-colors flex items-center justify-center shrink-0 active:scale-95"
	>
		<span class="material-symbols-outlined text-sm" aria-hidden="true">history</span>
	</button>
</section>
