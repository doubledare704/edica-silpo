<script lang="ts">
	import { onMount } from 'svelte';
	import { getBackendUrl } from '$lib/config';
	import { formatStoreLabel, selectedStore } from '$lib/selectedStore.svelte';

	interface Loyalty {
		card_number: string;
		status: string;
		bonus_balance: number;
		bonus_earned: number;
	}

	interface Promotion {
		id: string;
		title: string;
		description: string | null;
		discount_percent: number | null;
		price_from: number | null;
		price_to: number | null;
		ends_at: string | null;
		is_price_of_week: boolean;
		image_url: string | null;
	}

	interface PromoProduct {
		id: string;
		title: string;
		price: number;
		old_price: number | null;
		discount_percent: number | null;
		image_url?: string;
		unit?: string;
	}

	interface PersonalPromo {
		id: string;
		title: string;
		description: string | null;
		expires_at: string | null;
	}

	interface Coupon {
		id: string;
		title: string;
		discount: number;
		expires_at: string | null;
		barcode: string | null;
	}

	interface PromoCode {
		code: string;
		description: string | null;
		expires_at: string | null;
	}

	interface OffersOverview {
		loyalty: Loyalty;
		promotions: Promotion[];
		promo_products: PromoProduct[];
		personal_promos: PersonalPromo[];
		coupons: Coupon[];
		promo_codes: PromoCode[];
	}

	let offers: OffersOverview | null = $state(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	const currency = new Intl.NumberFormat('uk-UA', {
		style: 'currency',
		currency: 'UAH',
		maximumFractionDigits: 2,
	});

	function formatPrice(value: number): string {
		return currency.format(value);
	}

	function formatDate(value: string | null): string | null {
		if (!value) return null;
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) return null;
		return new Intl.DateTimeFormat('uk-UA', { day: 'numeric', month: 'long' }).format(date);
	}

	async function loadOffers() {
		loading = true;
		error = null;
		try {
			const address = encodeURIComponent(selectedStore.address);
			const response = await fetch(`${getBackendUrl()}/api/offers?delivery_address=${address}`);
			if (!response.ok) throw new Error(`HTTP ${response.status}`);
			offers = (await response.json()) as OffersOverview;
		} catch {
			error = 'Не вдалося завантажити пропозиції. Перевірте з’єднання.';
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		void loadOffers();
	});
</script>

<svelte:head>
	<title>Знижки та бонуси — Edica @ Сільпо</title>
</svelte:head>

<main class="w-full max-w-[1280px] mx-auto px-4 md:px-10 py-8 md:py-10 space-y-8">
	<div class="flex items-end justify-between gap-4">
		<div>
			<p class="text-sm font-semibold text-app-primary uppercase tracking-[0.16em]">Вигідні покупки</p>
			<h1 class="mt-2 text-3xl md:text-4xl font-semibold tracking-tight text-app-text">Знижки та бонуси</h1>
			<p class="mt-2 text-sm md:text-base text-[#6e6e73]">
				Пропозиції для магазину: {formatStoreLabel(selectedStore.name, selectedStore.address)}
			</p>
		</div>
		<button
			type="button"
			onclick={() => void loadOffers()}
			disabled={loading}
			class="shrink-0 rounded-full border border-app-border bg-white px-4 py-2 text-sm font-semibold text-app-text hover:border-app-primary hover:text-app-primary disabled:opacity-50"
		>
			<span class="material-symbols-outlined align-middle text-[18px]" aria-hidden="true">refresh</span>
			Оновити
		</button>
	</div>

	{#if loading}
		<div class="grid grid-cols-1 md:grid-cols-12 gap-4" data-testid="offers-loading">
			<div class="md:col-span-4 h-48 rounded-[28px] bg-orange-100 animate-pulse"></div>
			<div class="md:col-span-8 h-48 rounded-[28px] bg-white border border-app-border animate-pulse"></div>
		</div>
	{:else if error}
		<section class="rounded-[28px] bg-white border border-app-border p-8 text-center" data-testid="offers-error">
			<div class="mx-auto w-12 h-12 rounded-full bg-orange-100 text-app-primary flex items-center justify-center">
				<span class="material-symbols-outlined" aria-hidden="true">wifi_off</span>
			</div>
			<h2 class="mt-4 text-lg font-semibold">Щось пішло не так</h2>
			<p class="mt-2 text-sm text-[#6e6e73]">{error}</p>
			<button
				type="button"
				onclick={() => void loadOffers()}
				class="mt-5 rounded-full bg-app-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-app-primary-dark"
				>Спробувати ще</button
			>
		</section>
	{:else if offers}
		<section class="grid grid-cols-1 md:grid-cols-12 gap-4">
			<div class="md:col-span-4 rounded-[28px] bg-gradient-to-br from-[#ff6b00] via-[#f47b22] to-[#ffb800] text-white p-6 min-h-48 flex flex-col justify-between shadow-bento">
				<div class="flex items-start justify-between gap-3">
					<div>
						<p class="text-sm font-medium text-white/80">Мої балабонуси</p>
						<p class="mt-2 text-4xl font-semibold tracking-tight">{offers.loyalty.bonus_balance.toFixed(2)}</p>
						<p class="mt-1 text-sm text-white/80">балів доступно</p>
					</div>
					<span class="material-symbols-outlined text-4xl" aria-hidden="true">savings</span>
				</div>
				<p class="text-sm text-white/90">Нараховано цього періоду: {offers.loyalty.bonus_earned.toFixed(2)}</p>
			</div>
			<div class="md:col-span-8 rounded-[28px] bg-white border border-app-border p-6 shadow-bento flex flex-col justify-between">
				<div class="flex items-start justify-between gap-4">
					<div>
						<p class="text-sm font-semibold text-app-primary uppercase tracking-[0.14em]">Сільпо рекомендує</p>
						<h2 class="mt-2 text-2xl font-semibold">Ціни, які хочеться зберегти</h2>
					</div>
					<span class="material-symbols-outlined text-4xl text-app-secondary" aria-hidden="true">local_offer</span>
				</div>
				<p class="mt-4 max-w-xl text-sm leading-6 text-[#6e6e73]">
					Переглядайте актуальні акції та товари зі знижкою для обраного магазину. Доступність і ціни оновлюються з Silpo MCP.
				</p>
			</div>
		</section>

		{#if offers.promotions.length > 0}
			<section class="space-y-4" data-testid="promotions-section">
				<div class="flex items-end justify-between gap-4">
					<div>
						<p class="text-sm text-[#6e6e73]">Актуально зараз</p>
						<h2 class="text-2xl font-semibold">Акції у вашому Сільпо</h2>
					</div>
					<span class="text-sm font-semibold text-app-primary">{offers.promotions.length} пропозиції</span>
				</div>
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
					{#each offers.promotions as promotion (promotion.id)}
						<article class="rounded-[24px] bg-white border border-app-border p-5 shadow-bento hover:shadow-bento-hover transition-shadow">
							<div class="flex items-start justify-between gap-4">
								<div class="min-w-0">
									{#if promotion.is_price_of_week}
										<span class="inline-flex rounded-full bg-orange-100 px-2.5 py-1 text-xs font-semibold text-app-primary">Ціна тижня</span>
									{/if}
									<h3 class="mt-3 text-lg font-semibold">{promotion.title}</h3>
									<p class="mt-1 text-sm leading-5 text-[#6e6e73]">{promotion.description}</p>
								</div>
								{#if promotion.discount_percent}
									<span class="shrink-0 text-2xl font-semibold text-app-primary">-{promotion.discount_percent}%</span>
								{/if}
							</div>
							<div class="mt-5 flex items-center justify-between gap-3 text-sm">
								{#if promotion.price_to && promotion.price_from}
									<span><span class="text-[#8b8b91] line-through">{formatPrice(promotion.price_to)}</span> <strong>{formatPrice(promotion.price_from)}</strong></span>
								{:else}
									<span class="text-[#6e6e73]">Вигідна ціна в магазині</span>
								{/if}
								{#if formatDate(promotion.ends_at)}
									<span class="text-[#6e6e73]">до {formatDate(promotion.ends_at)}</span>
								{/if}
							</div>
						</article>
					{/each}
				</div>
			</section>
		{/if}

		{#if offers.promo_products.length > 0}
			<section class="space-y-4" data-testid="promo-products-section">
				<div>
					<p class="text-sm text-[#6e6e73]">Вигідно додати до кошика</p>
					<h2 class="text-2xl font-semibold">Товари зі знижкою</h2>
				</div>
				<div class="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
					{#each offers.promo_products as product (product.id)}
						<article class="rounded-[22px] bg-white border border-app-border p-3 md:p-4 shadow-bento hover:shadow-bento-hover transition-shadow">
							<div class="h-28 md:h-36 rounded-2xl bg-[#fff4e9] flex items-center justify-center overflow-hidden">
								{#if product.image_url}
									<img src={product.image_url} alt="" class="h-full w-full object-contain" />
								{:else}
									<span class="text-4xl" aria-hidden="true">🛍️</span>
								{/if}
							</div>
							<h3 class="mt-3 min-h-10 text-sm font-semibold leading-5">{product.title}</h3>
							<div class="mt-3 flex items-end justify-between gap-2">
								<div>
									<strong class="text-lg">{formatPrice(product.price)}</strong>
									{#if product.old_price}
										<span class="block text-xs text-[#8b8b91] line-through">{formatPrice(product.old_price)}</span>
									{/if}
								</div>
								{#if product.discount_percent}
									<span class="rounded-full bg-orange-100 px-2 py-1 text-xs font-bold text-app-primary">-{product.discount_percent}%</span>
								{/if}
							</div>
						</article>
					{/each}
				</div>
			</section>
		{/if}

		<div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
			{#if offers.personal_promos.length > 0}
				<section class="rounded-[24px] bg-white border border-app-border p-5 shadow-bento">
					<div class="flex items-center gap-2">
						<span class="material-symbols-outlined text-app-primary" aria-hidden="true">person_check</span>
						<h2 class="text-lg font-semibold">Для вас</h2>
					</div>
					<div class="mt-4 space-y-3">
						{#each offers.personal_promos as promo (promo.id)}
							<div class="rounded-2xl bg-[#fff8f1] p-3">
								<p class="text-sm font-semibold">{promo.title}</p>
								<p class="mt-1 text-xs leading-5 text-[#6e6e73]">{promo.description}</p>
							</div>
						{/each}
					</div>
				</section>
			{/if}

			{#if offers.coupons.length > 0}
				<section class="rounded-[24px] bg-white border border-app-border p-5 shadow-bento">
					<div class="flex items-center gap-2">
						<span class="material-symbols-outlined text-app-primary" aria-hidden="true">confirmation_number</span>
						<h2 class="text-lg font-semibold">Мої купони</h2>
					</div>
					<div class="mt-4 space-y-3">
						{#each offers.coupons as coupon (coupon.id)}
							<div class="rounded-2xl border border-dashed border-app-primary/40 p-3">
								<div class="flex justify-between gap-3">
									<p class="text-sm font-semibold">{coupon.title}</p>
									<span class="text-sm font-bold text-app-primary">-{formatPrice(coupon.discount)}</span>
								</div>
								{#if coupon.expires_at}<p class="mt-1 text-xs text-[#6e6e73]">Діє до {formatDate(coupon.expires_at)}</p>{/if}
							</div>
						{/each}
					</div>
				</section>
			{/if}

			{#if offers.promo_codes.length > 0}
				<section class="rounded-[24px] bg-white border border-app-border p-5 shadow-bento">
					<div class="flex items-center gap-2">
						<span class="material-symbols-outlined text-app-primary" aria-hidden="true">sell</span>
						<h2 class="text-lg font-semibold">Промокоди</h2>
					</div>
					<div class="mt-4 space-y-3">
						{#each offers.promo_codes as promo_code (promo_code.code)}
							<div class="rounded-2xl bg-[#f8f7f2] p-3">
								<p class="font-mono text-sm font-bold tracking-wide text-app-primary">{promo_code.code}</p>
								<p class="mt-1 text-xs leading-5 text-[#6e6e73]">{promo_code.description}</p>
							</div>
						{/each}
					</div>
				</section>
			{/if}
		</div>
	{/if}
</main>
