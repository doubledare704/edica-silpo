# Spec: `create_shopping_cart` integration (silpo-py-mcp 0.2.0)

## 1. Problem

`MCPProductService.create_cart` (`backend/app/services/mcp_service.py`) assumes `get_cart()`
always yields a usable cart id. When the server reports `exists: false` (no active cart),
`_product_value(cart, "id", "cartId", "cart_id")` returns `None` and the service raises
`ValueError("Silpo cart response is missing an id")`. `create_cart_node` catches it and falls
back to a mock `https://silpo.ua/cart/share/mock_*` URL, so real-mode users silently lose
their cart.

silpo-py-mcp 0.2.0 (released 2026-09-05, already bumped in `pyproject.toml`) adds the exact
missing piece: `SilpoClient.create_shopping_cart(...)` → `silpo_create_shopping_cart`,
idempotent (returns the existing `shoppingCartId` when a cart already exists).

## 2. New tool contract (verified against the 0.2.0 mock)

```python
await client.create_shopping_cart(
    address_type="delivery",      # required
    latitude=50.3957,             # required (str | float)
    longitude=30.6217,            # required (str | float)
    delivery_type="DeliveryHome", # required, live enum: DeliveryHome | WideAssortDelivery | SelfPickup | NovaPoshta | B2B
    branch_id="bran-1",           # required
    timeslot_start="...",         # required, ISO
    timeslot_end="...",           # required, ISO
    city=None, street=None, house=None, district=None,  # optional
) -> CreateShoppingCartResult(success=True, shopping_cart_id="cart-...")
```

Resolution chain (all methods verified on the mock):

| Step | Call | Notes |
|---|---|---|
| 1 | `get_cart()` → `CartSummary(cart_id, shopping_cart_id, exists)` | Skip creation when an id exists |
| 2 | `get_delivery_addresses()` → `[DeliveryAddress]` | Preferred source: zero user input |
| 3 | `find_address(text)` → `Address(coordinates=GeoPoint(lat, lng), city, street, ...)` | Only when no saved address but user supplied one |
| 4 | `get_available_delivery_types(lat, lng)` → `[AvailableDeliveryType(type, branch_id, min_order)]` | Prefer `SelfPickup` (min_order 0), else lowest `min_order` |
| 5 | `call_tool("silpo_get_time_slots", {...})` raw | Typed `get_time_slots()` suffers mock/real enum drift (`deliveryType` validation); parse raw payload tolerantly, pick first `isAvailable` slot |
| 6 | `create_shopping_cart(...)` | Then continue with existing `add_or_update_cart_products` flow |

## 3. Constraints

- `AGENTS.md` forbids new nodes, endpoints, and `SilpoAgentState` fields without a spec
  waiver. This document **is** the waiver request: no new nodes/endpoints; two new
  **optional** (`NotRequired`) state fields, backwards compatible.
- No fulfillment data exists in state today. Never invent an address: without a saved
  address or user input, behavior must stay exactly as now (fallback URL + summary).

## 4. Changes

### 4.1 `SilpoAgentState` (+ `TECH_SPEC.md` § State)

```python
delivery_address: NotRequired[str | None]          # user-supplied address text (future input)
fulfillment: NotRequired[dict[str, Any] | None]    # resolved bundle, cached for retries
```

`fulfillment` bundle keys: `address_type, latitude, longitude, delivery_type, branch_id,
timeslot_start, timeslot_end, city?, street?, house?, district?`.
`main.py` initial state sets both to `None` (no frontend contract change).

### 4.2 `MCPProductService`

```python
async def resolve_fulfillment(self, delivery_address: str | None) -> dict[str, Any] | None:
    """Saved address → geocode → delivery type → slot. None when unresolvable."""

async def ensure_cart(self, fulfillment: dict[str, Any] | None) -> str:
    """get_cart id, else create_shopping_cart(**fulfillment). Raises when neither works."""

async def create_cart(
    self, products: list[dict[str, Any]], fulfillment: dict[str, Any] | None = None
) -> str:
    """Existing flow, but cart id comes from ensure_cart(fulfillment)."""
```

- `fetch_products` untouched.
- Every new branch logs at INFO (`logger.info("mcp ensure_cart path=...")`, slots/branch chosen);
  creation failure logs a warning and raises (node converts to fallback URL, summary preserved).

### 4.3 `create_cart_node`

```python
fulfillment = state.get("fulfillment")
if fulfillment is None and not settings.MCP_MOCK_MODE:
    fulfillment = await mcp_product_service.resolve_fulfillment(state.get("delivery_address"))
cart_url = await mcp_product_service.create_cart(state.get("mcp_products", []), fulfillment)
```

Mock-mode path unchanged. `except` fallback (mock URL + summary) unchanged.

## 5. Edge cases

- `exists: false` + resolvable fulfillment → create, then add products. Happy path.
- `exists: false` + no saved address + no `delivery_address` → `resolve_fulfillment`
  returns `None`, `ensure_cart` raises, node keeps today's fallback URL. Logged, not silent.
- Slot list empty / all unavailable → `None` (same as above).
- `create_shopping_cart` raising `SilpoError` → propagates to node fallback.
- Retry loop (`check_constraints` → `plan_domain_logic`) unaffected: fulfillment resolved
  once per `create_cart_node` call; cache it into state on first success to avoid
  re-resolution (node writes back `{"fulfillment": fulfillment}` alongside cart fields).

## 6. Test plan (TDD, `backend/tests/`)

- `test_mcp_ensure_cart.py` (new): existing-cart short-circuit (no create call);
  `exists: false` + fulfillment → `create_shopping_cart` called, id returned;
  `exists: false` + `None` → raises.
- `test_mcp_resolve_fulfillment.py` (new): prefers saved address; prefers SelfPickup,
  else lowest `min_order`; first available slot; `None` when no addresses/slots.
  Mock `SilpoClient` methods with `AsyncMock`; no network.
- `test_create_cart_node.py` (extend): real-mode `exists: false` without fulfillment
  still yields fallback URL + summary (regression lock of current behavior).
- Gate: `uv run ruff format --check backend/ && uv run ruff check . &&
  uv run pyrefly check && uv run pytest backend/tests`.

## 7. Rollout

- **Phase 1 (service-only, shippable alone):** `ensure_cart` + `resolve_fulfillment` +
  unit tests. Node untouched → zero behavior change.
- **Phase 2 (wiring, needs this spec approved):** state fields, `TECH_SPEC.md` update,
  node wiring + fulfillment write-back, regression test.
- **Later (out of scope):** `delivery_address` capture (endpoint param / intent parsing),
  SSE tool events for cart creation, `update_shopping_cart` (promo/slot changes).
