<script lang="ts">
	/**
	 * AgentTimeline — SSE stream listener for POST /api/agent/stream.
	 *
	 * Uses a fetch-based reader (not native EventSource) because the endpoint
	 * requires a POST body.
	 *
	 * Props:
	 *   request — { userText, audioBase64, threadId } | null
	 *   oncomplete(payload: NodeCompletePayload) — called on `node_complete` event
	 */

	import { getBackendUrl } from '$lib/config';
	import { normalizeCartItems, type CartItem } from '$lib/cart';

	interface StreamRequest {
		userText: string;
		audioBase64: string;
		threadId: string;
	}

	interface TimelineEvent {
		id: number;
		type: string;
		label: string;
	}

	interface NodeCompletePayload {
		cartUrl: string | null;
		summary: string;
		audioUrl: string | null;
		totalPrice: number;
		isBudgetExceeded: boolean;
		items: CartItem[];
	}

	interface Props {
		request: StreamRequest | null;
		oncomplete: (payload: NodeCompletePayload) => void;
	}

	let { request, oncomplete }: Props = $props();

	let events: TimelineEvent[] = $state([]);
	let streaming = $state(false);
	let error: string | null = $state(null);
	let eventCounter = 0;

	function resolveAudioUrl(url: string | null): string | null {
		if (!url) return null;
		return /^https?:\/\//.test(url) ? url : `${getBackendUrl()}${url}`;
	}

	const NODE_LABELS: Record<string, string> = {
		stt: '🎤 Розпізнавання мовлення',
		parse_intent: '🧠 Визначення наміру',
		plan_domain_logic: '📋 Планування кошика',
		mcp_fetch: '🔍 Пошук товарів у Silpo',
		check_constraints: '💰 Перевірка бюджету',
		create_cart: '🛒 Формування кошика',
		tts: '🔊 Озвучення відповіді',
	};

	function addEvent(type: string, label: string) {
		events = [...events, { id: eventCounter++, type, label }];
	}

	async function runStream(req: StreamRequest) {
		events = [];
		streaming = true;
		error = null;

		try {
			const response = await fetch(`${getBackendUrl()}/api/agent/stream`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					user_text: req.userText || null,
					audio_base64: req.audioBase64 || null,
					thread_id: req.threadId,
				}),
			});

			if (!response.ok || !response.body) {
				throw new Error(`HTTP ${response.status}`);
			}

			const reader = response.body.getReader();
			const decoder = new TextDecoder();
			let buffer = '';
			let currentEventType = '';

			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split('\n');
				buffer = lines.pop() ?? '';

				for (const line of lines) {
					if (line.startsWith('event:')) {
						currentEventType = line.slice(6).trim();
					} else if (line.startsWith('data:')) {
						try {
							const data = JSON.parse(line.slice(5).trim());
							handleSSEEvent(currentEventType, data);
						} catch {
							// malformed JSON — skip
						}
					}
				}
			}
		} catch (err) {
			error = err instanceof Error ? err.message : "Помилка з'єднання";
		} finally {
			streaming = false;
		}
	}

	function handleSSEEvent(type: string, data: Record<string, unknown>) {
		switch (type) {
			case 'session_info':
				addEvent('session_info', `🆔 Сесія: ${data['thread_id']}`);
				break;

			case 'thinking_step': {
				const node = String(data['node'] ?? '');
				addEvent('thinking_step', NODE_LABELS[node] ?? `⚙️ ${node}`);
				break;
			}

			case 'tool_start':
				addEvent('tool_start', `🔧 Виклик інструменту: ${data['tool']}`);
				break;

			case 'tool_end':
				addEvent('tool_end', `✅ Інструмент завершено: ${data['tool']}`);
				break;

			case 'node_complete':
				addEvent('node_complete', '🏁 Готово!');
				oncomplete({
					cartUrl: (data['cart_url'] as string | null) ?? null,
					summary: String(data['summary'] ?? ''),
					audioUrl: resolveAudioUrl((data['audio_url'] as string | null) ?? null),
					totalPrice: Number(data['total_price'] ?? 0),
					isBudgetExceeded: Boolean(data['is_budget_exceeded']),
					items: normalizeCartItems(data['items']),
				});
				break;
		}
	}

	// React to request changes (Svelte 5 effect)
	$effect(() => {
		if (request) {
			runStream(request);
		}
	});

	let sessionTag = $derived(
		request ? request.threadId.replaceAll('-', '').slice(0, 4).toUpperCase() : '',
	);
</script>

<div
	data-testid="agent-timeline"
	class="w-full mx-auto bg-app-card rounded-[24px] border border-app-border shadow-bento p-6"
>
	{#if !request && events.length === 0}
		<p
			data-testid="timeline-empty"
			class="text-center text-on-surface-variant/70 text-sm flex items-center justify-center gap-2"
		>
			<span class="material-symbols-outlined text-sm" aria-hidden="true">lightbulb</span>
			Спробуйте запитати... Введіть запит, щоб розпочати…
		</p>
	{:else}
		<div class="mb-4 flex items-center justify-between gap-2">
			<h3 class="text-[14px] leading-5 font-semibold text-on-surface-variant flex items-center gap-2">
				<span class="material-symbols-outlined text-sm" aria-hidden="true">memory</span>
				Хід думок Edica
			</h3>
			{#if sessionTag}
				<span
					class="hidden sm:inline-block text-xs text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-full"
					>Сесія #{sessionTag}</span
				>
			{/if}
		</div>

		{#if streaming}
			<div data-testid="timeline-streaming" class="flex items-center gap-2 mb-4 text-primary">
				<span class="inline-block w-3 h-3 rounded-full bg-app-primary animate-pulse"></span>
				<span
					class="text-sm font-semibold bg-gradient-to-r from-app-primary to-app-secondary bg-clip-text text-transparent"
					>Edica думає…</span
				>
			</div>
		{/if}

		{#if error}
			<p class="text-error text-sm mb-4">⚠️ {error}</p>
		{/if}

		<div class="flex flex-col gap-4">
			{#each events as ev, index (ev.id)}
				{@const active = streaming && index === events.length - 1}
				{#if active}
					<div
						class="flex gap-3 items-start bg-primary-fixed/20 p-3 -mx-3 rounded-xl border border-primary-fixed"
					>
						<div
							class="w-6 h-6 rounded-full bg-app-primary text-white flex items-center justify-center mt-0.5 animate-pulse shrink-0"
						>
							<span class="w-2 h-2 bg-white rounded-full"></span>
						</div>
						<p class="text-[16px] leading-6 text-on-surface pt-0.5 font-medium">{ev.label}</p>
					</div>
				{:else}
					<div class="flex gap-3 items-start opacity-60">
						<div
							class="w-6 h-6 rounded-full bg-surface-container flex items-center justify-center mt-0.5 shrink-0"
						>
							<span class="material-symbols-outlined text-[14px]" aria-hidden="true">check</span>
						</div>
						<p class="text-[16px] leading-6 text-on-surface flex-1 pt-0.5">{ev.label}</p>
					</div>
				{/if}
			{/each}
		</div>
	{/if}
</div>
