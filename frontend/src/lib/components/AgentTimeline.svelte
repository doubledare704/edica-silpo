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

	const BACKEND_URL = 'http://localhost:8000';

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
			const response = await fetch(`${BACKEND_URL}/api/agent/stream`, {
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
					audioUrl: (data['audio_url'] as string | null) ?? null,
					totalPrice: Number(data['total_price'] ?? 0),
					isBudgetExceeded: Boolean(data['is_budget_exceeded']),
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
		{#if streaming}
			<div
				data-testid="timeline-streaming"
				class="flex items-center gap-2 mb-4 text-primary"
			>
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

		<ol class="relative border-l border-app-border ml-3 space-y-3">
			{#each events as ev (ev.id)}
				<li class="ml-4">
					<span
						class={[
							'absolute -left-1.5 mt-1 w-3 h-3 rounded-full border-2 border-white',
							ev.type === 'node_complete' ? 'bg-app-primary' : 'bg-app-secondary',
						].join(' ')}
					></span>
					<p class="text-sm text-on-surface">{ev.label}</p>
				</li>
			{/each}
		</ol>
	{/if}
</div>
