<script lang="ts">
	import VoiceInput from '$lib/components/VoiceInput.svelte';
	import AgentTimeline from '$lib/components/AgentTimeline.svelte';
	import CartCard from '$lib/components/CartCard.svelte';
	import SuccessBanner from '$lib/components/SuccessBanner.svelte';

	interface CartPayload {
		cartUrl: string | null;
		summary: string;
		audioUrl: string | null;
		totalPrice: number;
		isBudgetExceeded: boolean;
	}

	interface StreamRequest {
		userText: string;
		audioBase64: string;
		threadId: string;
	}

	const SUGGESTIONS = [
		'Збери вечірку з друзями на вихідні',
		'Продукти на тиждень до 1 500 грн',
		'Підбери вишукане вино та крафтові сири',
		'Замов каву, молоко та перекуси для офісу',
	];

	let currentRequest: StreamRequest | null = $state(null);
	let cartPayload: CartPayload | null = $state(null);

	function handleSubmit(data: { userText: string; audioBase64: string }) {
		cartPayload = null;
		currentRequest = {
			...data,
			threadId: crypto.randomUUID(),
		};
	}

	function handleSuggestion(suggestion: string) {
		handleSubmit({ userText: suggestion, audioBase64: '' });
	}

	function handleComplete(payload: CartPayload) {
		cartPayload = payload;
	}

	function handleNewRequest() {
		currentRequest = null;
		cartPayload = null;
	}
</script>

<svelte:head>
	<title>Edica — Silpo Smart Shopper Dashboard</title>
</svelte:head>

<main class="flex-1 max-w-[1280px] mx-auto w-full px-4 md:px-10 py-6 flex flex-col gap-4">
	{#if cartPayload}
		<SuccessBanner onnew={handleNewRequest} />
		<CartCard
			cartUrl={cartPayload.cartUrl}
			summary={cartPayload.summary}
			audioUrl={cartPayload.audioUrl}
			totalPrice={cartPayload.totalPrice}
			isBudgetExceeded={cartPayload.isBudgetExceeded}
		/>
	{:else}
		<div class="grid grid-cols-1 md:grid-cols-12 gap-4">
			<section
				class="md:col-span-12 bg-app-card rounded-[24px] p-6 border border-app-border shadow-bento flex flex-col items-center justify-center min-h-[500px] relative overflow-hidden"
				aria-label="Панель Edica — Режим очікування"
			>
				<div
					class="absolute inset-0 bg-gradient-to-b from-transparent to-[#FFB693]/10 pointer-events-none"
					aria-hidden="true"
				></div>

				<div class="relative mb-12 mt-4" aria-hidden="true">
					<div class="absolute inset-[-10px] bg-app-primary/40 rounded-full pulse-ring"></div>
					<div
						class="absolute inset-[-30px] bg-app-primary/20 rounded-full pulse-ring"
						style="animation-delay: 0.5s;"
					></div>
					<div
						class="absolute inset-[-50px] bg-app-secondary/20 rounded-full pulse-ring"
						style="animation-delay: 1s;"
					></div>
					<div
						class="relative bg-app-primary text-white w-28 h-28 rounded-full flex items-center justify-center shadow-lg z-10"
					>
						<span
							class="material-symbols-outlined text-5xl"
							style="font-variation-settings: 'FILL' 1;">mic</span
						>
					</div>
				</div>

				<div class="w-full max-w-xl relative z-10 mb-12">
					<VoiceInput onsubmit={handleSubmit} />
				</div>

				<div class="flex flex-col items-center z-10 w-full max-w-2xl px-4">
					<h2
						class="text-[14px] leading-5 font-semibold text-on-surface-variant mb-4 flex items-center gap-2"
					>
						<span class="material-symbols-outlined text-sm" aria-hidden="true">lightbulb</span>
						Спробуйте запитати...
					</h2>
					<div class="flex flex-wrap justify-center gap-3">
						{#each SUGGESTIONS as suggestion}
							<button
								type="button"
								onclick={() => handleSuggestion(suggestion)}
								class="bg-surface-container-lowest border border-app-border hover:border-app-primary hover:text-app-primary text-on-surface-variant text-sm font-semibold px-5 py-2.5 rounded-full transition-all active:scale-95 shadow-sm"
							>
								«{suggestion}»
							</button>
						{/each}
					</div>
				</div>
			</section>
		</div>

		{#if currentRequest}
			<AgentTimeline request={currentRequest} oncomplete={handleComplete} />
		{/if}
	{/if}
</main>
