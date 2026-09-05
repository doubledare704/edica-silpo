<script lang="ts">
	/**
	 * VoiceInput — push-to-talk voice input with text fallback.
	 *
	 * Props:
	 *   onsubmit(data: { userText: string; audioBase64: string }) — called when user submits
	 *
	 * Behaviour:
	 *   • Hold "Говори" button → starts MediaRecorder (WebM chunks)
	 *   • Release → stops recording, base64-encodes audio, calls onsubmit
	 *   • If MediaRecorder unavailable → mic button is disabled; text-only mode
	 *   • Text field + Send button always visible as fallback
	 */

	interface Props {
		onsubmit: (data: { userText: string; audioBase64: string }) => void;
	}

	let { onsubmit }: Props = $props();

	let userText = $state('');
	let recording = $state(false);
	let mediaRecorder: MediaRecorder | null = null;
	let chunks: Blob[] = [];
	let micAvailable = $state(true);

	async function startRecording() {
		try {
			const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
			chunks = [];
			mediaRecorder = new MediaRecorder(stream);
			mediaRecorder.ondataavailable = (e) => {
				if (e.data.size > 0) chunks.push(e.data);
			};
			mediaRecorder.onstop = () => {
				const blob = new Blob(chunks, { type: 'audio/webm' });
				const reader = new FileReader();
				reader.onloadend = () => {
					const base64 = (reader.result as string).split(',')[1] ?? '';
					onsubmit({ userText: '', audioBase64: base64 });
				};
				reader.readAsDataURL(blob);
				stream.getTracks().forEach((t) => t.stop());
			};
			mediaRecorder.start();
			recording = true;
		} catch {
			micAvailable = false;
			recording = false;
		}
	}

	function stopRecording() {
		mediaRecorder?.stop();
		recording = false;
	}

	function handlePTTPointerDown() {
		if (!recording) startRecording();
	}

	function handlePTTPointerUp() {
		if (recording) stopRecording();
	}

	function handleTextSubmit() {
		const text = userText.trim();
		if (!text) return;
		onsubmit({ userText: text, audioBase64: '' });
		userText = '';
	}

	function handleKeyDown(e: KeyboardEvent) {
		if (e.key === 'Enter') handleTextSubmit();
	}
</script>

<div class="flex flex-col gap-3 w-full mx-auto">
	<div class="relative">
		<input
			type="text"
			class="w-full bg-surface border border-app-border rounded-full py-4 pl-6 pr-14 text-[16px] leading-6 text-on-surface text-center focus:outline-none focus:ring-2 focus:ring-app-primary focus:border-transparent transition-shadow shadow-sm placeholder:text-on-surface-variant/70"
			placeholder="Я слухаю... Запитайте Edica, наприклад:"
			aria-label="Текст запиту до Edica"
			bind:value={userText}
			onkeydown={handleKeyDown}
		/>
		<button
			data-testid="send-button"
			type="button"
			aria-label="Надіслати"
			onclick={handleTextSubmit}
			class="absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-surface-container hover:bg-surface-container-high flex items-center justify-center text-on-surface-variant hover:text-app-primary transition-colors active:scale-95"
		>
			<span class="material-symbols-outlined" aria-hidden="true">send</span>
		</button>
	</div>

	<button
		data-testid="ptt-button"
		type="button"
		disabled={!micAvailable}
		onpointerdown={handlePTTPointerDown}
		onpointerup={handlePTTPointerUp}
		onpointerleave={handlePTTPointerUp}
		class={[
			'rounded-full px-6 py-3 text-sm font-semibold transition-all duration-150 select-none border inline-flex items-center justify-center gap-2',
			recording
				? 'bg-red-500 border-red-500 text-white scale-95 shadow-inner'
				: micAvailable
					? 'bg-surface-container-lowest text-on-surface-variant border-app-border hover:border-app-primary hover:text-app-primary shadow-sm'
					: 'bg-surface-container-low text-on-surface-variant/50 border-app-border cursor-not-allowed',
		].join(' ')}
	>
		<span class="material-symbols-outlined text-[20px]" aria-hidden="true">
			{!micAvailable ? 'mic_off' : recording ? 'fiber_manual_record' : 'mic'}
		</span>
		{#if !micAvailable}
			Мікрофон недоступний
		{:else if recording}
			Запис… (відпустіть)
		{:else}
			Говори (утримуй)
		{/if}
	</button>
</div>
