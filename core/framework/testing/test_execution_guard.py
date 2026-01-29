"""
Tests for ExecutionGuard runtime safety limits.
"""

import asyncio
import pytest
from framework.runtime.execution_guard import ExecutionGuard, ExecutionLimitConfig


class TestExecutionGuard:
    """Test execution guard functionality."""
    
    def test_step_limit_exceeded(self):
        """Test that step limit triggers termination."""
        config = ExecutionLimitConfig(max_steps=3)
        guard = ExecutionGuard("test-execution", config)
        
        # Simulate 3 steps
        for _ in range(3):
            guard.increment_step()
            result = guard.check_step_limit()
            assert result is None
        
        # 4th step should trigger limit
        guard.increment_step()
        result = guard.check_step_limit()
        assert result is not None
        assert result.should_terminate is True
        assert result.reason == "STEP_LIMIT_EXCEEDED"
    
    def test_runtime_limit_exceeded(self):
        """Test that runtime limit triggers termination."""
        config = ExecutionLimitConfig(max_runtime_ms=100)  # 100ms
        guard = ExecutionGuard("test-execution", config)
        
        # Should not trigger immediately
        result = guard.check_runtime_limit()
        assert result is None
        
        # Wait for 150ms
        import time
        time.sleep(0.15)
        
        # Should trigger now
        result = guard.check_runtime_limit()
        assert result is not None
        assert result.should_terminate is True
        assert result.reason == "TIME_LIMIT_EXCEEDED"
    
    def test_token_limit_exceeded(self):
        """Test that token limit triggers termination."""
        config = ExecutionLimitConfig(max_tokens=100)
        guard = ExecutionGuard("test-execution", config)
        
        # Add 99 tokens
        guard.add_tokens(99)
        result = guard.check_token_limit()
        assert result is None
        
        # Add 2 more tokens (total 101)
        guard.add_tokens(2)
        result = guard.check_token_limit()
        assert result is not None
        assert result.should_terminate is True
        assert result.reason == "TOKEN_LIMIT_EXCEEDED"
    
    def test_cost_limit_exceeded(self):
        """Test that cost limit triggers termination."""
        config = ExecutionLimitConfig(max_cost_usd=1.00)
        guard = ExecutionGuard("test-execution", config)
        
        # Add $0.99
        guard.add_cost(0.99)
        result = guard.check_cost_limit()
        assert result is None
        
        # Add $0.02 more (total $1.01)
        guard.add_cost(0.02)
        result = guard.check_cost_limit()
        assert result is not None
        assert result.should_terminate is True
        assert result.reason == "COST_LIMIT_EXCEEDED"
    
    def test_all_checks_passed(self):
        """Test that all checks pass when within limits."""
        config = ExecutionLimitConfig(
            max_steps=100,
            max_runtime_ms=10000,
            max_tokens=1000,
            max_cost_usd=10.0
        )
        guard = ExecutionGuard("test-execution", config)
        
        # Simulate usage within limits
        guard.increment_step()
        guard.add_tokens(50)
        guard.add_cost(0.50)
        
        result = guard.check_all_limits()
        assert result.should_terminate is False
        assert result.reason == "WITHIN_LIMITS"
    
    def test_no_limits_configured(self):
        """Test that no limits defaults to allowing execution."""
        config = ExecutionLimitConfig()
        guard = ExecutionGuard("test-execution", config)
        
        # Add significant usage
        for _ in range(1000):
            guard.increment_step()
        guard.add_tokens(1000000)
        guard.add_cost(1000.0)
        
        result = guard.check_all_limits()
        assert result.should_terminate is False
        assert result.reason == "WITHIN_LIMITS"
    
    def test_get_stats(self):
        """Test that statistics are correctly reported."""
        config = ExecutionLimitConfig(max_steps=100, max_runtime_ms=1000)
        guard = ExecutionGuard("test-execution", config)
        
        guard.increment_step()
        guard.add_tokens(25)
        guard.add_cost(0.25)
        
        stats = guard.get_stats()
        assert stats["execution_id"] == "test-execution"
        assert stats["step_count"] == 1
        assert stats["token_count"] == 25
        assert stats["cost_usd"] == 0.25
        assert stats["limits"]["max_steps"] == 100