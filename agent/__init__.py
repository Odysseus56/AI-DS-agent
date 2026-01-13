"""
Agent Package - ReAct Agent V2 for Data Science

This package provides a modular implementation of the ReAct-style agent
for data analysis tasks.

Modules:
- state: Data classes (AgentState, FinalOutput, ExecutionLog, etc.)
- tools: Tool definitions and implementations
- prompts: System prompt building and example library
- loop_detection: Safeguards against repetitive patterns
- core: Main agent loop functions
- llm_client: Centralized OpenAI client

Public API:
- run_agent: Non-streaming agent execution
- run_agent_streaming: Streaming agent execution
- process_question_v2: Integration function (non-streaming)
- process_question_v2_streaming: Integration function (streaming)
- AgentState, FinalOutput, ExecutionLog, IterationLog, ToolCallLog: Data classes
"""

# State classes - for type hints and external use
from .state import (
    AgentState,
    ToolCallLog,
    IterationLog,
    ExecutionLog,
    FinalOutput
)

# Core functions - main public API
from .core import (
    run_agent,
    run_agent_streaming,
    process_question_v2,
    process_question_v2_streaming
)

# Tools - for advanced use cases
from .tools import TOOLS, execute_tool

# Prompts - for customization
from .prompts import EXAMPLE_LIBRARY, retrieve_examples, build_system_prompt

# Loop detection - for debugging
from .loop_detection import detect_loop, get_divergence_message

# LLM client - for direct access if needed
from .llm_client import get_openai_client


__all__ = [
    # State classes
    "AgentState",
    "ToolCallLog", 
    "IterationLog",
    "ExecutionLog",
    "FinalOutput",
    
    # Core functions
    "run_agent",
    "run_agent_streaming",
    "process_question_v2",
    "process_question_v2_streaming",
    
    # Tools
    "TOOLS",
    "execute_tool",
    
    # Prompts
    "EXAMPLE_LIBRARY",
    "retrieve_examples",
    "build_system_prompt",
    
    # Loop detection
    "detect_loop",
    "get_divergence_message",
    
    # LLM client
    "get_openai_client",
]
