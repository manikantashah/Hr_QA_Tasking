# ============================================================
# unified_router.py
# ============================================================

import json
import re

from llm import llm
from task_router import task_router


# ============================================================
# EXTRACT JSON OBJECT
# ============================================================

def extract_json_object(
    text: str
):
    """
    Extract the first complete JSON object from an LLM response.
    """

    if not text:
        return None

    text = str(text).strip()

    # --------------------------------------------------------
    # Remove markdown code fences
    # --------------------------------------------------------

    text = re.sub(
        r"```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"```\s*",
        "",
        text
    )

    text = text.strip()

    # --------------------------------------------------------
    # Find first JSON object
    # --------------------------------------------------------

    start = text.find("{")

    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for index in range(
        start,
        len(text)
    ):

        char = text[index]

        # ----------------------------------------------------
        # Escaped character
        # ----------------------------------------------------

        if escape:
            escape = False
            continue

        if char == "\\" and in_string:
            escape = True
            continue

        # ----------------------------------------------------
        # String boundary
        # ----------------------------------------------------

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        # ----------------------------------------------------
        # Opening brace
        # ----------------------------------------------------

        if char == "{":
            depth += 1

        # ----------------------------------------------------
        # Closing brace
        # ----------------------------------------------------

        elif char == "}":

            depth -= 1

            if depth == 0:

                json_text = text[
                    start:index + 1
                ]

                try:

                    return json.loads(
                        json_text
                    )

                except json.JSONDecodeError:

                    return None

    return None

def update_missing_information(state):
    """
    Recalculate missing information based on the current state.
    """

    missing = []

    task_type = state.get("task_type")

    # ========================================================
    # CHECK AVAILABILITY
    # ========================================================

    if task_type == "CHECK_AVAILABILITY":

        requisition_number = state.get(
            "requisition_number"
        )

        interviewer_names = state.get(
            "interviewer_names"
        )

        date = state.get(
            "date"
        )

        # ----------------------------------------------------
        # INTERVIEWER / REQUISITION
        # ----------------------------------------------------
        # At least one of these is required.
        #
        # If requisition_number is provided but interviewer
        # names are not provided, the orchestration layer can
        # retrieve interviewers from INTERVIEWERDATA.
        # ----------------------------------------------------

        if (
            not requisition_number
            and
            not interviewer_names
        ):

            missing.append(
                "requisition_or_interviewer"
            )

        # ----------------------------------------------------
        # DATE
        # ----------------------------------------------------

        if not date:

            missing.append(
                "date"
            )

    # ========================================================
    # SCHEDULE INTERVIEW
    # ========================================================

    elif task_type == "SCHEDULE_INTERVIEW":

        # ----------------------------------------------------
        # CANDIDATE
        # ----------------------------------------------------

        if not state.get(
            "candidate_name"
        ):

            missing.append(
                "candidate_name"
            )

        # ----------------------------------------------------
        # REQUISITION
        # ----------------------------------------------------

        if not state.get(
            "requisition_number"
        ):

            missing.append(
                "requisition_number"
            )

        # ----------------------------------------------------
        # INTERVIEWER
        # ----------------------------------------------------

        if not state.get(
            "interviewer_names"
        ):

            missing.append(
                "interviewer"
            )

        # ----------------------------------------------------
        # DATE
        # ----------------------------------------------------

        if not state.get(
            "date"
        ):

            missing.append(
                "date"
            )

        # ----------------------------------------------------
        # START DATETIME
        # ----------------------------------------------------

        if not state.get(
            "start_datetime"
        ):

            missing.append(
                "start_datetime"
            )

        # ----------------------------------------------------
        # END DATETIME
        # ----------------------------------------------------

        if not state.get(
            "end_datetime"
        ):

            missing.append(
                "end_datetime"
            )

    # ========================================================
    # SAVE MISSING INFORMATION
    # ========================================================

    state["missing_information"] = missing

    return state
# ============================================================
# CLASSIFY HR REQUEST
# ============================================================

def classify_mode(
    question: str
) -> str:
    """
    Classify the user's request as:

        TASKING
        QA

    TASKING = user wants an HR operation.

    QA = user wants information from HR recruitment data.
    """

    # ========================================================
    # SAFETY CHECK
    # ========================================================

    if not question:

        raise ValueError(
            "Question cannot be empty."
        )

    # ========================================================
    # PROMPT
    # ========================================================

    prompt = f"""
You are the TOP-LEVEL ROUTER for a combined HR Recruitment
system.

Your job is to decide whether the user's request is:

1. TASKING
2. QA

============================================================
1. TASKING
============================================================

Use TASKING when the user wants the system to perform
an HR operation or retrieve information through a task
workflow.

Examples:

- screen a candidate
- move a candidate to screening
- show interviewers assigned to a requisition
- list interviewers for a requisition
- get interviewers for a requisition
- check interviewer availability
- find interviewer free time
- find common interviewer availability
- schedule an interview
- book an interview
- arrange an interview
- send an email
- send an interview notification
- send a rejection email
- post a job description to LinkedIn
- publish a job opening on LinkedIn

============================================================
2. QA
============================================================

Use QA when the user wants general information from the
HR recruitment data.

Examples:

- what are a candidate's skills?
- what is a candidate's education?
- what is the candidate's experience?
- compare candidate AI scores
- give me candidate details
- who is the recruiter?
- show candidates in requisition 44

============================================================
IMPORTANT INTERVIEWER RULE
============================================================

Questions about interviewers assigned to a specific
requisition are TASKING requests.

Examples:

"Show me the interviewers for requisition 44."

-> TASKING

"Who are the interviewers for requisition 44?"

-> TASKING

"List the interviewers assigned to requisition 44."

-> TASKING

"Get the interviewers for requisition 44."

-> TASKING

"What interviewers are assigned to requisition 44?"

-> TASKING

These MUST NOT be classified as QA.

They must be sent to:

TASKING
    ↓
LIST_INTERVIEWERS
    ↓
INTERVIEWERDATA

============================================================
IMPORTANT AVAILABILITY RULE
============================================================

Questions about interviewer availability are TASKING.

Examples:

"Is Charles Wood available on September 2?"

-> TASKING

"Give me Charles Wood's free time on September 2."

-> TASKING

"When are Charles and Farid both free?"

-> TASKING

"Which interviewers are available for requisition 44
on September 2?"

-> TASKING

If the user provides a requisition number but does not
provide interviewer names, the task workflow will retrieve
the interviewers from INTERVIEWERDATA.

Do NOT classify these questions as QA.

============================================================
SCHEDULE RULE
============================================================

Questions asking to schedule, book, arrange, or create
an interview are always TASKING.

Examples:

"Schedule an interview for Jithu."

-> TASKING

"Book an interview with Charles."

-> TASKING

"Arrange an interview for Jithu on September 2."

-> TASKING

============================================================
EMAIL RULE
============================================================

Questions asking the system to send an email are TASKING.

Examples:

"Send an email to Jithu."

-> TASKING

"Send a rejection email to Manikanta."

-> TASKING

"Send an interview email."

-> TASKING

============================================================
LINKEDIN RULE
============================================================

The following are TASKING:

"Post this job description on LinkedIn."

"Publish this job opening on LinkedIn."

"Share this job description on LinkedIn."

"Create a LinkedIn job post."

============================================================
JOB DESCRIPTION RULE
============================================================

A standalone complete job description is TASKING.

Example:

"# Job Description - AI Engineer

## Position

AI Engineer

## Job Summary

We are looking for a talented AI Engineer...

## Key Responsibilities

...

## Required Skills

...

## Education

...

## Experience

..."

-> TASKING

A standalone complete job description is intended for
the LinkedIn job-posting workflow.

Therefore:

Standalone Job Description
        ↓
TASKING
        ↓
LINKEDIN_JOB_DESC

Do NOT classify a complete standalone job description as QA.

============================================================
GENERAL INTENT RULE
============================================================

Understand the meaning of the COMPLETE request.

Do not require fixed sentence structure.

The user may:

- change word order
- use different grammar
- use synonyms
- use different capitalization
- use singular or plural wording
- ask naturally
- use short or long sentences

Ignore capitalization.

Do NOT classify based only on one keyword.

Determine whether the user wants:

ACTION / TASK
or
INFORMATION / QA

============================================================
EXAMPLES
============================================================

"Show me the interviewers for requisition 44."

-> TASKING

"Who are the interviewers for requisition 44?"

-> TASKING

"List the interviewers assigned to requisition 44."

-> TASKING

"Give me Charles Wood's free time on September 2."

-> TASKING

"Which interviewers are available for requisition 44
on September 2?"

-> TASKING

"Give me Charles and Farid common availability."

-> TASKING

"Schedule an interview for Jithu."

-> TASKING

"Send an email to Jithu."

-> TASKING

"What are Jithu Daniel's skills?"

-> QA

"Show me Jithu Daniel's experience."

-> QA

"Give me all candidates in requisition 44."

-> QA

"Who is the recruiter for Jithu Daniel?"

-> QA

============================================================
FINAL CLASSIFICATION PRINCIPLE
============================================================

If the user wants an ACTION or TASK:
TASKING

If the user wants general HR DATA INFORMATION:
QA

If the user asks to list/show/get interviewers assigned
to a requisition:
TASKING

If the user asks about interviewer availability:
TASKING

If the user asks to schedule an interview:
TASKING

If the user asks to send an email:
TASKING

If the user asks to post a job description to LinkedIn:
TASKING

If the user provides a complete standalone job description:
TASKING

============================================================
USER QUESTION
============================================================

{question}

============================================================
OUTPUT RULE
============================================================

Return ONLY one JSON object.

Do not provide:

- reasoning
- explanations
- introductory text
- Markdown
- code fences
- text before JSON
- text after JSON

Valid output MUST be exactly:

{{"mode":"TASKING"}}

or

{{"mode":"QA"}}
"""

    # ========================================================
    # CALL LLM
    # ========================================================

    response = llm.invoke(
        prompt
    )

    content = (
        response.content
        .strip()
    )

    print(
        "\n========================================"
    )

    print(
        "UNIFIED ROUTER"
    )

    print(
        "========================================"
    )

    print(
        "USER QUESTION:"
    )

    print(
        question
    )

    print(
        "\nRAW UNIFIED ROUTER RESPONSE:"
    )

    print(
        content
    )

    # ========================================================
    # EXTRACT JSON
    # ========================================================

    result = extract_json_object(
        content
    )

    if result is None:

        raise RuntimeError(
            "Unified router returned invalid JSON.\n"
            f"Response: {content}"
        )

    # ========================================================
    # VALIDATE OBJECT
    # ========================================================

    if not isinstance(
        result,
        dict
    ):

        raise RuntimeError(
            "Unified router response must be a JSON object.\n"
            f"Response: {content}"
        )

    # ========================================================
    # GET MODE
    # ========================================================

    mode = result.get(
        "mode"
    )

    # ========================================================
    # VALIDATE MODE
    # ========================================================

    if mode not in {
        "TASKING",
        "QA"
    }:

        raise ValueError(
            f"Invalid unified router mode: {mode}"
        )

    print(
        "\nUNIFIED ROUTER MODE:"
    )

    print(
        mode
    )

    return mode


# ============================================================
# ROUTE REQUEST
# ============================================================

def route_request(
    question: str
):
    """
    Route the request to:

        TASKING
        or
        QA
    """

    mode = classify_mode(
        question
    )

    # ========================================================
    # TASKING
    # ========================================================

    if mode == "TASKING":

        state = {
            "question": question
        }

        task_state = task_router(
            state
        )

        return (
            mode,
            task_state
        )

    # ========================================================
    # QA
    # ========================================================

    return (
        mode,
        {
            "question": question
        }
    )