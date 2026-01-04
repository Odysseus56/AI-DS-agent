"""About page for AI Data Scientist Agent."""
import streamlit as st


def render_about_page():
    """Render the About page with app information and documentation."""
    st.markdown("""
    ### 🎯 Key Strengths

    **1. Writes Code to Analyze Datasets**  
    Generates Python code for statistical analysis, ML models, and data transformations.

    **2. Multi-Dataset Intelligence**  
    Analyze across multiple datasets in one conversation with automatic context management.

    **3. Complete Transparency**  
    4-stage workflow shows execution planning, code generation, evaluation, and final report.

    **4. Auto Error Recovery**  
    Self-debugging with up to 3 retry attempts - GPT-4 fixes errors automatically.

    ---
    
    ### 🛠️ Technical Stack

    - **LLM:** GPT-4o for code generation, GPT-4o-mini for planning
    - **Data:** pandas, numpy, scipy, statsmodels
    - **Viz:** Plotly, matplotlib, seaborn
    - **ML:** scikit-learn
    - **UI:** Streamlit

    ---
    
    ### 💡 Use Cases

    - **Business:** Customer segmentation, campaign analysis, revenue forecasting
    - **Research:** Hypothesis testing, experimental design, statistical modeling
    - **Operations:** Process optimization, anomaly detection, trend analysis
    - **Compliance:** Auditable workflows with full documentation

    ---
    
    ### 🚀 Getting Started

    1. Upload dataset(s) via "Add Dataset"
    2. Ask questions in natural language
    3. Expand debug dropdowns to see workflow
    4. Download logs for reproducibility
    """)

    st.divider()

    st.markdown("*Built with ❤️ for data-driven decision making*")
