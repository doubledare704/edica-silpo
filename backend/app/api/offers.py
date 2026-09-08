from typing import Any

from fastapi import APIRouter, Query

from ..services.mcp_service import mcp_product_service

router = APIRouter(prefix="/api/offers", tags=["offers"])


@router.get("")
async def offers_endpoint(
    delivery_address: str | None = Query(default=None, min_length=1),
) -> dict[str, Any]:
    """Returns loyalty balance and currently available Silpo offers."""
    return await mcp_product_service.get_offers_overview(delivery_address)
