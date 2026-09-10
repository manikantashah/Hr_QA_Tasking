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
    # FLOW / RESUME STAGE
    # ========================================================
    #
    # This tells the orchestrator where the workflow currently
    # is and where it should resume after user confirmation.
    #
    # Examples:
    #
    # START
    # TITLE_RESOLUTION
    # TITLE_SELECTION
    # CANDIDATE_RESOLUTION
    # CANDIDATE_SELECTION
    # INTERVIEWER_RESOLUTION
    # INTERVIEWER_SELECTION
    # AVAILABILITY_CHECK
    # AVAILABILITY_SLOT_SELECTION
    # SCHEDULE_INTERVIEW
    # COMPLETED
    #
    # This prevents already completed Oracle agents from being
    # called again after a user selects an option.
    # ========================================================

    flow_stage: Optional[str]


    # ========================================================
    # JOB REQUISITIONS
    # ========================================================

    requisition_title: Optional[str]


    # ========================================================
    # REQUISITION
    # ========================================================

    requisition_number: Optional[str]

    requisition_header_id: Optional[str]


    # ========================================================
    # TITLE RESOLUTION / CONFIRMATION
    # ========================================================

    original_title_input: Optional[str]

    suggested_title: Optional[str]

    suggested_titles: List[str]

    title_matches: List[Dict[str, Any]]


    # ========================================================
    # CANDIDATE INFORMATION
    # ========================================================

    candidate_name: Optional[str]

    candidate_names: List[str]

    candidate_email: Optional[str]

    candidate_emails: List[str]


    # ========================================================
    # CANDIDATE RESOLUTION / CONFIRMATION
    # ========================================================

    candidate_matches: List[Dict[str, Any]]

    suggested_candidates: List[str]


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
    # INTERVIEWER RESOLUTION / CONFIRMATION
    # ========================================================

    interviewer_matches: List[Dict[str, Any]]

    suggested_interviewers: List[str]


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

    interview_questions_result: Any


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

    # --------------------------------------------------------
    # Original values typed by the user
    # --------------------------------------------------------

    original_candidate_input: Optional[str]

    original_interviewer_input: Optional[str]

    original_title_input: Optional[str]


    # --------------------------------------------------------
    # Suggested values from Oracle / resolver
    # --------------------------------------------------------

    suggested_candidate: Optional[str]

    suggested_interviewer: Optional[str]

    suggested_title: Optional[str]


    # --------------------------------------------------------
    # Canonical values after user confirms
    # --------------------------------------------------------

    confirmed_candidate_name: Optional[str]

    confirmed_interviewer_names: List[str]

    confirmed_title_name: Optional[str]


    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    result_summary: Any

    final_response: str
