import type { CartItem, MealPlan } from '$lib/cart';

export interface CartStorePayload {
	cartUrl: string | null;
	summary: string;
	totalPrice: number;
	isBudgetExceeded: boolean;
	items: CartItem[];
	mealPlan?: MealPlan | null;
}

export const cartStore = $state<{
	items: CartItem[];
	cartUrl: string | null;
	summary: string;
	totalPrice: number;
	isBudgetExceeded: boolean;
	mealPlan: MealPlan | null;
}>({
	items: [],
	cartUrl: null,
	summary: '',
	totalPrice: 0,
	isBudgetExceeded: false,
	mealPlan: null,
});

export function setCart(payload: CartStorePayload): void {
	cartStore.items = payload.items;
	cartStore.cartUrl = payload.cartUrl;
	cartStore.summary = payload.summary;
	cartStore.totalPrice = payload.totalPrice;
	cartStore.isBudgetExceeded = payload.isBudgetExceeded;
	cartStore.mealPlan = payload.mealPlan ?? null;
}

export function clearCart(): void {
	cartStore.items = [];
	cartStore.cartUrl = null;
	cartStore.summary = '';
	cartStore.totalPrice = 0;
	cartStore.isBudgetExceeded = false;
	cartStore.mealPlan = null;
}

export function cartItemsCount(): number {
	return cartStore.items.reduce((sum, item) => sum + item.quantity, 0);
}
