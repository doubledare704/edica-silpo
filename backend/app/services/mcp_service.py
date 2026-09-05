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

    async def create_cart(self, products: list[dict[str, Any]]) -> str:
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
            cart = await client.get_cart()
            cart_id = self._product_value(cart, "id", "cartId", "cart_id")
            if not cart_id:
                raise ValueError("Silpo cart response is missing an id")

            existing_items = self._product_value(cart, "items", "products", default=[])
            if existing_items:
                await client.clear_cart(cart_id)
            result = await client.add_or_update_cart_products(cart_id, items=items)

        share_url = self._product_value(result, "share_url", "shareUrl", "url")
        return share_url or f"https://silpo.ua/cart/{cart_id}"


mcp_product_service = MCPProductService()
