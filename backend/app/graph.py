"""Explicit async Silpo workflow with a bounded iterative picker loop."""

from typing import Any, Literal, cast

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .enums import IntentEnum, NodeName
from .nodes import (
    check_constraints_node,
    create_cart_node,
    parse_intent_node,
    picker_node,
    plan_domain_logic_node,
    stt_node,
    tts_node,
    unsupported_request_node,
)
from .state import SilpoAgentState


def route_constraints(state: SilpoAgentState) -> Literal["picker", "create_cart"]:
    """Re-pick while over budget or requirements unmet (with progress guard); else checkout."""
    attempts = int(state.get("attempts", 0) or 0)
    max_attempts = int(state.get("max_attempts", 3) or 3)
    if attempts >= max_attempts:
        return NodeName.CREATE_CART.value
    if bool(state.get("is_budget_exceeded", False)):
        return NodeName.PICKER.value
    if not bool(state.get("is_requirements_met", True)):
        if int(state.get("picker_accepted", 1) or 0) == 0 and attempts > 0:
            return NodeName.CREATE_CART.value
        return NodeName.PICKER.value
    return NodeName.CREATE_CART.value


def route_parsed_intent(state: SilpoAgentState) -> Literal["unsupported", "plan_domain_logic"]:
    """Skip all shopping work for intents outside the supported domains."""
    if state.get("intent") == IntentEnum.UNSUPPORTED:
        return NodeName.UNSUPPORTED.value
    return NodeName.PLAN_DOMAIN_LOGIC.value


def create_silpo_agent_graph(checkpointer: MemorySaver | None = None) -> CompiledStateGraph:
    """Assemble and compile the explicit async workflow with a checkpointer."""
    workflow = StateGraph(cast(type[Any], SilpoAgentState))

    workflow.add_node(NodeName.STT, stt_node)
    workflow.add_node(NodeName.PARSE_INTENT, parse_intent_node)
    workflow.add_node(NodeName.UNSUPPORTED, unsupported_request_node)
    workflow.add_node(NodeName.PLAN_DOMAIN_LOGIC, plan_domain_logic_node)
    workflow.add_node(NodeName.PICKER, picker_node)
    workflow.add_node(NodeName.CHECK_CONSTRAINTS, check_constraints_node)
    workflow.add_node(NodeName.CREATE_CART, create_cart_node)
    workflow.add_node(NodeName.TTS, tts_node)

    workflow.add_edge(START, NodeName.STT)
    workflow.add_edge(NodeName.STT, NodeName.PARSE_INTENT)
    workflow.add_conditional_edges(
        NodeName.PARSE_INTENT,
        route_parsed_intent,
        {
            NodeName.UNSUPPORTED: NodeName.UNSUPPORTED,
            NodeName.PLAN_DOMAIN_LOGIC: NodeName.PLAN_DOMAIN_LOGIC,
        },
    )
    workflow.add_edge(NodeName.PLAN_DOMAIN_LOGIC, NodeName.PICKER)
    workflow.add_edge(NodeName.PICKER, NodeName.CHECK_CONSTRAINTS)
    workflow.add_conditional_edges(
        NodeName.CHECK_CONSTRAINTS,
        route_constraints,
        {
            NodeName.PICKER: NodeName.PICKER,
            NodeName.CREATE_CART: NodeName.CREATE_CART,
        },
    )
    workflow.add_edge(NodeName.CREATE_CART, NodeName.TTS)
    workflow.add_edge(NodeName.TTS, END)
    workflow.add_edge(NodeName.UNSUPPORTED, END)

    saver = checkpointer if checkpointer is not None else MemorySaver()
    return workflow.compile(checkpointer=saver)
