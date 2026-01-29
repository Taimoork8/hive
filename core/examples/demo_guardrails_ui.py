"""
Demo: Execution guardrails in a simple browser UI (Streamlit).

Shows EXECUTION_STARTED, EXECUTION_TERMINATED, EXECUTION_COMPLETED in the UI
when the runtime limit is exceeded.

Install Streamlit once:
    pip install streamlit

Run from repo root:
    PYTHONPATH=core streamlit run core/examples/demo_guardrails_ui.py

Then open http://localhost:8501 and click "Run guardrails demo".
"""

import asyncio
import json
import time
from collections.abc import Callable
from pathlib import Path

import streamlit as st

from framework.graph import Goal, NodeSpec, SuccessCriterion
from framework.graph.edge import GraphSpec
from framework.llm.provider import LLMProvider, LLMResponse, Tool
from framework.runtime.agent_runtime import (
    AgentRuntimeConfig,
    EntryPointSpec,
    create_agent_runtime,
)
from framework.runtime.event_bus import EventType
from framework.runtime.execution_guard import ExecutionLimitConfig
from framework.storage.concurrent import ConcurrentStorage


class SlowLLMProvider(LLMProvider):
    """LLM that sleeps so execution runs long enough for guard to fire."""

    def complete(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[Tool] | None = None,
        max_tokens: int = 1024,
        response_format: dict | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        time.sleep(3)
        return LLMResponse(content=json.dumps({"result": "ok"}), model="slow")

    def complete_with_tools(
        self,
        messages: list[dict],
        system: str,
        tools: list[Tool],
        tool_executor: Callable,
        max_iterations: int = 10,
    ) -> LLMResponse:
        time.sleep(3)
        return LLMResponse(content=json.dumps({"result": "ok"}), model="slow")


async def run_demo(events_out: list):
    """Run guardrails demo and append events to events_out."""

    async def on_event(event):
        events_out.append(
            {
                "type": event.type.value,
                "execution_id": event.execution_id,
                "stream_id": event.stream_id,
                "data": getattr(event, "data", {}),
            }
        )

    goal = Goal(
        id="demo-goal",
        name="Demo Goal",
        description="Demo",
        success_criteria=[
            SuccessCriterion(
                id="ok",
                description="OK",
                metric="output_contains",
                target="result",
            )
        ],
        constraints=[],
    )

    node = NodeSpec(
        id="slow_node",
        name="Slow",
        description="Slow node",
        node_type="llm_generate",
        input_keys=["x"],
        output_keys=["result"],
        system_prompt='Return JSON: {"result": "ok"}',
    )

    graph = GraphSpec(
        id="demo-graph",
        goal_id=goal.id,
        version="1.0.0",
        entry_node="slow_node",
        entry_points={"start": "slow_node"},
        terminal_nodes=["slow_node"],
        pause_nodes=[],
        nodes=[node],
        edges=[],
        default_model="slow",
        max_tokens=10,
    )

    guard_config = ExecutionLimitConfig(max_runtime_ms=2000)
    config = AgentRuntimeConfig(execution_guard_config=guard_config)

    storage_path = Path("./demo_guardrails_storage")
    storage_path.mkdir(exist_ok=True)
    storage = ConcurrentStorage(storage_path)
    await storage.start()

    runtime = create_agent_runtime(
        graph=graph,
        goal=goal,
        storage_path=storage_path,
        entry_points=[
            EntryPointSpec(
                id="demo",
                name="Demo",
                entry_node="slow_node",
                trigger_type="manual",
                isolation_level="shared",
            )
        ],
        llm=SlowLLMProvider(),
        config=config,
    )

    runtime.subscribe_to_events(
        event_types=[
            EventType.EXECUTION_STARTED,
            EventType.EXECUTION_TERMINATED,
            EventType.EXECUTION_COMPLETED,
        ],
        handler=on_event,
    )

    await runtime.start()
    await runtime.trigger_and_wait("demo", {"x": "test"}, timeout=10)
    await runtime.stop()
    await storage.stop()


st.set_page_config(page_title="Guardrails Demo", page_icon="🛡️")
st.title("🛡️ Execution Guardrails Demo")
st.caption(
    "Runs an agent with a 2s runtime limit. The LLM sleeps 3s, so the guard fires "
    "and you see EXECUTION_TERMINATED."
)

if st.button("Run guardrails demo"):
    events: list = []
    with st.spinner("Running... (guard will fire after ~2s)"):
        asyncio.run(run_demo(events))

    st.success("Done.")
    st.subheader("Events")
    for i, e in enumerate(events):
        if e["type"] == "execution_terminated":
            st.error(f"🔴 **GUARD FIRED:** {e['type']}")
            st.json(e["data"])
        else:
            st.write(f"**{e['type']}** — `{e['execution_id']}`")
    if not events:
        st.info("No events captured (event bus may not have been used).")
