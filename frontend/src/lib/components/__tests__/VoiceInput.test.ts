import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect, vi } from 'vitest';
import VoiceInput from '../VoiceInput.svelte';

describe('VoiceInput', () => {
	it('renders a text input field', () => {
		render(VoiceInput, { onsubmit: vi.fn() });
		expect(screen.getByRole('textbox')).toBeInTheDocument();
	});

	it('renders a push-to-talk button', () => {
		render(VoiceInput, { onsubmit: vi.fn() });
		// A button with a mic-related label should exist
		expect(screen.getByTestId('ptt-button')).toBeInTheDocument();
	});

	it('renders a send button', () => {
		render(VoiceInput, { onsubmit: vi.fn() });
		expect(screen.getByTestId('send-button')).toBeInTheDocument();
	});

	it('calls onsubmit with userText when text is entered and send is clicked', async () => {
		const onsubmit = vi.fn();
		render(VoiceInput, { onsubmit });

		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'Збери кошик для пікніка' } });
		await fireEvent.click(screen.getByTestId('send-button'));

		expect(onsubmit).toHaveBeenCalledOnce();
		expect(onsubmit).toHaveBeenCalledWith(
			expect.objectContaining({ userText: 'Збери кошик для пікніка', audioBase64: '' }),
		);
	});

	it('does not call onsubmit when text input is empty', async () => {
		const onsubmit = vi.fn();
		render(VoiceInput, { onsubmit });
		await fireEvent.click(screen.getByTestId('send-button'));
		expect(onsubmit).not.toHaveBeenCalled();
	});

	it('clears text input after successful submit', async () => {
		const onsubmit = vi.fn();
		render(VoiceInput, { onsubmit });

		const input = screen.getByRole('textbox') as HTMLInputElement;
		await fireEvent.input(input, { target: { value: 'Тест' } });
		await fireEvent.click(screen.getByTestId('send-button'));

		expect(input.value).toBe('');
	});
});

