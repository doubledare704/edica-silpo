"""Hybrid Silpo graph: STT -> shopper_agent (create_agent) -> TTS.

Legacy NodeName values are preserved for the SSE contract; INNER_TO_LEGACY maps
inner ReAct activity (tools/model) back to the legacy step names.
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .enums import NodeName
from .nodes import stt_node, tts_node
from .shopper_node import shopper_agent_node
from .state import SilpoAgentState

INNER_TO_LEGACY: dict[str, NodeName] = {
    "agent": NodeName.PARSE_INTENT,
    "model": NodeName.PARSE_INTENT,
    "parse_intent": NodeName.PARSE_INTENT,
    "plan_items": NodeName.PLAN_DOMAIN_LOGIC,
    "fetch_products": NodeName.MCP_FETCH,
    "check_budget": NodeName.CHECK_CONSTRAINTS,
    "create_cart": NodeName.CREATE_CART,
}

LEGACY_SUBSTEP_ORDER: list[NodeName] = [
    NodeName.PARSE_INTENT,
    NodeName.PLAN_DOMAIN_LOGIC,
    NodeName.MCP_FETCH,
    NodeName.CHECK_CONSTRAINTS,
    NodeName.CREATE_CART,
]


def create_silpo_agent_graph(checkpointer: MemorySaver | None = None) -> CompiledStateGraph:
    """Assembles and compiles the hybrid Silpo graph with checkpointer."""
    workflow = StateGraph(SilpoAgentState)  # pyrefly: ignore[bad-specialization]

    workflow.add_node(NodeName.STT.value, stt_node)
    workflow.add_node(NodeName.SHOPPER_AGENT, shopper_agent_node)
    workflow.add_node(NodeName.TTS.value, tts_node)

    workflow.add_edge(START, NodeName.STT.value)
    workflow.add_edge(NodeName.STT.value, NodeName.SHOPPER_AGENT)
    workflow.add_edge(NodeName.SHOPPER_AGENT, NodeName.TTS.value)
    workflow.add_edge(NodeName.TTS.value, END)

    saver = checkpointer if checkpointer is not None else MemorySaver()
    return workflow.compile(checkpointer=saver)
