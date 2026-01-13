"""
ReAct Agent V2 - Tool-Based Data Scientist Agent

This module is a backward-compatibility layer that re-exports from the agent package.
The actual implementation has been modularized into:

- agent/state.py: Data classes (AgentState, FinalOutput, ExecutionLog, etc.)
- agent/tools.py: Tool definitions and implementations
- agent/prompts.py: System prompt building and example library
- agent/loop_detection.py: Safeguards against repetitive patterns
- agent/core.py: Main agent loop functions
- agent/llm_client.py: Centralized OpenAI client

For new code, prefer importing directly from the agent package:
    from agent import run_agent, AgentState, FinalOutput

This file maintains backward compatibility for existing imports:
    from react_agent import run_agent, AgentState, FinalOutput
"""

# Re-export everything from the agent package for backward compatibility
from agent import (
    # State classes
    AgentState,
    ToolCallLog,
    IterationLog,
    ExecutionLog,
    FinalOutput,
    
    # Core functions
    run_agent,
    run_agent_streaming,
    process_question_v2,
    process_question_v2_streaming,
    
    # Tools
    TOOLS,
    execute_tool,
    
    # Prompts
    EXAMPLE_LIBRARY,
    retrieve_examples,
    build_system_prompt,
    
    # Loop detection
    detect_loop,
    get_divergence_message,
    
    # LLM client
    get_openai_client,
)


# Define __all__ for explicit public API
__all__ = [
    "AgentState",
    "ToolCallLog",
    "IterationLog",
    "ExecutionLog",
    "FinalOutput",
    "run_agent",
    "run_agent_streaming",
    "process_question_v2",
    "process_question_v2_streaming",
    "TOOLS",
    "execute_tool",
    "EXAMPLE_LIBRARY",
    "retrieve_examples",
    "build_system_prompt",
    "detect_loop",
    "get_divergence_message",
    "get_openai_client",
]
