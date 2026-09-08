<script lang="ts">
	/**
	 * QueryInProgress — compact hero replacement while the agent is streaming.
	 *
	 * Shows the recognized user query inside an animated gradient border so the
	 * page confirms the input without the dead space of disabled controls.
	 *
	 * Props:
	 *   query — user text (empty for voice requests → voice fallback label)
	 */

	interface Props {
		query?: string;
	}

	let { query = '' }: Props = $props();

	const label = $derived(query.trim() || '🎤 Голосовий запит');
</script>

<div
	data-testid="query-in-progress"
	role="status"
	aria-live="polite"
	aria-label="Запит обробляється"
	class="query-flow w-full rounded-full p-[2px]"
>
	<div class="flex items-center gap-2 rounded-full bg-app-card px-6 py-4 shadow-sm">
		<span
			class="inline-block h-2.5 w-2.5 shrink-0 rounded-full bg-app-primary animate-pulse"
			aria-hidden="true"
		></span>
		<p
			data-testid="query-in-progress-text"
			title={label}
			class="flex-1 truncate text-center text-[16px] leading-6 text-on-surface"
		>
			«{label}»
		</p>
		<span class="material-symbols-outlined shrink-0 text-app-primary animate-pulse" aria-hidden="true"
			>autorenew</span
		>
	</div>
</div>
