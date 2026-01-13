"""
Agent Prompts - System prompt building and example library.

This module contains:
- EXAMPLE_LIBRARY: Example questions and approaches for retrieval
- retrieve_examples: Function to find relevant examples
- build_system_prompt: Function to construct the agent's system prompt
"""

from .state import AgentState


# =============================================================================
# EXAMPLE LIBRARY (Placeholder - will be expanded)
# =============================================================================

EXAMPLE_LIBRARY = [
    {
        "id": "comparison_proportions_01",
        "question": "Is there a significant difference in conversion rates between A and B?",
        "approach": "Use chi-square test to compare proportions between two groups",
        "output_var": "result",
        "tags": ["comparison", "proportions", "chi-square"]
    },
    {
        "id": "comparison_continuous_01",
        "question": "Do customers in segment A have higher average spend than segment B?",
        "approach": "Use independent t-test to compare means between two groups",
        "output_var": "result",
        "tags": ["comparison", "continuous", "t-test"]
    },
    {
        "id": "visualization_distribution_01",
        "question": "Show me the distribution of customer ages",
        "approach": "Create a histogram using Plotly",
        "output_var": "fig",
        "tags": ["visualization", "distribution", "histogram"]
    },
    {
        "id": "correlation_01",
        "question": "What's the correlation between price and quantity?",
        "approach": "Calculate Pearson correlation coefficient",
        "output_var": "result",
        "tags": ["relationship", "correlation"]
    },
    {
        "id": "aggregation_01",
        "question": "What's the average revenue by region?",
        "approach": "Group by region and calculate mean revenue",
        "output_var": "result",
        "tags": ["description", "aggregation", "groupby"]
    }
]


def retrieve_examples(question: str, top_k: int = 2) -> list:
    """
    Retrieve relevant examples based on question similarity.
    
    For MVP, uses simple keyword matching. Will be upgraded to semantic search.
    
    Args:
        question: The user's question
        top_k: Number of examples to return
        
    Returns:
        List of relevant example dictionaries
    """
    question_lower = question.lower()
    
    scored_examples = []
    for example in EXAMPLE_LIBRARY:
        score = 0
        
        # Check tags
        for tag in example.get("tags", []):
            if tag in question_lower:
                score += 2
        
        # Check question similarity (simple keyword overlap)
        example_words = set(example["question"].lower().split())
        question_words = set(question_lower.split())
        overlap = len(example_words & question_words)
        score += overlap
        
        # Boost visualization examples if user asks to "show" or "plot"
        if any(word in question_lower for word in ["show", "plot", "visualize", "chart", "graph"]):
            if example.get("output_var") == "fig":
                score += 3
        
        scored_examples.append((score, example))
    
    # Sort by score and return top_k
    scored_examples.sort(key=lambda x: x[0], reverse=True)
    return [ex for score, ex in scored_examples[:top_k] if score > 0]


def build_system_prompt(state: AgentState) -> str:
    """
    Build the system prompt with context.
    
    Args:
        state: The current agent state containing datasets and retrieved examples
        
    Returns:
        The complete system prompt string
    """
    # Get data summary
    data_summary = ""
    for name, dataset_info in state.datasets.items():
        data_summary += f"\nDataset '{name}':\n{dataset_info.get('data_summary', 'No summary available')[:1000]}\n"
    
    # Get examples (if any)
    examples_text = ""
    if state.retrieved_examples:
        examples_text = "\n\nSIMILAR EXAMPLES:\n"
        for ex in state.retrieved_examples[:2]:
            examples_text += f"- Question: {ex.get('question', '')}\n"
            examples_text += f"  Approach: {ex.get('approach', '')}\n"
    
    return f"""You are an expert data scientist assistant. Help the user analyze their data.

AVAILABLE DATA:
{data_summary}
{examples_text}

HOW TO WORK:
1. First, use profile_data to understand what columns are available
2. Then, use write_code to generate analysis code
3. Use execute_code to run the code
4. Use validate_results to check the results make sense
5. Finally, use explain_findings to prepare your response

IMPORTANT:
- Always profile data before writing code
- Always validate results before explaining
- If code fails, analyze the error and try a different approach
- Define 'result' for numeric/table output, 'fig' for visualizations
- Only use 'fig' if user explicitly asks to "show", "plot", or "visualize"

When you have validated results and are ready to respond, provide your final answer directly without calling more tools."""
