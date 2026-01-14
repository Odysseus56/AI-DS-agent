# Pages package for AI Data Scientist Agent
# Each page module contains a render_*() function that handles that page's UI

from .about_page import render_about_page
from .add_dataset_page import render_add_dataset_page
from .dataset_page import render_dataset_page
from .log_page import render_log_page
from .scenarios_page import (
    render_scenarios_page,
    should_auto_submit_next_question,
    get_next_scenario_question,
    advance_scenario_progress
)
from .chat_page import render_chat_page
from .quick_start_page import render_quick_start_page
from .helpers import (
    handle_file_upload,
    load_sample_dataset,
    _process_dataset
)

__all__ = [
    "render_about_page",
    "render_add_dataset_page", 
    "render_dataset_page",
    "render_log_page",
    "render_scenarios_page",
    "render_chat_page",
    "render_quick_start_page",
    "handle_file_upload",
    "load_sample_dataset",
    "should_auto_submit_next_question",
    "get_next_scenario_question",
    "advance_scenario_progress",
]
