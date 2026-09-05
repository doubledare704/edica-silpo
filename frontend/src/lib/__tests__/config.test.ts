import { describe, it, expect, vi, afterEach } from 'vitest';
import { getBackendUrl } from '../config';

afterEach(() => {
	vi.unstubAllEnvs();
});

describe('getBackendUrl', () => {
	it('falls back to localhost:8000 when no env var is set', () => {
		vi.stubEnv('VITE_BACKEND_URL', '');
		expect(getBackendUrl()).toBe('http://localhost:8000');
	});

	it('returns the configured backend url', () => {
		vi.stubEnv('VITE_BACKEND_URL', 'https://api.example.com');
		expect(getBackendUrl()).toBe('https://api.example.com');
	});

	it('strips a trailing slash so URLs join cleanly', () => {
		vi.stubEnv('VITE_BACKEND_URL', 'https://api.example.com/');
		expect(getBackendUrl()).toBe('https://api.example.com');
	});
});