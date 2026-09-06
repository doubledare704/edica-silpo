export interface CartItem {
	id: string | null;
	title: string;
	price: number;
	quantity: number;
	is_private_label: boolean;
	line_total: number;
}

const EMOJI_RULES: Array<[RegExp, string]> = [
	[/ошийок|ошийник|свинин|яловичин|курк|м'яс|мяс|bbq|стейк/i, '🥩'],
	[/томат/i, '🍅'],
	[/багет|булк|хліб|хлеб|круасан/i, '🥖'],
	[/овоч|салат|зелень/i, '🥗'],
	[/молок/i, '🥛'],
	[/яйц/i, '🥚'],
	[/сир|брі|гауда|горгонзол|моцарел/i, '🧀'],
	[/вино|wine|chianti|el maestro/i, '🍷'],
	[/кав/i, '☕'],
	[/чай|tea/i, '🍵'],
	[/печиво|крекер|cookies/i, '🍪'],
	[/виноград|кишмиш/i, '🍇'],
	[/яблук/i, '🍎'],
	[/вугілля|вуг/i, '🪵'],
	[/вод/i, '💧'],
	[/цукор/i, '🍬'],
];

export function itemEmoji(title: string): string {
	for (const [pattern, emoji] of EMOJI_RULES) {
		if (pattern.test(title)) return emoji;
	}
	return '🛒';
}

export function itemsCountLabel(count: number): string {
	const mod10 = count % 10;
	const mod100 = count % 100;
	if (mod10 === 1 && mod100 !== 11) return `${count} товар`;
	if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${count} товари`;
	return `${count} товарів`;
}

export function normalizeCartItems(raw: unknown): CartItem[] {
	if (!Array.isArray(raw)) return [];
	return raw
		.filter((entry): entry is Record<string, unknown> => typeof entry === 'object' && entry !== null)
		.map((entry) => {
			const price = Number(entry['price'] ?? 0);
			const quantity = Number(entry['quantity'] ?? 1);
			return {
				id: entry['id'] != null ? String(entry['id']) : null,
				title: String(entry['title'] ?? ''),
				price: Number.isFinite(price) ? price : 0,
				quantity: Number.isFinite(quantity) && quantity > 0 ? Math.floor(quantity) : 1,
				is_private_label: Boolean(entry['is_private_label']),
				line_total: Number(entry['line_total'] ?? (Number.isFinite(price) ? price : 0)),
			} satisfies CartItem;
		})
		.filter((item) => item.title.length > 0);
}
