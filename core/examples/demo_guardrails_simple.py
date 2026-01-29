"""
Demo: ExecutionGuard in isolation (no runtime).

Shows the guard firing when step / time / token / cost limits are exceeded.
Run from repo root:

    PYTHONPATH=core python core/examples/demo_guardrails_simple.py
"""

import time

from framework.runtime.execution_guard import (
    ExecutionGuard,
    ExecutionLimitConfig,
)


def main():
    print("=" * 60)
    print("  ExecutionGuard demo (limits in isolation)")
    print("=" * 60)

    # 1. Step limit
    print("\n1. Step limit (max_steps=3):")
    config = ExecutionLimitConfig(max_steps=3)
    guard = ExecutionGuard("demo-1", config)
    for i in range(5):
        guard.increment_step()
        result = guard.check_all_limits()
        if result.should_terminate:
            print(f"   After step {i + 1}: GUARD FIRED — {result.reason} {result.details}")
            break
        print(f"   Step {i + 1}: within limits")

    # 2. Runtime limit
    print("\n2. Runtime limit (max_runtime_ms=150):")
    config2 = ExecutionLimitConfig(max_runtime_ms=150)
    guard2 = ExecutionGuard("demo-2", config2)
    print("   Waiting 200ms...")
    time.sleep(0.2)
    result2 = guard2.check_all_limits()
    if result2.should_terminate:
        print(f"   GUARD FIRED — {result2.reason} {result2.details}")
    else:
        print("   (still within limits)")

    # 3. Token limit
    print("\n3. Token limit (max_tokens=10):")
    config3 = ExecutionLimitConfig(max_tokens=10)
    guard3 = ExecutionGuard("demo-3", config3)
    guard3.add_tokens(12)
    result3 = guard3.check_all_limits()
    if result3.should_terminate:
        print(f"   GUARD FIRED — {result3.reason} {result3.details}")

    # 4. Cost limit
    print("\n4. Cost limit (max_cost_usd=1.0):")
    config4 = ExecutionLimitConfig(max_cost_usd=1.0)
    guard4 = ExecutionGuard("demo-4", config4)
    guard4.add_cost(1.5)
    result4 = guard4.check_all_limits()
    if result4.should_terminate:
        print(f"   GUARD FIRED — {result4.reason} {result4.details}")

    print("\n" + "=" * 60)
    print("  Guard logic works. In the full runtime, the guard runs")
    print("  in a background task and publishes EXECUTION_TERMINATED.")
    print("=" * 60)


if __name__ == "__main__":
    main()
