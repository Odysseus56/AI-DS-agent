"""
Reusable node display functions for consistent UI rendering across streaming and chat history.

This module provides display functions for each node in the MVP LangGraph architecture,
ensuring consistent rendering in both real-time streaming and chat history replay.
"""
from typing import Dict, List, Optional, Any
import streamlit as st


def display_node_0_understanding(data: Optional[Dict[str, Any]], expanded: bool = False) -> None:
    """Display Node 0: Question Understanding"""
    if data:
        with st.expander("🧠 Step 0: Question Understanding", expanded=expanded):
            st.write(f"**Needs Data Work:** {data.get('needs_data_work', True)}")
            st.write(f"**Reasoning:** {data.get('question_reasoning', 'N/A')}")


def display_node_1b_requirements(data: Optional[Dict[str, Any]], expanded: bool = False) -> None:
    """Display Node 1B: Requirements"""
    if data:
        with st.expander("📋 Step 1B: Requirements", expanded=expanded):
            st.write(f"**Analysis Type:** {data.get('analysis_type', 'N/A')}")
            st.write(f"**Variables Needed:** {', '.join(data.get('variables_needed', []))}")
            if data.get('constraints'):
                st.write(f"**Constraints:** {', '.join(data.get('constraints', []))}")
            st.write(f"**Success Criteria:** {data.get('success_criteria', 'N/A')}")
            if data.get('reasoning'):
                st.write(f"**Reasoning:** {data.get('reasoning', 'N/A')}")


def display_node_2_profile(data: Optional[Dict[str, Any]], expanded: bool = False) -> None:
    """Display Node 2: Data Profile"""
    if data:
        with st.expander("📊 Step 2: Data Profile", expanded=expanded):
            st.write(f"**Available Columns:** {', '.join(data.get('available_columns', []))}")
            if data.get('missing_columns'):
                st.write(f"**Missing Columns:** {', '.join(data.get('missing_columns', []))}")
            st.write(f"**Suitable:** {data.get('is_suitable', 'N/A')}")
            if data.get('limitations'):
                st.write(f"**Limitations:** {', '.join(data.get('limitations', []))}") 
            if data.get('reasoning'):
                st.write(f"**Reasoning:** {data.get('reasoning', 'N/A')}")


def display_node_3_alignment(data: Optional[Dict[str, Any]], expanded: bool = False) -> None:
    """Display Node 3: Alignment Check"""
    if data:
        with st.expander("🔗 Step 3: Alignment Check", expanded=expanded):
            st.write(f"**Aligned:** {data.get('aligned', 'N/A')}")
            if data.get('gaps'):
                st.write(f"**Gaps:** {', '.join(data.get('gaps', []))}")
            st.write(f"**Recommendation:** {data.get('recommendation', 'N/A')}")
            if data.get('reasoning'):
                st.write(f"**Reasoning:** {data.get('reasoning', 'N/A')}")


def display_failed_attempts(failed_attempts: List[Dict[str, Any]], expanded: bool = False) -> None:
    """Display failed code attempts"""
    if failed_attempts:
        for failed in failed_attempts:
            attempt_num = failed['attempt']
            with st.expander(f"❌ Failed Attempt {attempt_num}", expanded=expanded):
                st.code(failed['code'], language="python")
                st.error(f"**Error:** {failed['error'][:500]}{'...' if len(failed['error']) > 500 else ''}")


def display_node_4_code(code: Optional[str], failed_attempts: Optional[List[Dict[str, Any]]] = None, expanded: bool = False) -> None:
    """Display Node 4: Code Generation"""
    if code:
        title = f"💻 Step 4: Code Generation (Attempt {len(failed_attempts or []) + 1} - Success ✅)" if failed_attempts else "💻 Step 4: Code Generation"
        with st.expander(title, expanded=expanded):
            st.code(code, language="python")


def display_code_execution_output(result_str: Optional[str], expanded: bool = False) -> None:
    """Display Code Execution Output"""
    if result_str:
        with st.expander("⚙️ Code Execution Output", expanded=expanded):
            st.code(result_str)


def display_node_5_evaluation(data: Optional[Any], expanded: bool = False) -> None:
    """Display Node 5: Result Evaluation"""
    if data:
        with st.expander("🔍 Step 5: Result Evaluation", expanded=expanded):
            if isinstance(data, dict):
                st.write(f"**Valid:** {data.get('is_valid', 'N/A')}")
                st.write(f"**Confidence:** {data.get('confidence', 'N/A')}")
                if data.get('issues_found'):
                    st.write(f"**Issues:** {', '.join(data.get('issues_found', []))}")
                st.write(f"**Recommendation:** {data.get('recommendation', 'N/A')}")
                if data.get('reasoning'):
                    st.write(f"**Reasoning:** {data.get('reasoning', 'N/A')}")
            else:
                st.markdown(data)


def display_node_5a_remediation(data: Optional[Dict[str, Any]], total_remediations: Optional[int] = None, expanded: bool = False) -> None:
    """Display Node 5a: Remediation Plan"""
    if data:
        with st.expander("🔧 Step 5a: Remediation Plan", expanded=expanded):
            st.write(f"**Root Cause:** {data.get('root_cause', 'N/A')}")
            st.write(f"**Action:** {data.get('action', 'N/A')}")
            st.write(f"**Guidance:** {data.get('guidance', 'N/A')}")
            if total_remediations is not None:
                st.write(f"**Total Remediations:** {total_remediations}")


def display_node_6_explanation(explanation: Optional[str], expanded: bool = True) -> None:
    """Display Node 6: Final Report"""
    if explanation:
        with st.expander("✍️ Final Report", expanded=expanded):
            st.markdown(explanation)


def display_all_nodes(metadata: Dict[str, Any], expanded_final_report: bool = True) -> None:
    """
    Display all MVP architecture nodes from metadata.
    
    Args:
        metadata: Dictionary containing all node outputs
        expanded_final_report: Whether to expand the final report by default
    """
    # Node 0: Question Understanding
    if metadata.get("question_reasoning"):
        display_node_0_understanding({
            "needs_data_work": metadata.get("needs_data_work"),
            "question_reasoning": metadata.get("question_reasoning")
        })
    
    # Node 1B: Requirements
    if metadata.get("requirements"):
        display_node_1b_requirements(metadata["requirements"])
    
    # Node 2: Data Profile
    if metadata.get("data_profile"):
        display_node_2_profile(metadata["data_profile"])
    
    # Node 3: Alignment Check
    if metadata.get("alignment_check"):
        display_node_3_alignment(metadata["alignment_check"])
    
    # Failed Attempts
    failed_attempts = metadata.get("failed_attempts", [])
    if failed_attempts:
        display_failed_attempts(failed_attempts)
    
    # Node 4: Code Generation
    if metadata.get("code"):
        display_node_4_code(metadata["code"], failed_attempts)
    
    # Code Execution Output
    if metadata.get("result_str"):
        display_code_execution_output(metadata["result_str"])
    
    # Node 5: Result Evaluation
    if metadata.get("evaluation"):
        display_node_5_evaluation(metadata["evaluation"])
    
    # Node 5a: Remediation Plan
    if metadata.get("remediation_plan"):
        display_node_5a_remediation(
            metadata["remediation_plan"],
            metadata.get("total_remediations")
        )
    
    # Node 6: Final Report
    if metadata.get("explanation"):
        display_node_6_explanation(metadata["explanation"], expanded=expanded_final_report)
