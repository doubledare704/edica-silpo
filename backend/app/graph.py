"""Explicit async Silpo workflow with a bounded budget retry loop."""

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

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
from .state import SilpoAgentState


def route_constraints(state: SilpoAgentState) -> Literal["plan_domain_logic", "create_cart"]:
    """Retry planning only while the budget is exceeded and attempts remain."""
    attempts = int(state.get("attempts", 0) or 0)
    max_attempts = int(state.get("max_attempts", 3) or 3)
    if bool(state.get("is_budget_exceeded", False)) and attempts < max_attempts:
        return NodeName.PLAN_DOMAIN_LOGIC.value
    return NodeName.CREATE_CART.value


def create_silpo_agent_graph(checkpointer: MemorySaver | None = None) -> CompiledStateGraph:
    """Assemble and compile the explicit async workflow with a checkpointer."""
    workflow = StateGraph(SilpoAgentState)  # pyrefly: ignore[bad-specialization]

    workflow.add_node(NodeName.STT.value, stt_node)
    workflow.add_node(NodeName.PARSE_INTENT.value, parse_intent_node)
    workflow.add_node(NodeName.PLAN_DOMAIN_LOGIC.value, plan_domain_logic_node)
    workflow.add_node(NodeName.MCP_FETCH.value, mcp_fetch_node)
    workflow.add_node(NodeName.CHECK_CONSTRAINTS.value, check_constraints_node)
    workflow.add_node(NodeName.CREATE_CART.value, create_cart_node)
    workflow.add_node(NodeName.TTS.value, tts_node)

    workflow.add_edge(START, NodeName.STT.value)
    workflow.add_edge(NodeName.STT.value, NodeName.PARSE_INTENT.value)
    workflow.add_edge(NodeName.PARSE_INTENT.value, NodeName.PLAN_DOMAIN_LOGIC.value)
    workflow.add_edge(NodeName.PLAN_DOMAIN_LOGIC.value, NodeName.MCP_FETCH.value)
    workflow.add_edge(NodeName.MCP_FETCH.value, NodeName.CHECK_CONSTRAINTS.value)
    workflow.add_conditional_edges(
        NodeName.CHECK_CONSTRAINTS.value,
        route_constraints,
        {
            NodeName.PLAN_DOMAIN_LOGIC.value: NodeName.PLAN_DOMAIN_LOGIC.value,
            NodeName.CREATE_CART.value: NodeName.CREATE_CART.value,
        },
    )
    workflow.add_edge(NodeName.CREATE_CART.value, NodeName.TTS.value)
    workflow.add_edge(NodeName.TTS.value, END)

    saver = checkpointer if checkpointer is not None else MemorySaver()
    return workflow.compile(checkpointer=saver)
