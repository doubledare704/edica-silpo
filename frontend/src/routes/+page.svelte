<script lang="ts">
	import VoiceInput from '$lib/components/VoiceInput.svelte';
	import AgentTimeline from '$lib/components/AgentTimeline.svelte';
	import CartCard from '$lib/components/CartCard.svelte';

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

	let currentRequest: StreamRequest | null = $state(null);
	let cartPayload: CartPayload | null = $state(null);

	function handleSubmit(data: { userText: string; audioBase64: string }) {
		cartPayload = null;
		currentRequest = {
			...data,
			threadId: crypto.randomUUID(),
		};
	}

	function handleComplete(payload: CartPayload) {
		cartPayload = payload;
	}
</script>

<svelte:head>
	<title>Silpo Smart Shopper</title>
</svelte:head>

<main class="min-h-screen bg-gray-50 px-4 py-10">
	<div class="max-w-xl mx-auto space-y-8">
		<!-- Header -->
		<header class="text-center space-y-1">
			<h1 class="text-3xl font-bold text-green-700">🛒 Silpo Smart Shopper</h1>
			<p class="text-sm text-gray-500">Голосовий або текстовий запит → готовий кошик</p>
		</header>

		<!-- Voice / Text input -->
		<VoiceInput onsubmit={handleSubmit} />

		<!-- Streaming timeline -->
		{#if currentRequest}
			<AgentTimeline request={currentRequest} oncomplete={handleComplete} />
		{/if}

		<!-- Result card -->
		{#if cartPayload}
			<CartCard
				cartUrl={cartPayload.cartUrl}
				summary={cartPayload.summary}
				audioUrl={cartPayload.audioUrl}
				totalPrice={cartPayload.totalPrice}
				isBudgetExceeded={cartPayload.isBudgetExceeded}
			/>
		{/if}
	</div>
</main>

