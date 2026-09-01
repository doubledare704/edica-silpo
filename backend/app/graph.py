from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .enums import NodeName
from .nodes import (
    check_constraints_node,
    create_cart_node,
    mcp_fetch_node,
    parse_intent_node,
    plan_domain_logic_node,
    stt_node,
    tts_node,
)
from .state import AgentState


def _route_constraints(state: AgentState) -> str:
    """Routes back to plan_domain_logic if budget is exceeded and attempts < max_attempts."""
    attempts = state.get("attempts", 0)
    max_attempts = state.get("max_attempts", 3)
    is_exceeded = state.get("is_budget_exceeded", False)

    if is_exceeded and attempts < max_attempts:
        return NodeName.PLAN_DOMAIN_LOGIC
    return NodeName.CREATE_CART


def create_silpo_agent_graph(checkpointer: MemorySaver | None = None) -> Any:
    """Assembles and compiles the Silpo Smart Shopper LangGraph graph with checkpointer."""
    workflow = StateGraph(AgentState)  # type: ignore[type-var]

    # Add specification nodes
    workflow.add_node(NodeName.STT, stt_node)
    workflow.add_node(NodeName.PARSE_INTENT, parse_intent_node)
    workflow.add_node(NodeName.PLAN_DOMAIN_LOGIC, plan_domain_logic_node)
    workflow.add_node(NodeName.MCP_FETCH, mcp_fetch_node)
    workflow.add_node(NodeName.CHECK_CONSTRAINTS, check_constraints_node)
    workflow.add_node(NodeName.CREATE_CART, create_cart_node)
    workflow.add_node(NodeName.TTS, tts_node)

    # Add edges
    workflow.add_edge(START, NodeName.STT)
    workflow.add_edge(NodeName.STT, NodeName.PARSE_INTENT)
    workflow.add_edge(NodeName.PARSE_INTENT, NodeName.PLAN_DOMAIN_LOGIC)
    workflow.add_edge(NodeName.PLAN_DOMAIN_LOGIC, NodeName.MCP_FETCH)
    workflow.add_edge(NodeName.MCP_FETCH, NodeName.CHECK_CONSTRAINTS)

    workflow.add_conditional_edges(
        NodeName.CHECK_CONSTRAINTS,
        _route_constraints,
        {
            NodeName.PLAN_DOMAIN_LOGIC: NodeName.PLAN_DOMAIN_LOGIC,
            NodeName.CREATE_CART: NodeName.CREATE_CART,
        },
    )

    workflow.add_edge(NodeName.CREATE_CART, NodeName.TTS)
    workflow.add_edge(NodeName.TTS, END)

    saver = checkpointer if checkpointer is not None else MemorySaver()
    return workflow.compile(checkpointer=saver)
