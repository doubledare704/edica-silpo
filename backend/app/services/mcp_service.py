import logging
import math
import uuid
from typing import Any

from silpo_py_mcp import SilpoClient
from silpo_py_mcp.exceptions import SilpoError

from ..config import settings

logger = logging.getLogger(__name__)

MOCK_SHOPPING_CONTEXT: dict[str, str] = {
    "branch_id": "bran-1",
    "delivery_type": "SelfPickup",
    "timeslot_start": "2026-09-06T10:00:00",
    "timeslot_end": "2026-09-06T12:00:00",
}

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
            if isinstance(product, dict) and name in product:
                return product[name]
            value = getattr(product, name, None)
            if value is not None and not callable(value):
                return value
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
        slug = cls._product_value(product, "slug")
        if slug is not None:
            normalized["slug"] = str(slug)
        image_url = cls._product_value(product, "image_url", "imageUrl", "image")
        if image_url is not None:
            normalized["image_url"] = str(image_url)
        return normalized

    @staticmethod
    def _match_fallback(query: str) -> dict[str, Any]:
        query_lower = query.lower()
        for key, prod in STATIC_MCP_FALLBACK_CATALOG.items():
            if key in query_lower:
                matched = prod.copy()
                matched["is_fallback"] = True
                return matched
        return {
            "id": f"sku-gen-{abs(hash(query)) % 1000}",
            "title": query,
            "price": 75.0,
            "is_private_label": "премія" in query_lower,
            "is_fallback": True,
        }

    @staticmethod
    def _line_total(product: Any, quantity: int) -> float:
        try:
            price = float(MCPProductService._product_value(product, "price", default=100.0))
        except (TypeError, ValueError):
            price = 100.0
        return price * quantity

    async def search_one(
        self,
        query: str,
        quantity: int = 1,
        prefer_private_label: bool = False,
        max_price: float | None = None,
        category: str | None = None,
        context: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        """Resolves one query to the cheapest fitting product, or None when over ceiling."""

        def with_category(prod: dict[str, Any]) -> dict[str, Any]:
            if category is not None:
                prod["category"] = category
            return prod

        def fallback_or_none() -> dict[str, Any] | None:
            # Static catalog is demo/offline data: only fabricate it when no live
            # catalog is reachable (no context) or in mock mode. With a live
            # context a miss is an honest miss — fabricated SKUs would fail cart
            # validation downstream (non-UUID productId, no company/branch).
            if context is not None and not settings.MCP_MOCK_MODE:
                return None
            prod = self._match_fallback(query)
            prod["quantity"] = quantity
            if max_price is not None and float(prod.get("price", 0.0)) * quantity > max_price:
                return None
            return with_category(prod)

        if context is None:
            return fallback_or_none()

        client = SilpoClient.for_mock() if settings.MCP_MOCK_MODE else SilpoClient.for_real_server()
        try:
            async with client:
                try:
                    result = await client.find_products_batch(
                        context["branch_id"],
                        context["delivery_type"],
                        context["timeslot_start"],
                        context["timeslot_end"],
                        [query],
                        limit=5,
                    )
                except (SilpoError, RuntimeError, IndexError, KeyError, ValueError) as exc:
                    logger.debug("Silpo MCP batch search error for '%s': %s", query, exc)
                    return fallback_or_none()
                results = self._product_value(result, "results", default={}) or {}
                items = list(results.get(query, [])) if isinstance(results, dict) else []
                if max_price is not None:
                    items = [product for product in items if self._line_total(product, quantity) <= max_price]
                if not items:
                    return fallback_or_none()
                private_items = [
                    product
                    for product in items
                    if bool(self._product_value(product, "is_private_label", "isPrivateLabel", default=False))
                ]
                candidates = private_items if prefer_private_label and private_items else items
                selected = min(candidates, key=lambda product: self._line_total(product, 1))
                return with_category(self._normalize_product(selected, query, quantity, "sku-search"))
        except (SilpoError, RuntimeError, OSError, ValueError) as exc:
            logger.warning("Silpo MCP client connection error: %s. Using catalog fallback.", exc)
            return fallback_or_none()

    async def fetch_products(
        self,
        calculated_items: list[dict[str, Any]],
        max_price: float | None = None,
        context: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        if not calculated_items:
            return []
        products: list[dict[str, Any]] = []
        for item in calculated_items:
            matched = await self.search_one(
                item.get("query", ""),
                quantity=item.get("quantity", 1),
                prefer_private_label=bool(item.get("prefer_private_label", False)),
                max_price=max_price,
                category=item.get("category"),
                context=context,
            )
            if matched is not None:
                products.append(matched)
        return products

    async def fetch_promo_products(
        self,
        context: dict[str, str] | None,
        max_price: float | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Returns in-stock promo products within budget, empty when unavailable."""
        if context is None:
            return []
        client = SilpoClient.for_mock() if settings.MCP_MOCK_MODE else SilpoClient.for_real_server()
        try:
            async with client:
                result = await client.get_products(
                    context["branch_id"],
                    context["delivery_type"],
                    context["timeslot_start"],
                    context["timeslot_end"],
                    must_have_promotion=True,
                    in_stock=True,
                    to_price=max_price,
                    limit=limit,
                )
                items = list(self._product_value(result, "items", default=[]) or [])
        except (SilpoError, RuntimeError, OSError, ValueError) as exc:
            logger.debug("Silpo MCP promo products error: %s", exc)
            return []
        return [
            {
                **self._normalize_product(
                    entry, str(self._product_value(entry, "title", "name", default="Акція")), 1, f"promo-{i}"
                ),
                "is_promo": True,
                "category": "promo",
            }
            for i, entry in enumerate(items)
        ]

    @classmethod
    def _normalize_promotion(cls, promotion: Any) -> dict[str, Any]:
        return {
            "id": str(cls._product_value(promotion, "id", "code", default="")),
            "title": str(cls._product_value(promotion, "title", default="Акція")),
            "description": cls._product_value(promotion, "description"),
            "discount_percent": cls._product_value(promotion, "discount_percent", "discountPercent"),
            "price_from": cls._product_value(promotion, "price_from", "priceFrom"),
            "price_to": cls._product_value(promotion, "price_to", "priceTo"),
            "starts_at": cls._product_value(promotion, "starts_at", "startsAt"),
            "ends_at": cls._product_value(promotion, "ends_at", "endsAt"),
            "is_price_of_week": bool(cls._product_value(promotion, "is_price_of_week", "isPriceOfWeek", default=False)),
            "image_url": cls._product_value(promotion, "image_url", "imageUrl"),
        }

    @classmethod
    def _normalize_offer_product(cls, product: Any, index: int) -> dict[str, Any]:
        normalized = cls._normalize_product(
            product,
            str(cls._product_value(product, "title", "name", default="Товар зі знижкою")),
            1,
            f"promo-{index}",
        )
        old_price = cls._product_value(product, "old_price", "oldPrice")
        price = float(normalized["price"])
        discount_percent = None
        if old_price is not None:
            try:
                old_price_value = float(old_price)
                if old_price_value > price:
                    discount_percent = round((old_price_value - price) / old_price_value * 100, 1)
            except (TypeError, ValueError):
                old_price = None
        normalized.update(
            {
                "old_price": old_price,
                "discount_percent": discount_percent,
                "is_promo": True,
            }
        )
        return normalized

    @classmethod
    def _normalize_loyalty(cls, loyalty: Any) -> dict[str, Any]:
        return {
            "card_number": str(cls._product_value(loyalty, "card_number", "cardNumber", default="")),
            "status": str(cls._product_value(loyalty, "status", default="")),
            "bonus_balance": float(cls._product_value(loyalty, "bonus_balance", "bonusBalance", default=0.0) or 0.0),
            "bonus_earned": float(cls._product_value(loyalty, "bonus_earned", "bonusEarned", default=0.0) or 0.0),
        }

    @classmethod
    def _normalize_personal_promo(cls, promo: Any) -> dict[str, Any]:
        return {
            "id": str(cls._product_value(promo, "promo_id", "promoId", "id", default="")),
            "title": str(cls._product_value(promo, "title", default="Персональна пропозиція")),
            "description": cls._product_value(promo, "description"),
            "expires_at": cls._product_value(promo, "expires_at", "expiresAt"),
        }

    @classmethod
    def _normalize_coupon(cls, coupon: Any) -> dict[str, Any]:
        return {
            "id": str(cls._product_value(coupon, "coupon_id", "couponId", "id", default="")),
            "title": str(cls._product_value(coupon, "title", default="Купон")),
            "discount": float(cls._product_value(coupon, "discount", default=0.0) or 0.0),
            "expires_at": cls._product_value(coupon, "expires_at", "expiresAt"),
            "barcode": cls._product_value(coupon, "barcode"),
        }

    @classmethod
    def _normalize_promo_code(cls, promo_code: Any) -> dict[str, Any]:
        return {
            "code": str(cls._product_value(promo_code, "code", default="")),
            "description": cls._product_value(promo_code, "description"),
            "expires_at": cls._product_value(promo_code, "expires_at", "expiresAt"),
        }

    async def get_offers_overview(self, delivery_address: str | None = None) -> dict[str, Any]:
        """Loads loyalty, branch promotions, and personal offers from Silpo MCP."""
        context = await self.resolve_shopping_context(delivery_address)
        client = SilpoClient.for_mock() if settings.MCP_MOCK_MODE else SilpoClient.for_real_server()
        promotions: list[dict[str, Any]] = []
        promo_products: list[dict[str, Any]] = []
        loyalty: dict[str, Any] = self._normalize_loyalty(None)
        personal_promos: list[dict[str, Any]] = []
        coupons: list[dict[str, Any]] = []
        promo_codes: list[dict[str, Any]] = []
        try:
            async with client:
                loyalty = self._normalize_loyalty(await client.get_loyalty_info())
                personal_promos = [self._normalize_personal_promo(entry) for entry in await client.get_promos()]
                coupons = [self._normalize_coupon(entry) for entry in await client.get_coupons()]
                promo_codes = [self._normalize_promo_code(entry) for entry in await client.get_promo_codes()]
                if context is not None:
                    promotions = [
                        self._normalize_promotion(entry)
                        for entry in await client.get_promotions(
                            context["branch_id"],
                            context["delivery_type"],
                            context["timeslot_start"],
                            context["timeslot_end"],
                        )
                    ]
                    result = await client.get_products(
                        context["branch_id"],
                        context["delivery_type"],
                        context["timeslot_start"],
                        context["timeslot_end"],
                        must_have_promotion=True,
                        in_stock=True,
                        limit=12,
                    )
                    promo_products = [
                        self._normalize_offer_product(entry, index)
                        for index, entry in enumerate(self._product_value(result, "items", default=[]) or [])
                    ]
        except (SilpoError, RuntimeError, OSError, ValueError) as exc:
            logger.warning("Silpo MCP offers lookup failed: %s", exc)

        return {
            "loyalty": loyalty,
            "promotions": promotions,
            "promo_products": promo_products,
            "personal_promos": personal_promos,
            "coupons": coupons,
            "promo_codes": promo_codes,
        }

    @classmethod
    def _normalize_profile(cls, profile: Any) -> dict[str, Any]:
        return {
            "name": cls._product_value(profile, "name"),
            "phone": cls._product_value(profile, "phone"),
            "email": cls._product_value(profile, "email"),
            "birth_date": cls._product_value(profile, "birth_date", "birthDate"),
        }

    @classmethod
    def _normalize_profile_address(cls, address: Any) -> dict[str, Any]:
        coordinates = cls._extract_coords(address)
        return {
            "address_id": str(cls._product_value(address, "address_id", "addressId", "id", default="")),
            "label": cls._product_value(address, "label", "tag"),
            "text": cls._product_value(address, "text", "address"),
            "coordinates": {"latitude": coordinates[0], "longitude": coordinates[1]}
            if coordinates is not None
            else None,
        }

    @classmethod
    def _normalize_branch(cls, branch: Any) -> dict[str, Any]:
        coordinates = cls._extract_coords(branch)
        return {
            "branch_id": str(cls._product_value(branch, "branch_id", "branchId", default="")),
            "name": str(cls._product_value(branch, "name", default="Сільпо")),
            "city": cls._product_value(branch, "city"),
            "address": cls._product_value(branch, "address"),
            "display_address": cls._branch_display_address(branch),
            "latitude": coordinates[0] if coordinates is not None else None,
            "longitude": coordinates[1] if coordinates is not None else None,
            "has_pickup": bool(cls._product_value(branch, "has_pickup", "hasPickup", default=False)),
            "has_nova_poshta": bool(cls._product_value(branch, "has_nova_poshta", "hasNovaPoshta", default=False)),
        }

    @classmethod
    def _normalize_delivery_type(cls, delivery_type: Any) -> dict[str, Any]:
        raw_type = cls._product_value(delivery_type, "type", "delivery_type", "deliveryType", default="")
        return {
            "type": str(getattr(raw_type, "value", raw_type)),
            "description": cls._product_value(delivery_type, "description"),
            "branch_id": cls._product_value(delivery_type, "branch_id", "branchId"),
            "min_order": cls._product_value(delivery_type, "min_order", "minOrder"),
        }

    async def get_profile_overview(self, delivery_address: str | None = None) -> dict[str, Any]:
        """Loads the MCP profile and the delivery data used by profile preferences."""
        client = SilpoClient.for_mock() if settings.MCP_MOCK_MODE else SilpoClient.for_real_server()
        profile: dict[str, Any] = {"name": None, "phone": None, "email": None, "birth_date": None}
        loyalty: dict[str, Any] = self._normalize_loyalty(None)
        addresses: list[dict[str, Any]] = []
        branches: list[dict[str, Any]] = []
        delivery_types: list[dict[str, Any]] = []
        try:
            async with client:
                profile = self._normalize_profile(await client.get_profile())
                loyalty = self._normalize_loyalty(await client.get_loyalty_info())
                addresses = [
                    self._normalize_profile_address(entry)
                    for entry in await client.get_delivery_addresses()
                    if self._product_value(entry, "text", "address")
                ]
                branches = [self._normalize_branch(entry) for entry in await client.list_branches(limit=20)]

                coordinates = self._extract_coords(addresses[0]) if addresses else None
                if coordinates is None and delivery_address:
                    coordinates = self._extract_coords(await client.find_address(delivery_address))
                if coordinates is not None:
                    delivery_types = [
                        self._normalize_delivery_type(entry)
                        for entry in await client.get_available_delivery_types(
                            latitude=coordinates[0], longitude=coordinates[1]
                        )
                    ]
        except (SilpoError, RuntimeError, OSError, ValueError) as exc:
            logger.warning("Silpo MCP profile lookup failed: %s", exc)

        return {
            "profile": profile,
            "loyalty": loyalty,
            "addresses": addresses,
            "delivery_types": delivery_types,
            "branches": branches,
        }

    async def fetch_similar(self, slug: str, context: dict[str, str] | None) -> list[dict[str, Any]]:
        """Returns products similar to the given slug, empty on any failure."""
        if context is None:
            return []
        client = SilpoClient.for_mock() if settings.MCP_MOCK_MODE else SilpoClient.for_real_server()
        try:
            async with client:
                entries = await client.get_similar_products(context["branch_id"], slug, limit=5) or []
        except (SilpoError, RuntimeError, OSError, ValueError) as exc:
            logger.debug("Silpo MCP similar error for '%s': %s", slug, exc)
            return []
        return [self._normalize_product(entry, slug, 1, f"sim-{i}") for i, entry in enumerate(entries)]

    async def fetch_product_details(self, slug: str, context: dict[str, str] | None) -> dict[str, Any] | None:
        """Returns card metadata (description, composition, nutrition) for a slug, None on failure."""
        if context is None:
            return None
        client = SilpoClient.for_mock() if settings.MCP_MOCK_MODE else SilpoClient.for_real_server()
        try:
            async with client:
                entry = await client.get_product_details(
                    context["branch_id"],
                    slug,
                    context["delivery_type"],
                    context["timeslot_start"],
                    context["timeslot_end"],
                )
        except (SilpoError, RuntimeError, OSError, ValueError) as exc:
            logger.debug("Silpo MCP details error for '%s': %s", slug, exc)
            return None
        if entry is None:
            return None
        details = {
            key: self._product_value(entry, key)
            for key in ("description", "composition", "nutritional_value", "attributes")
        }
        details = {key: value for key, value in details.items() if value is not None}
        return details or None

    async def fetch_replacements(
        self, ref_product: dict[str, Any], context: dict[str, str] | None
    ) -> list[dict[str, Any]]:
        """Returns replacement candidates for a reference product, empty on any failure."""
        product_id = ref_product.get("productId") or ref_product.get("id")
        company_id = ref_product.get("companyId") or ref_product.get("company_id")
        if context is None or not product_id or not company_id:
            return []
        client = SilpoClient.for_mock() if settings.MCP_MOCK_MODE else SilpoClient.for_real_server()
        try:
            async with client:
                entries = (
                    await client.get_replacements(
                        context["branch_id"], str(company_id), context["delivery_type"], [str(product_id)]
                    )
                    or []
                )
        except (SilpoError, RuntimeError, OSError, ValueError) as exc:
            logger.debug("Silpo MCP replacements error: %s", exc)
            return []
        products = []
        for i, entry in enumerate(entries):
            candidate = self._product_value(entry, "replacement", default=entry)
            products.append(self._normalize_product(candidate, str(i), 1, f"repl-{i}"))
        return products

    async def fetch_categories(self, context: dict[str, str] | None) -> list[dict[str, Any]]:
        """Returns catalog categories, empty on any failure."""
        if context is None:
            return []
        client = SilpoClient.for_mock() if settings.MCP_MOCK_MODE else SilpoClient.for_real_server()
        try:
            async with client:
                entries = await client.get_categories(context["branch_id"]) or []
        except (SilpoError, RuntimeError, OSError, ValueError) as exc:
            logger.debug("Silpo MCP categories error: %s", exc)
            return []
        return [
            {
                "id": str(self._product_value(entry, "id", "category_id", default=i)),
                "name": str(self._product_value(entry, "name", "title", default="")),
            }
            for i, entry in enumerate(entries)
        ]

    @staticmethod
    def _slot_bounds(slot: Any) -> tuple[str, str | None] | None:
        """Extracts (start, end) bounds from a slot dict/model/string."""
        if isinstance(slot, str):
            return (slot, None)
        if slot is None:
            return None
        start = MCPProductService._product_value(slot, "startsAt", "starts_at", "start")
        if start is None:
            return None
        end = MCPProductService._product_value(slot, "endsAt", "ends_at", "end")
        return (str(start), str(end) if end is not None else None)

    @staticmethod
    def _normalize_cart_detail(detail: Any) -> dict[str, Any] | None:
        """Flattens a cart detail envelope into plain snake_case fields."""
        if detail is None:
            return None
        branch_id = MCPProductService._product_value(detail, "branch_id", "branchId")
        delivery_type = MCPProductService._product_value(detail, "delivery_type", "deliveryType")
        if branch_id is None or delivery_type is None:
            return None
        totals = MCPProductService._product_value(detail, "totals", default={}) or {}
        loyalty = MCPProductService._product_value(detail, "loyalty", default={}) or {}
        return {
            "cart_id": str(
                MCPProductService._product_value(detail, "cart_id", "cartId", "shopping_cart_id", default="")
            ),
            "branch_id": str(branch_id),
            "delivery_type": str(delivery_type),
            "timeslot": MCPProductService._product_value(detail, "timeslot"),
            "items": list(MCPProductService._product_value(detail, "items", default=[]) or []),
            "shipments": list(MCPProductService._product_value(detail, "shipments", default=[]) or []),
            "address": MCPProductService._product_value(detail, "address", default={}) or {},
            "total_price": totals.get("total_price", totals.get("totalPrice"))
            if isinstance(totals, dict)
            else float(getattr(totals, "total_price", 0.0) or 0.0),
            "loyalty": loyalty,
            "validations": [
                {
                    "code": str(MCPProductService._product_value(entry, "code", default="")),
                    "message": str(MCPProductService._product_value(entry, "message", default="")),
                    "severity": str(MCPProductService._product_value(entry, "severity", default="info")),
                }
                for entry in (MCPProductService._product_value(detail, "validations", default=[]) or [])
            ],
            "checkout_web_link": MCPProductService._product_value(detail, "checkout_web_link", "checkoutWebLink"),
            "checkout_mobile_link": MCPProductService._product_value(
                detail, "checkout_mobile_link", "checkoutMobileLink"
            ),
        }

    async def _fetch_cart_detail(self, client: Any, cart_id: str) -> dict[str, Any] | None:
        try:
            return self._normalize_cart_detail(await client.get_cart_by_id(cart_id))
        except (SilpoError, RuntimeError, OSError, ValueError, AttributeError) as exc:
            logger.debug("Could not load cart detail for '%s': %s", cart_id, exc)
            return None

    @staticmethod
    def _loyalty_hint(loyalty: Any) -> str | None:
        """Ask-don't-apply bonus prompt per the official bonus flow."""
        get = MCPProductService._product_value
        enabled = get(loyalty, "is_enabled", "isEnabled", default=False)
        requested = get(loyalty, "bonus_requested", "bonusRequested", default=None)
        try:
            available = float(get(loyalty, "bonus_available", "bonusAvailable", default=0.0) or 0.0)
        except (TypeError, ValueError):
            return None
        if enabled and available > 0 and requested is None:
            return f"У вас є {available:g} балабонусів. Скажіть «застосуй бонуси», щоб використати їх."
        return None

    async def _validated_slot(
        self, client: Any, branch_id: str, delivery_type: str, slot: Any
    ) -> tuple[str, str | None] | None:
        """Returns current slot bounds when still bookable, else the first available slot."""
        try:
            slots = await client.get_time_slots(branch_id, delivery_types=[delivery_type]) or []
        except (SilpoError, RuntimeError, OSError, ValueError) as exc:
            logger.debug("Could not validate slot for branch '%s': %s", branch_id, exc)
            return self._slot_bounds(slot)
        bounds = [self._slot_bounds(entry) for entry in slots]
        bounds = [entry for entry in bounds if entry is not None]
        if not bounds:
            return self._slot_bounds(slot)
        current = self._slot_bounds(slot)
        if current is not None and any(start == current[0] for start, _ in bounds):
            return current
        logger.info("mcp slot changed branch=%s old=%s new=%s", branch_id, current, bounds[0])
        return bounds[0]

    async def _context_from_cart(self, client: Any) -> dict[str, str] | None:
        """Official flow steps 1-3: cart → detail → validated slot context."""
        try:
            cart = await client.get_cart()
        except (SilpoError, RuntimeError, OSError, ValueError) as exc:
            logger.debug("Could not load active cart: %s", exc)
            return None
        cart_id = self._product_value(cart, "cart_id", "cartId", "shopping_cart_id", "shoppingCartId", "id")
        if not cart_id:
            return None
        detail = await self._fetch_cart_detail(client, str(cart_id))
        if detail is None:
            return None
        bounds = await self._validated_slot(client, detail["branch_id"], detail["delivery_type"], detail["timeslot"])
        if bounds is None:
            return None
        return {
            "branch_id": detail["branch_id"],
            "delivery_type": detail["delivery_type"],
            "timeslot_start": bounds[0],
            "timeslot_end": bounds[1] or bounds[0],
        }

    async def resolve_shopping_context(self, delivery_address: str | None) -> dict[str, str] | None:
        """Resolves branch/delivery/slot context: active cart first, address flow fallback."""
        if settings.MCP_MOCK_MODE:
            return dict(MOCK_SHOPPING_CONTEXT)
        client = SilpoClient.for_real_server()
        try:
            async with client:
                context = await self._context_from_cart(client)
                if context is not None:
                    return context
        except (SilpoError, RuntimeError, OSError, ValueError) as exc:
            logger.debug("Cart-first context resolution failed: %s", exc)
        fulfillment = await self.resolve_fulfillment(delivery_address)
        if fulfillment is None:
            return None
        return {
            "branch_id": str(fulfillment["branch_id"]),
            "delivery_type": str(fulfillment["delivery_type"]),
            "timeslot_start": str(fulfillment["timeslot_start"]),
            "timeslot_end": str(fulfillment["timeslot_end"]),
        }

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

    FETCH_BRANCHES_LIMIT = 500

    @staticmethod
    def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        radius_km = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
        )
        return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _branch_distance_km(branch: Any, lat: float, lng: float) -> float:
        coords = MCPProductService._extract_coords(branch)
        if coords is None:
            return math.inf
        return MCPProductService._haversine_km(lat, lng, *coords)

    @staticmethod
    def _branch_display_address(branch: Any) -> str:
        parts = [
            part
            for part in (
                MCPProductService._product_value(branch, "city"),
                MCPProductService._product_value(branch, "address"),
            )
            if part
        ]
        if parts:
            return ", ".join(str(part) for part in parts)
        return str(
            MCPProductService._product_value(
                branch, "name", default=MCPProductService._product_value(branch, "branch_id", "branchId", default="")
            )
        )

    async def find_nearest_branches(self, address_text: str, limit: int = 10) -> dict[str, Any]:
        """Geocodes an address, lists Silpo branches, returns the nearest ones first."""
        client = SilpoClient.for_mock() if settings.MCP_MOCK_MODE else SilpoClient.for_real_server()
        async with client:
            try:
                geocoded = await client.find_address(address_text)
            except (SilpoError, RuntimeError, OSError, ValueError) as exc:
                raise ValueError(f"Could not geocode address '{address_text}': {exc}") from exc
            coords = self._extract_coords(geocoded)
            if coords is None:
                raise ValueError(f"Could not geocode address '{address_text}'")
            lat, lng = coords

            try:
                branches = await client.list_branches(limit=self.FETCH_BRANCHES_LIMIT)
            except (SilpoError, RuntimeError, OSError, ValueError) as exc:
                raise ValueError(f"Could not list Silpo branches: {exc}") from exc

            ranked = sorted(
                (
                    branch
                    for branch in branches
                    if self._product_value(branch, "is_open", "open", default=None) is not False
                ),
                key=lambda branch: self._branch_distance_km(branch, lat, lng),
            )
            stores: list[dict[str, Any]] = []
            for branch in ranked:
                distance = self._branch_distance_km(branch, lat, lng)
                if distance == math.inf:
                    continue
                branch_coords = self._extract_coords(branch)
                stores.append(
                    {
                        "branch_id": str(self._product_value(branch, "branch_id", "branchId", default="")),
                        "name": str(self._product_value(branch, "name", default="Сільпо")),
                        "city": self._product_value(branch, "city"),
                        "address": self._product_value(branch, "address"),
                        "display_address": self._branch_display_address(branch),
                        "distance_km": round(distance, 1),
                        "has_pickup": bool(self._product_value(branch, "has_pickup", "hasPickup", default=False)),
                        "latitude": branch_coords[0] if branch_coords is not None else None,
                        "longitude": branch_coords[1] if branch_coords is not None else None,
                    }
                )
                if len(stores) >= max(limit, 0):
                    break
            return {
                "query": address_text,
                "resolved_address": str(self._product_value(geocoded, "text", "address", default=address_text)),
                "latitude": lat,
                "longitude": lng,
                "stores": stores,
            }

    async def find_nearby_contexts(
        self,
        delivery_address: str | None,
        primary: dict[str, str] | None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Returns purchasable contexts of nearby branches, closest first.

        The picker re-searches assortment misses (`not_found` / `rejected_irrelevant`)
        in these branches when the primary branch cannot cover the weekly goal.
        Mock mode stays single-branch; without a delivery address the user cannot
        be located, so no candidates are returned.
        """
        if settings.MCP_MOCK_MODE:
            logger.debug("Nearby branch lookup skipped: mock mode stays single-branch")
            return []
        if not delivery_address or primary is None:
            logger.info("nearby branches resolved=0 reason=no_delivery_address")
            return []
        delivery_type = primary.get("delivery_type", "")
        if not delivery_type:
            logger.info("nearby branches resolved=0 reason=no_delivery_type")
            return []
        cap = limit if limit is not None else settings.MAX_NEARBY_BRANCHES
        try:
            ranked = await self.find_nearest_branches(delivery_address, limit=cap + 5)
        except (ValueError, SilpoError, RuntimeError, OSError) as exc:
            logger.debug("Nearby branch ranking failed: %s", exc)
            return []
        primary_branch = primary.get("branch_id")
        contexts: list[dict[str, Any]] = []
        skipped_primary = 0
        skipped_far = 0
        skipped_no_slot = 0
        client = SilpoClient.for_real_server()
        try:
            async with client:
                for store in ranked.get("stores", []):
                    if len(contexts) >= max(cap, 0):
                        break
                    branch_id = str(store.get("branch_id", ""))
                    if not branch_id or branch_id == primary_branch:
                        skipped_primary += 1
                        continue
                    try:
                        distance = float(store.get("distance_km", math.inf))
                    except (TypeError, ValueError):
                        distance = math.inf
                    if distance > settings.MAX_NEARBY_DISTANCE_KM:
                        skipped_far += 1
                        continue
                    try:
                        raw_slots = await client.get_time_slots(branch_id, delivery_types=[delivery_type])
                    except (SilpoError, RuntimeError, OSError, ValueError) as exc:
                        logger.debug("No slots for nearby branch %s: %s", branch_id, exc)
                        skipped_no_slot += 1
                        continue
                    slot = next(
                        (parsed for parsed in (self._normalize_slot(e) for e in raw_slots or []) if parsed is not None),
                        None,
                    )
                    if slot is None:
                        skipped_no_slot += 1
                        continue
                    contexts.append(
                        {
                            "branch_id": branch_id,
                            "delivery_type": delivery_type,
                            "timeslot_start": slot["start"],
                            "timeslot_end": slot["end"],
                            "distance_km": store.get("distance_km"),
                            "display_address": store.get("display_address"),
                        }
                    )
        except (SilpoError, RuntimeError, OSError, ValueError) as exc:
            logger.debug("Nearby branch context resolution failed: %s", exc)
            return []
        logger.info(
            "nearby branches resolved=%d primary=%s delivery=%s skipped_primary=%d skipped_far=%d skipped_no_slot=%d",
            len(contexts),
            primary_branch,
            delivery_type,
            skipped_primary,
            skipped_far,
            skipped_no_slot,
        )
        return contexts

    async def list_saved_addresses(self) -> list[dict[str, Any]]:
        """Returns the user's saved Silpo delivery addresses (empty when unavailable)."""
        client = SilpoClient.for_mock() if settings.MCP_MOCK_MODE else SilpoClient.for_real_server()
        try:
            async with client:
                saved = await client.get_delivery_addresses() or []
        except (SilpoError, RuntimeError, OSError, ValueError) as exc:
            logger.debug("Could not load saved delivery addresses: %s", exc)
            return []
        addresses: list[dict[str, Any]] = []
        for entry in saved:
            text = self._product_value(entry, "text", "address", default=None)
            if text is None:
                continue
            addresses.append(
                {
                    "address_id": str(self._product_value(entry, "address_id", "addressId", default="")),
                    "label": self._product_value(entry, "label"),
                    "text": str(text),
                }
            )
        return addresses

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

                raw_slots = await client.get_time_slots(chosen["branch_id"], delivery_types=[chosen["type"]])
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

    @staticmethod
    def _validate_cart_item(product: dict[str, Any]) -> str | None:
        """Returns the rejection reason when the product cannot be written to a live cart."""
        product_id = product.get("productId") or product.get("id")
        if not product_id:
            return "missing productId"
        try:
            uuid.UUID(str(product_id))
        except (ValueError, AttributeError, TypeError):
            return f"productId {product_id!r} is not a UUID (static fallback, not a live catalog product)"
        for key in ("companyId", "branchId"):
            if not product.get(key):
                return f"missing {key}"
        return None

    @staticmethod
    def _delivery_differs(detail: dict[str, Any], fulfillment: dict[str, Any]) -> bool:
        bounds = MCPProductService._slot_bounds(detail.get("timeslot"))
        current_start = bounds[0] if bounds else None
        return (
            detail.get("branch_id") != fulfillment.get("branch_id")
            or detail.get("delivery_type") != fulfillment.get("delivery_type")
            or current_start != fulfillment.get("timeslot_start")
        )

    @staticmethod
    def _build_shipments(items: list[dict[str, Any]], branch_id: str) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            company_id = str(item.get("companyId") or "")
            grouped.setdefault(company_id, []).append(
                {"productId": item["productId"], "quantity": item.get("quantity", 1)}
            )
        return [
            {"branchId": branch_id, "companyId": company_id, "items": lines} for company_id, lines in grouped.items()
        ]

    async def _apply_delivery_settings(
        self,
        client: Any,
        cart_id: str,
        detail: dict[str, Any],
        fulfillment: dict[str, Any],
        items: list[dict[str, Any]],
    ) -> None:
        """Best-effort delivery update: a rejected update must not kill a valid cart write."""
        shipments = detail.get("shipments") or self._build_shipments(items, str(fulfillment["branch_id"]))
        try:
            await client.update_shopping_cart(
                cart_id,
                str(fulfillment["delivery_type"]),
                {"start": fulfillment["timeslot_start"], "end": fulfillment["timeslot_end"]},
                self._fulfillment_address(fulfillment),
                shipments,
                branch_id=str(fulfillment["branch_id"]),
            )
        except (SilpoError, RuntimeError, OSError, ValueError) as exc:
            logger.warning("mcp delivery update failed, keeping cart settings: %s", exc)

    @staticmethod
    def _fulfillment_address(fulfillment: dict[str, Any]) -> dict[str, Any]:
        return {
            key: fulfillment[key]
            for key in ("address_type", "latitude", "longitude", "city", "street", "house", "district")
            if fulfillment.get(key) is not None
        }

    async def create_cart(
        self, products: list[dict[str, Any]], fulfillment: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Official fill-cart flow: ensure cart → clear stale → apply delivery → upsert → verify.

        An empty product list still ensures a real cart (clearing stale items under
        replace semantics) and returns its URL instead of raising, so all-miss
        queries surface an honest empty cart rather than a mock fallback link.
        Returns cart_url, checkout_url, verified_total, validations, loyalty_hint
        and the fulfillment used.
        """
        invalid = [
            f"{product.get('title', product.get('productId') or product.get('id'))}: {reason}"
            for product in products
            if (reason := self._validate_cart_item(product)) is not None
        ]
        if invalid:
            raise ValueError(
                f"Cannot write cart: {len(invalid)} product(s) are not real Silpo products: {'; '.join(invalid)}"
            )

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
            cart = await client.get_cart()
            cart_id = self._product_value(cart, "cart_id", "cartId", "shopping_cart_id", "shoppingCartId", "id")
            detail = await self._fetch_cart_detail(client, str(cart_id)) if cart_id else None
            if detail is None:
                if fulfillment is None:
                    raise ValueError("Silpo has no active cart and no fulfillment details were provided")
                created = await client.create_shopping_cart(**fulfillment)
                cart_id = self._product_value(created, "shopping_cart_id", "shoppingCartId", "cart_id", "cartId", "id")
                if not cart_id:
                    raise ValueError("Silpo cart creation response is missing an id")
                cart_id = str(cart_id)
            if detail is not None and detail.get("items"):
                try:
                    await client.clear_cart(str(cart_id))
                except (SilpoError, RuntimeError, OSError, ValueError) as exc:
                    logger.warning("mcp cart clear failed, upserting into dirty cart: %s", exc)
            if items:
                await client.add_or_update_cart_products(str(cart_id), products=items)
            if fulfillment is not None and items:
                refreshed = await self._fetch_cart_detail(client, str(cart_id))
                if refreshed is not None and self._delivery_differs(refreshed, fulfillment):
                    await self._apply_delivery_settings(client, str(cart_id), refreshed, fulfillment, items)
            verified = await self._fetch_cart_detail(client, str(cart_id))

        validations = verified["validations"] if verified else []
        loyalty_hint = self._loyalty_hint(verified["loyalty"]) if verified else None
        verified_total = verified["total_price"] if verified else None
        checkout_url = None
        if verified:
            checkout_url = verified["checkout_web_link"] or verified["checkout_mobile_link"]
        cart_url = checkout_url or f"https://silpo.ua/cart/{cart_id}"
        logger.info(
            "mcp cart written cart_id=%s items=%d validations=%d total=%s",
            cart_id,
            len(items),
            len(validations),
            verified_total,
        )
        return {
            "cart_url": cart_url,
            "checkout_url": checkout_url,
            "verified_total": verified_total,
            "validations": validations,
            "loyalty_hint": loyalty_hint,
            "fulfillment": fulfillment,
        }


mcp_product_service = MCPProductService()
