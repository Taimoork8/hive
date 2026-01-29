"""
Execution Guard - Runtime safety limits for preventing runaway agent execution.

This module provides centralized execution guardrails to prevent:
- Unbounded execution loops (replanning, retries)
- Excessive runtime duration
- Runaway costs and resource consumption

The guard enforces hard limits at the execution level and provides
deterministic termination with structured reasons for observability.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ExecutionLimitConfig:
    """Configuration for execution safety limits."""
    max_steps: Optional[int] = None  # Maximum execution steps, None = no limit
    max_runtime_ms: Optional[int] = None  # Maximum wall-clock time, None = no limit
    max_tokens: Optional[int] = None  # Maximum token usage, None = no limit
    max_cost_usd: Optional[float] = None  # Maximum cost in USD, None = no limit


@dataclass
class ExecutionGuardResult:
    """Result of execution guard check."""
    should_terminate: bool
    reason: str
    details: dict[str, object]


class ExecutionGuard:
    """
    Centralized execution guard for enforcing runtime safety limits.
    
    The guard is evaluated on each execution iteration and provides
    deterministic termination conditions to prevent runaway behavior.
    """
    
    def __init__(self, execution_id: str, config: ExecutionLimitConfig):
        """
        Initialize the execution guard.
        
        Args:
            execution_id: Unique identifier for this execution
            config: Execution limit configuration
        """
        self.execution_id = execution_id
        self.config = config
        self.start_time = time.time()
        self.step_count = 0
        self.token_count = 0
        self.cost_tracker = 0.0
        
        logger.debug(f"ExecutionGuard initialized for {execution_id} with limits: {config}")
    
    def check_step_limit(self) -> Optional[ExecutionGuardResult]:
        """Check if step limit has been exceeded (terminate after exceeding max_steps)."""
        if self.config.max_steps is not None and self.step_count > self.config.max_steps:
            return ExecutionGuardResult(
                should_terminate=True,
                reason="STEP_LIMIT_EXCEEDED",
                details={
                    "step_count": self.step_count,
                    "max_steps": self.config.max_steps,
                }
            )
        return None
    
    def check_runtime_limit(self) -> Optional[ExecutionGuardResult]:
        """Check if runtime limit has been exceeded."""
        if self.config.max_runtime_ms is not None:
            current_runtime_ms = (time.time() - self.start_time) * 1000
            if current_runtime_ms >= self.config.max_runtime_ms:
                return ExecutionGuardResult(
                    should_terminate=True,
                    reason="TIME_LIMIT_EXCEEDED",
                    details={
                        "current_runtime_ms": current_runtime_ms,
                        "max_runtime_ms": self.config.max_runtime_ms,
                    }
                )
        return None
    
    def check_token_limit(self) -> Optional[ExecutionGuardResult]:
        """Check if token limit has been exceeded."""
        if self.config.max_tokens is not None and self.token_count >= self.config.max_tokens:
            return ExecutionGuardResult(
                should_terminate=True,
                reason="TOKEN_LIMIT_EXCEEDED",
                details={
                    "token_count": self.token_count,
                    "max_tokens": self.config.max_tokens,
                }
            )
        return None
    
    def check_cost_limit(self) -> Optional[ExecutionGuardResult]:
        """Check if cost limit has been exceeded."""
        if self.config.max_cost_usd is not None and self.cost_tracker >= self.config.max_cost_usd:
            return ExecutionGuardResult(
                should_terminate=True,
                reason="COST_LIMIT_EXCEEDED",
                details={
                    "current_cost_usd": self.cost_tracker,
                    "max_cost_usd": self.config.max_cost_usd,
                }
            )
        return None
    
    def check_all_limits(self) -> ExecutionGuardResult:
        """
        Check all configured limits and return termination result.
        
        Returns:
            ExecutionGuardResult indicating if execution should terminate
        """
        # Check each limit in order of criticality
        checks = [
            self.check_step_limit(),
            self.check_runtime_limit(),
            self.check_token_limit(),
            self.check_cost_limit(),
        ]
        
        for check_result in checks:
            if check_result is not None:
                logger.warning(
                    f"ExecutionGuard: Terminating execution {self.execution_id} "
                    f"due to {check_result.reason}: {check_result.details}"
                )
                return check_result
        
        # All checks passed
        return ExecutionGuardResult(
            should_terminate=False,
            reason="WITHIN_LIMITS",
            details={
                "step_count": self.step_count,
                "runtime_ms": (time.time() - self.start_time) * 1000,
                "token_count": self.token_count,
                "cost_usd": self.cost_tracker,
            }
        )
    
    def increment_step(self) -> None:
        """Increment step counter."""
        self.step_count += 1
    
    def add_tokens(self, token_count: int) -> None:
        """Add tokens to the counter."""
        if token_count > 0:
            self.token_count += token_count
    
    def add_cost(self, cost_usd: float) -> None:
        """Add cost to the tracker."""
        if cost_usd > 0:
            self.cost_tracker += cost_usd
    
    def get_stats(self) -> dict[str, object]:
        """Get current execution statistics."""
        return {
            "execution_id": self.execution_id,
            "step_count": self.step_count,
            "runtime_ms": (time.time() - self.start_time) * 1000,
            "token_count": self.token_count,
            "cost_usd": self.cost_tracker,
            "limits": {
                "max_steps": self.config.max_steps,
                "max_runtime_ms": self.config.max_runtime_ms,
                "max_tokens": self.config.max_tokens,
                "max_cost_usd": self.config.max_cost_usd,
            }
        }