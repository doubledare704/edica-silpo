<script lang="ts">
	/**
	 * EmptyCart — honest nothing-found state for runs where the picker
	 * accepted zero products.
	 *
	 * Props:
	 *   summary     — Ukrainian text summary from the agent
	 *   audioUrl    — path to TTS audio of the agent reply (or null)
	 *   unfulfilled — requested items that could not be picked
	 *   onnew()     — called when the user starts over
	 */

	interface Props {
		summary: string;
		audioUrl: string | null;
		unfulfilled?: string[];
		onnew: () => void;
	}

	let { summary, audioUrl, unfulfilled = [], onnew }: Props = $props();
	let audioElement = $state<HTMLAudioElement | null>(null);

	async function playAudio() {
		if (!audioElement) return;
		try {
			await audioElement.play();
		} catch {
			// autoplay blocked — the native controls stay available
		}
	}

	$effect(() => {
		if (audioUrl && audioElement) void playAudio();
	});
</script>

<section
	data-testid="empty-cart"
	aria-label="Нічого не знайдено"
	class="w-full mx-auto bg-app-card rounded-[24px] p-6 border border-app-border shadow-bento flex flex-col"
>
	<div class="flex items-center gap-4 mb-6">
		<div
			class="w-16 h-16 rounded-full bg-surface-container flex items-center justify-center shrink-0"
		>
			<span class="material-symbols-outlined text-3xl text-on-surface-variant" aria-hidden="true"
				>search_off</span
			>
		</div>
		<div>
			<h3 class="text-[24px] leading-8 font-semibold text-on-surface">Нічого не знайдено</h3>
			<p class="text-[14px] leading-5 text-on-surface-variant">
				Жоден товар не вдалося підібрати під цей запит.
			</p>
		</div>
	</div>

	<p class="text-on-surface text-base leading-relaxed mb-6">{summary}</p>

	{#if unfulfilled.length > 0}
		<div data-testid="empty-cart-missing" class="mb-6">
			<p class="text-sm font-semibold text-on-surface mb-2">Не вдалося знайти:</p>
			<ul class="flex flex-wrap gap-2">
				{#each unfulfilled as request}
					<li
						class="text-sm text-on-surface-variant bg-surface-container border border-app-border px-3 py-1 rounded-full"
					>
						{request}
					</li>
				{/each}
			</ul>
		</div>
	{/if}

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
				<p class="text-xs text-on-surface-variant font-semibold uppercase tracking-wide mb-1">
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
			</div>
		</div>
	{/if}

	<button
		data-testid="empty-cart-retry"
		type="button"
		onclick={onnew}
		class="w-full bg-app-primary hover:bg-app-primary-dark text-white font-semibold text-base py-3.5 px-4 rounded-xl flex justify-center items-center gap-2 transition-colors active:scale-[0.98] shadow-md shadow-app-primary/20"
	>
		<span>Спробувати ще раз</span>
		<span class="material-symbols-outlined text-[20px]" aria-hidden="true">refresh</span>
	</button>
</section>
