from typing import Annotated, Any

from fastapi import APIRouter, Query

from ..services.mcp_service import mcp_product_service

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("")
async def profile_endpoint(
    delivery_address: Annotated[str | None, Query(min_length=1)] = None,
) -> dict[str, Any]:
    """Returns profile, loyalty, saved addresses, delivery modes, and branches."""
    return await mcp_product_service.get_profile_overview(delivery_address)
