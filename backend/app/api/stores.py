from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..schemas import NearestStoresResponse, SavedAddressItem
from ..services.mcp_service import mcp_product_service

router = APIRouter(prefix="/api/stores", tags=["stores"])


@router.get("/saved-addresses", response_model=list[SavedAddressItem])
async def saved_addresses_endpoint() -> list[dict[str, Any]]:
    """Returns the user's saved Silpo delivery addresses for the store picker."""
    return await mcp_product_service.list_saved_addresses()


@router.get("/nearest", response_model=NearestStoresResponse)
async def nearest_stores_endpoint(
    address: str = Query(min_length=1),
    limit: int = Query(default=10, ge=1, le=10),
) -> dict[str, object]:
    """Returns the nearest Silpo branches to a user-supplied address (max 10)."""
    text = address.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Address must not be blank")
    try:
        return await mcp_product_service.find_nearest_branches(text, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
