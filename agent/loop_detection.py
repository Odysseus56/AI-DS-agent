"""
Loop Detection - Safeguards against agent getting stuck.

This module contains:
- detect_loop: Check if the agent is stuck in a repetitive pattern
- get_divergence_message: Message to inject when loop is detected
"""

from .state import AgentState


def detect_loop(state: AgentState) -> bool:
    """
    Check if agent is stuck in a loop.
    
    Detects when the agent is repeatedly calling the same tool
    without making progress (especially with errors).
    
    Args:
        state: The current agent state with tool call history
        
    Returns:
        True if a loop is detected, False otherwise
    """
    if len(state.tool_call_history) < 4:
        return False
    
    # Check last 4 tool calls
    recent = state.tool_call_history[-4:]
    
    # If same tool called 3+ times in a row with errors
    if all(t["name"] == recent[0]["name"] for t in recent):
        error_count = sum(1 for t in recent if t.get("had_error", False))
        if error_count >= 2:
            return True
    
    return False


def get_divergence_message() -> str:
    """
    Message to inject when loop is detected.
    
    This message is added to the conversation to force the agent
    to try a different approach.
    
    Returns:
        The divergence instruction message
    """
    return """LOOP DETECTED: You've tried the same approach multiple times without success.

You MUST try a DIFFERENT approach. Options:
1. Use a completely different statistical method
2. Simplify the analysis (fewer variables, simpler aggregation)
3. Explain why this analysis cannot be performed with available data

Do NOT repeat the same tool call."""
