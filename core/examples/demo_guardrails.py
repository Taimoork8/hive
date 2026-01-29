"""
Demo: Execution guardrails (runtime limits) in action.

Shows the ExecutionGuard terminating a run when max_runtime_ms is exceeded:
- Subscribes to EXECUTION_STARTED, EXECUTION_TERMINATED, EXECUTION_COMPLETED
- Uses a "slow" LLM (sleeps 3s) so the runtime limit (2s) fires
- Prints events so you can see the guard working

Run from repo root:
    PYTHONPATH=core python core/examples/demo_guardrails.py

Or with venv (PowerShell): activate .venv then run as above.
    $env:PYTHONPATH = "core"
    python core/examples/demo_guardrails.py
"""

import asyncio
import json
import time
from collections.abc import Callable
from pathlib import Path

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
    """LLM that sleeps before returning so execution runs long enough for guard to fire."""

    def complete(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[Tool] | None = None,
        max_tokens: int = 1024,
        response_format: dict | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        # Sleep 3s so runtime limit (2s) is exceeded
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


async def on_event(event):
    """Print events (called by event bus)."""
    if event.type == EventType.EXECUTION_TERMINATED:
        print("\n  🔴 GUARD FIRED: EXECUTION_TERMINATED")
        print(f"     reason: {event.data.get('reason', '?')}")
        print(f"     details: {event.data.get('details', {})}")
    elif event.type == EventType.EXECUTION_STARTED:
        print(f"\n  ▶ EXECUTION_STARTED  execution_id={event.execution_id}")
    elif event.type == EventType.EXECUTION_COMPLETED:
        print(f"  ✓ EXECUTION_COMPLETED execution_id={event.execution_id}")
    else:
        print(f"  • {event.type.value}  execution_id={event.execution_id}")


async def main():
    print("=" * 60)
    print("  Execution Guardrails Demo")
    print("  (Guard will fire after 2s; LLM sleeps 3s)")
    print("=" * 60)

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

    # Guard: terminate if execution runs longer than 2 seconds
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

    # Subscribe so we see EXECUTION_TERMINATED when guard fires
    runtime.subscribe_to_events(
        event_types=[
            EventType.EXECUTION_STARTED,
            EventType.EXECUTION_TERMINATED,
            EventType.EXECUTION_COMPLETED,
        ],
        handler=on_event,
    )

    await runtime.start()

    print("\nTriggering execution (will run until guard fires at ~2s)...")
    result = await runtime.trigger_and_wait("demo", {"x": "test"}, timeout=10)
    print(f"\nResult: {result}")

    await runtime.stop()
    await storage.stop()

    print("\n" + "=" * 60)
    print("  If you saw 'GUARD FIRED: EXECUTION_TERMINATED' above,")
    print("  the execution guardrails are working.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
