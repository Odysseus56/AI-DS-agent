"""
Agent State Management - Data classes for the ReAct agent.

This module contains all the data structures used by the agent:
- AgentState: Conversation-based state for the ReAct agent
- ToolCallLog: Log entry for a single tool call
- IterationLog: Log entry for a single agent iteration
- ExecutionLog: Complete execution log for an agent run
- FinalOutput: Structured final output from the agent
"""

import json
from typing import Any, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AgentState:
    """Simple conversation-based state for the ReAct agent."""
    
    # Current task
    question: str
    datasets: dict  # {name: {df, data_summary, ...}}
    
    # Conversation history (for LLM context)
    messages: list = field(default_factory=list)
    
    # Retrieved examples for this question
    retrieved_examples: list = field(default_factory=list)
    
    # Execution state
    current_code: Optional[str] = None
    current_results: Optional[dict] = None
    validation: Optional[dict] = None
    data_profile: Optional[dict] = None
    
    # Loop control
    iterations: int = 0
    max_iterations: int = 8
    
    # Tracking for safeguards
    failed_attempts: list = field(default_factory=list)
    tool_call_history: list = field(default_factory=list)


@dataclass
class ToolCallLog:
    """Log entry for a single tool call."""
    tool_name: str
    arguments: dict
    result: dict
    duration_ms: float
    success: bool
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    model: Optional[str] = None  # Which model was used for this tool call


@dataclass 
class IterationLog:
    """Log entry for a single agent iteration."""
    iteration_num: int
    llm_reasoning: Optional[str]  # What the LLM said before tool calls
    tool_calls: list = field(default_factory=list)  # List of ToolCallLog
    raw_response: Optional[str] = None  # Full LLM response content
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    model: Optional[str] = None  # Which model was used for this iteration
    prompt_tokens: int = 0  # Tokens used in prompt
    completion_tokens: int = 0  # Tokens used in completion
    total_tokens: int = 0  # Total tokens used


@dataclass
class ExecutionLog:
    """Complete execution log for a ReAct agent run."""
    question: str
    start_time: str
    end_time: Optional[str] = None
    
    # Iteration details
    iterations: list = field(default_factory=list)  # List of IterationLog
    
    # Context used
    retrieved_examples: list = field(default_factory=list)
    system_prompt: Optional[str] = None
    
    # Final outcome
    final_output_type: Optional[str] = None
    final_confidence: Optional[float] = None
    total_tool_calls: int = 0
    
    # Token usage tracking
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    
    # Errors and issues
    loop_detected: bool = False
    forced_divergence: bool = False
    max_iterations_reached: bool = False
    errors: list = field(default_factory=list)
    
    def add_iteration(self, iteration: IterationLog):
        self.iterations.append(iteration)
        self.total_tool_calls += len(iteration.tool_calls)
        # Accumulate token usage
        self.total_prompt_tokens += iteration.prompt_tokens
        self.total_completion_tokens += iteration.completion_tokens
        self.total_tokens += iteration.total_tokens
    
    def to_markdown(self) -> str:
        """Convert execution log to markdown format for file logging."""
        md = []
        md.append(f"## ReAct Agent Execution")
        md.append(f"**Question:** {self.question}")
        md.append(f"**Started:** {self.start_time}")
        if self.end_time:
            md.append(f"**Ended:** {self.end_time}")
        md.append("")
        
        # Retrieved examples
        if self.retrieved_examples:
            md.append("### Retrieved Examples")
            for ex in self.retrieved_examples:
                md.append(f"- {ex.get('question', 'N/A')} → {ex.get('approach', 'N/A')}")
            md.append("")
        
        # Iterations
        for iteration in self.iterations:
            md.append(f"### Iteration {iteration.iteration_num}")
            md.append(f"*{iteration.timestamp}*")
            
            # Show model and token usage for this iteration
            if iteration.model:
                md.append(f"**Model:** `{iteration.model}`")
            if iteration.total_tokens > 0:
                md.append(f"**Tokens:** {iteration.prompt_tokens} prompt + {iteration.completion_tokens} completion = {iteration.total_tokens} total")
            md.append("")
            
            # Show LLM reasoning at EVERY iteration (not just final)
            if iteration.llm_reasoning:
                md.append(f"**LLM Reasoning:**")
                md.append(f"> {iteration.llm_reasoning}")
                md.append("")
            
            for tc in iteration.tool_calls:
                status = "✓" if tc.success else "✗"
                model_info = f" [{tc.model}]" if tc.model else ""
                md.append(f"**Tool Call:** `{tc.tool_name}` {status} ({tc.duration_ms:.0f}ms){model_info}")
                md.append("")
                
                # Format arguments as proper JSON block
                md.append("**Arguments:**")
                md.append("```json")
                md.append(json.dumps(tc.arguments, indent=2, default=str))
                md.append("```")
                md.append("")
                
                # Format result as proper JSON block
                md.append("**Result:**")
                md.append("```json")
                md.append(json.dumps(tc.result, indent=2, default=str))
                md.append("```")
                
                if tc.error:
                    md.append(f"**Error:** {tc.error}")
                md.append("")
        
        # Final summary
        md.append("### Execution Summary")
        md.append(f"- **Output Type:** {self.final_output_type or 'N/A'}")
        md.append(f"- **Confidence:** {self.final_confidence or 'N/A'}")
        md.append(f"- **Total Iterations:** {len(self.iterations)}")
        md.append(f"- **Total Tool Calls:** {self.total_tool_calls}")
        
        # Token usage summary
        if self.total_tokens > 0:
            md.append(f"- **Total Tokens:** {self.total_tokens:,} ({self.total_prompt_tokens:,} prompt + {self.total_completion_tokens:,} completion)")
        
        if self.loop_detected:
            md.append(f"- **⚠️ Loop Detected:** Yes")
        if self.forced_divergence:
            md.append(f"- **⚠️ Forced Divergence:** Yes")
        if self.max_iterations_reached:
            md.append(f"- **⚠️ Max Iterations Reached:** Yes")
        
        if self.errors:
            md.append("")
            md.append("### Errors")
            for err in self.errors:
                md.append(f"- {err}")
        
        md.append("")
        md.append("---")
        md.append("")
        
        return "\n".join(md)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "question": self.question,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "iterations": [
                {
                    "iteration_num": it.iteration_num,
                    "llm_reasoning": it.llm_reasoning,
                    "model": it.model,
                    "prompt_tokens": it.prompt_tokens,
                    "completion_tokens": it.completion_tokens,
                    "total_tokens": it.total_tokens,
                    "tool_calls": [
                        {
                            "tool_name": tc.tool_name,
                            "arguments": tc.arguments,
                            "result": tc.result,
                            "duration_ms": tc.duration_ms,
                            "success": tc.success,
                            "error": tc.error,
                            "model": tc.model
                        }
                        for tc in it.tool_calls
                    ]
                }
                for it in self.iterations
            ],
            "retrieved_examples": self.retrieved_examples,
            "final_output_type": self.final_output_type,
            "final_confidence": self.final_confidence,
            "total_tool_calls": self.total_tool_calls,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "loop_detected": self.loop_detected,
            "forced_divergence": self.forced_divergence,
            "max_iterations_reached": self.max_iterations_reached,
            "errors": self.errors
        }


@dataclass
class FinalOutput:
    """Structured final output from the agent."""
    
    # Required
    answer: str
    confidence: float
    output_type: Literal["analysis", "visualization", "explanation", "error"]
    
    # Optional
    result: Any = None
    figures: list = field(default_factory=list)
    code: Optional[str] = None
    
    # Always included
    caveats: list = field(default_factory=list)
    reasoning_trace: list = field(default_factory=list)
    
    # Detailed execution log for debugging
    execution_log: Optional[ExecutionLog] = None
