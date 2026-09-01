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
                    matched_prod: dict[str, Any] | None = None

                    try:
                        result = await client.get_products(query)
                        items = getattr(result, "items", [])
                        if items:
                            first = items[0]
                            matched_prod = {
                                "id": getattr(first, "id", f"sku-{len(products) + 1}"),
                                "title": getattr(first, "title", query),
                                "price": float(getattr(first, "price", 100.0)),
                                "is_private_label": bool(getattr(first, "is_private_label", False)),
                                "quantity": quantity,
                            }
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


mcp_product_service = MCPProductService()
