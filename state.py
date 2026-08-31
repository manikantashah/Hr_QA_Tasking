# ============================================================
# state.py
# ============================================================

from typing import TypedDict, Optional, List, Dict, Any


class TaskState(TypedDict, total=False):

    # ========================================================
    # USER QUESTION
    # ========================================================

    question: str


    # ========================================================
    # TASK ROUTING
    # ========================================================

    task_type: str

    route_reason: str


    # ========================================================
    # REQUISITION
    # ========================================================

    requisition_number: Optional[str]

    requisition_header_id: Optional[str]


    # ========================================================
    # CANDIDATE INFORMATION
    # ========================================================

    candidate_name: Optional[str]

    candidate_names: List[str]

    candidate_email: Optional[str]

    candidate_emails: List[str]


    # ========================================================
    # APPLICATION INFORMATION
    # ========================================================

    job_application_id: Optional[str]

    job_application_ids: List[str]


    # ========================================================
    # INTERVIEWER INFORMATION
    # ========================================================

    interviewer_names: List[str]

    interviewer_emails: List[str]

    # ========================================================
# LINKEDIN
# ========================================================

    job_description: str


    # ========================================================
    # INTERVIEW INFORMATION
    # ========================================================

    date: Optional[str]

    start_datetime: Optional[str]

    end_datetime: Optional[str]

    subject: Optional[str]


    # ========================================================
    # AVAILABILITY
    # ========================================================

    common_slots: List[Dict[str, Any]]

    selected_slot: Optional[Dict[str, Any]]


    # ========================================================
    # AGENT RESULTS
    # ========================================================

    candidate_result: Any

    screening_result: Any

    interviewer_result: Any

    availability_result: Any

    scheduling_result: Any

    email_generation_result: Any

    email_send_result: Any

    linkedin_result: Any

    # ========================================================
    # CONVERSATION / MISSING INFORMATION
    # ========================================================

    missing_information: List[str]

    waiting_for_user: bool

    awaiting_confirmation: bool

    confirmation_type: Optional[str]


    # ========================================================
    # MEMORY / CONFIRMATION
    # ========================================================

    # Original value typed by user when a typo is suspected
    original_candidate_input: Optional[str]

    original_interviewer_input: Optional[str]


    # Suggested value from Oracle data
    suggested_candidate: Optional[str]

    suggested_interviewer: Optional[str]


    # Canonical values after user confirms
    confirmed_candidate_name: Optional[str]

    confirmed_interviewer_names: List[str]


    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    final_response: str