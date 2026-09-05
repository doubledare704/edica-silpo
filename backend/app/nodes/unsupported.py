import logging
from typing import Any

from ..state import SilpoAgentState

logger = logging.getLogger(__name__)


async def unsupported_request_node(state: SilpoAgentState) -> dict[str, Any]:
    """Returns a clear response without invoking shopping integrations."""
    logger.info("unsupported request ended workflow")
    return {
        "summary_message": "Я можу допомогти лише зі створенням кошика продуктів для party, budget, office або gourmet.",
        "cart_url": None,
        "audio_url": None,
    }
