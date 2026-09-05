import logging
from typing import Any

from silpo_py_mcp import SilpoClient
from silpo_py_mcp.exceptions import SilpoError

from ..config import settings

logger = logging.getLogger(__name__)

STATIC_MCP_FALLBACK_CATALOG: dict[str, dict[str, Any]] = {
    "ошийник": {
        "id": "sku-1",
        "title": "Ошийник свинячий",
        "price": 240.0,
        "is_private_label": False,
    },
    "овочі": {
        "id": "sku-2",
        "title": "Овочі для гриля Премія",
        "price": 85.0,
        "is_private_label": True,
    },
    "вода": {
        "id": "sku-3",
        "title": "Вода мінеральна Моршинська",
        "price": 22.0,
        "is_private_label": False,
    },
    "вугілля": {
        "id": "sku-4",
        "title": "Вугілля деревне Премія 2.5 кг",
        "price": 120.0,
        "is_private_label": True,
    },
    "молоко": {
        "id": "sku-5",
        "title": "Молоко Премія 2.5% 900 мл",
        "price": 36.9,
        "is_private_label": True,
    },
    "хліб": {
        "id": "sku-6",
        "title": "Хліб український нарізний",
        "price": 28.5,
        "is_private_label": False,
    },
    "яйця": {
        "id": "sku-7",
        "title": "Яйця курячі С1, 10 шт",
        "price": 54.9,
        "is_private_label": False,
    },
    "сир": {
        "id": "sku-8",
        "title": "Сир Гауда 45% 250 г",
        "price": 89.0,
        "is_private_label": False,
    },
    "яблука": {
        "id": "sku-9",
        "title": "Яблука Гала, 1 кг",
        "price": 42.0,
        "is_private_label": False,
    },
}


class MCPProductService:
    """Service to search and resolve products via Silpo MCP client with local fallback."""

    @staticmethod
    def _product_value(product: Any, *names: str, default: Any = None) -> Any:
        for name in names:
            value = getattr(product, name, None)
            if value is not None:
                return value
            if isinstance(product, dict) and name in product:
                return product[name]
        return default

    @classmethod
    def _normalize_product(cls, product: Any, query: str, quantity: Any, fallback_id: str) -> dict[str, Any]:
        product_id = cls._product_value(product, "productId", "product_id", "id", default=fallback_id)
        normalized = {
            "id": product_id,
            "productId": product_id,
            "title": cls._product_value(product, "title", "name", default=query),
            "price": float(cls._product_value(product, "price", default=100.0)),
            "is_private_label": bool(cls._product_value(product, "is_private_label", "isPrivateLabel", default=False)),
            "quantity": quantity,
        }
        company_id = cls._product_value(product, "companyId", "company_id")
        branch_id = cls._product_value(product, "branchId", "branch_id")
        if company_id is not None:
            normalized["companyId"] = company_id
        if branch_id is not None:
            normalized["branchId"] = branch_id
        return normalized

    @staticmethod
    def _match_fallback(query: str) -> dict[str, Any]:
        query_lower = query.lower()
        for key, prod in STATIC_MCP_FALLBACK_CATALOG.items():
            if key in query_lower:
                return prod.copy()
        return {
            "id": f"sku-gen-{abs(hash(query)) % 1000}",
            "title": query,
            "price": 75.0,
            "is_private_label": "премія" in query_lower,
        }

    async def fetch_products(self, calculated_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not calculated_items:
            return []

        client = SilpoClient.for_mock() if settings.MCP_MOCK_MODE else SilpoClient.for_real_server()
        products: list[dict[str, Any]] = []

        try:
            async with client:
                for item in calculated_items:
                    query = item.get("query", "")
                    quantity = item.get("quantity", 1)
                    prefer_private_label = bool(item.get("prefer_private_label", False))
                    matched_prod: dict[str, Any] | None = None

                    try:
                        if prefer_private_label:
                            result = await client.get_products(query, on_sale=True, limit=5)
                        else:
                            result = await client.get_products(query, limit=5)
                        items = getattr(result, "items", [])
                        if items:
                            private_items = [
                                product
                                for product in items
                                if bool(
                                    self._product_value(product, "is_private_label", "isPrivateLabel", default=False)
                                )
                            ]
                            candidates = private_items if prefer_private_label and private_items else items
                            selected = min(
                                candidates,
                                key=lambda product: float(self._product_value(product, "price", default=100.0)),
                            )
                            matched_prod = self._normalize_product(
                                selected,
                                query,
                                quantity,
                                f"sku-{len(products) + 1}",
                            )
                    except (SilpoError, RuntimeError, IndexError, KeyError, ValueError) as exc:
                        logger.debug("Silpo MCP search error for '%s': %s", query, exc)

                    if matched_prod is None:
                        matched_prod = self._match_fallback(query)
                        matched_prod["quantity"] = quantity

                    products.append(matched_prod)
        except (SilpoError, RuntimeError, OSError, ValueError) as exc:
            logger.warning("Silpo MCP client connection error: %s. Using catalog fallback.", exc)
            for item in calculated_items:
                query = item.get("query", "")
                quantity = item.get("quantity", 1)
                prod = self._match_fallback(query)
                prod["quantity"] = quantity
                products.append(prod)

        return products

    @staticmethod
    def _extract_coords(source: Any) -> tuple[float, float] | None:
        coords = MCPProductService._product_value(source, "coordinates", "coords", "geo", "location")
        if coords is None:
            coords = source
        lat = MCPProductService._product_value(coords, "lat", "latitude")
        lng = MCPProductService._product_value(coords, "lng", "longitude", "lon")
        if lat is None or lng is None:
            return None
        try:
            return float(lat), float(lng)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_delivery_option(entry: Any) -> dict[str, Any] | None:
        raw_type = MCPProductService._product_value(entry, "type", "delivery_type", "deliveryType")
        dtype = getattr(raw_type, "value", raw_type)
        branch_id = MCPProductService._product_value(entry, "branch_id", "branchId")
        min_order = MCPProductService._product_value(entry, "min_order", "minOrder", default=None)
        try:
            min_order_value = float(min_order) if min_order is not None else float("inf")
        except (TypeError, ValueError):
            min_order_value = float("inf")
        if dtype is None or branch_id is None:
            return None
        return {"type": str(dtype), "branch_id": str(branch_id), "min_order": min_order_value}

    @staticmethod
    def _normalize_slot(entry: Any) -> dict[str, str] | None:
        start = MCPProductService._product_value(entry, "startsAt", "start", "starts_at")
        end = MCPProductService._product_value(entry, "endsAt", "end", "ends_at")
        available = MCPProductService._product_value(entry, "isAvailable", "available", "is_available", default=True)
        if not start or not end or not available:
            return None
        return {"start": str(start), "end": str(end)}

    async def resolve_fulfillment(self, delivery_address: str | None) -> dict[str, Any] | None:
        """Resolves cart-creation details: saved address → geocode → delivery type → slot."""
        client = SilpoClient.for_real_server()
        try:
            async with client:
                saved = await client.get_delivery_addresses() or []
                first_saved = saved[0] if saved else None
                text = self._product_value(first_saved, "text", "address") if first_saved is not None else None
                if text is None:
                    text = delivery_address
                if text is None:
                    logger.debug("No saved or supplied delivery address, fulfillment unresolvable")
                    return None

                coords = self._extract_coords(first_saved) if first_saved is not None else None
                geocoded: Any = None
                if coords is None:
                    geocoded = await client.find_address(text)
                    coords = self._extract_coords(geocoded)
                if coords is None:
                    logger.debug("Could not geocode delivery address '%s'", text)
                    return None
                lat, lng = coords

                options = [
                    option
                    for option in (
                        self._normalize_delivery_option(entry)
                        for entry in await client.get_available_delivery_types(lat=lat, lng=lng)
                    )
                    if option is not None
                ]
                if not options:
                    logger.debug("No delivery types available for (%s, %s)", lat, lng)
                    return None
                options.sort(
                    key=lambda option: (0 if option["type"].lower() == "selfpickup" else 1, option["min_order"])
                )
                chosen = options[0]

                raw_slots = await client.call_tool(
                    "silpo_get_time_slots",
                    {
                        "branchId": chosen["branch_id"],
                        "deliveryType": chosen["type"],
                        "deliveryTypes": [chosen["type"]],
                    },
                )
                slots = [
                    slot for slot in (self._normalize_slot(entry) for entry in raw_slots or []) if slot is not None
                ]
                if not slots:
                    logger.debug("No available time slots for branch %s", chosen["branch_id"])
                    return None

                bundle = {
                    "address_type": "delivery",
                    "latitude": lat,
                    "longitude": lng,
                    "delivery_type": chosen["type"],
                    "branch_id": chosen["branch_id"],
                    "timeslot_start": slots[0]["start"],
                    "timeslot_end": slots[0]["end"],
                    "city": self._product_value(geocoded, "city"),
                    "street": self._product_value(geocoded, "street"),
                    "house": self._product_value(geocoded, "house_number", "house"),
                    "district": self._product_value(geocoded, "district"),
                }
                logger.info(
                    "mcp fulfillment resolved type=%s branch=%s slot=%s",
                    chosen["type"],
                    chosen["branch_id"],
                    slots[0]["start"],
                )
                return bundle
        except (SilpoError, RuntimeError, OSError, ValueError) as exc:
            logger.debug("Fulfillment resolution failed: %s", exc)
            return None

    async def _get_or_create_cart_id(self, client: SilpoClient, fulfillment: dict[str, Any] | None) -> tuple[str, Any]:
        """Resolves the cart id and its existing items within one open client session."""
        cart = await client.get_cart()
        cart_id = self._product_value(cart, "id", "cartId", "cart_id", "shopping_cart_id", "shoppingCartId")
        if cart_id:
            logger.info("mcp ensure_cart path=existing cart_id=%s", cart_id)
            return str(cart_id), self._product_value(cart, "items", "products", default=[])
        if fulfillment is None:
            raise ValueError("Silpo cart response is missing an id and no fulfillment details were provided")
        created = await client.create_shopping_cart(**fulfillment)
        new_id = self._product_value(created, "shopping_cart_id", "shoppingCartId", "id", "cartId", "cart_id")
        if not new_id:
            raise ValueError("Silpo cart creation response is missing an id")
        logger.info("mcp ensure_cart path=created cart_id=%s", new_id)
        return str(new_id), []

    async def ensure_cart(self, fulfillment: dict[str, Any] | None) -> str:
        """Returns the active cart id, creating one when the server reports exists=false."""
        client = SilpoClient.for_real_server()
        async with client:
            cart_id, _ = await self._get_or_create_cart_id(client, fulfillment)
            return cart_id

    async def create_cart(self, products: list[dict[str, Any]], fulfillment: dict[str, Any] | None = None) -> str:
        if not products:
            raise ValueError("Cannot create a cart without products")

        client = SilpoClient.for_real_server()
        items: list[dict[str, Any]] = []
        for product in products:
            product_id = product.get("productId") or product.get("id")
            if not product_id:
                raise ValueError("Cart product is missing productId")
            cart_item = {
                "productId": product_id,
                "quantity": int(product.get("quantity", 1) or 1),
            }
            for key in ("companyId", "branchId"):
                if product.get(key) is not None:
                    cart_item[key] = product[key]
            items.append(cart_item)

        async with client:
            cart_id, existing_items = await self._get_or_create_cart_id(client, fulfillment)
            if existing_items:
                await client.clear_cart(cart_id)
            result = await client.add_or_update_cart_products(cart_id, items=items)

        share_url = self._product_value(result, "share_url", "shareUrl", "url")
        return share_url or f"https://silpo.ua/cart/{cart_id}"


mcp_product_service = MCPProductService()
