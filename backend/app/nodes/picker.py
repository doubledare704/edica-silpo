import logging
from typing import Any

from ..config import settings
from ..domain.picker import GeminiPickerAdvisor, PickerService
from ..services.mcp_service import mcp_product_service
from ..state import SilpoAgentState

logger = logging.getLogger(__name__)


def _default_advisor() -> GeminiPickerAdvisor | None:
    if settings.GEMINI_MOCK_MODE or not settings.GEMINI_API_KEY:
        return None
    return GeminiPickerAdvisor()


async def picker_node(state: SilpoAgentState) -> dict[str, Any]:
    """Iteratively picks priced products via Silpo tools until budget/requirements resolve."""
    service = PickerService(product_service=mcp_product_service, advisor=_default_advisor())
    result = await service.run(state)
    logger.info(
        "picker node done accepted=%d met=%s remaining=%s",
        result["picker_accepted"],
        result["is_requirements_met"],
        result["remaining_budget"],
    )
    return result
