
# ============================================================
# task_router.py
# ============================================================

import json
import re

from llm import llm
from state import TaskState


# ============================================================
# EXTRACT JSON OBJECT FROM LLM RESPONSE
# ============================================================

def extract_json_object(
    text: str
):
    """
    Extract the first complete JSON object from an LLM response.

    Handles:

        ```json
        {
            ...
        }
        ```

    and responses where the LLM adds text before or after JSON.
    """

    if not text:
        return None

    text = str(
        text
    ).strip()

    # ========================================================
    # REMOVE MARKDOWN CODE FENCES
    # ========================================================

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

    # ========================================================
    # FIND FIRST JSON OBJECT
    # ========================================================

    start = text.find(
        "{"
    )

    if start == -1:
        return None

    # ========================================================
    # FIND MATCHING CLOSING BRACE
    # ========================================================

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

        if (
            char == "\\"
            and
            in_string
        ):

            escape = True

            continue

        # ----------------------------------------------------
        # Enter / leave JSON string
        # ----------------------------------------------------

        if char == '"':

            in_string = not in_string

            continue

        # Ignore braces inside strings

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


# ============================================================
# ROUTE USER QUESTION
# ============================================================

def task_router(
    state: TaskState
):

    question = (
        state.get(
            "question",
            ""
        )
    )

    print(
        "\n========================================"
    )

    print(
        "TASK ROUTER"
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

    # ========================================================
    # PROMPT
    # ========================================================

    prompt = f"""
You are the TASK ROUTER for an HR Recruitment system.

Your job is to understand the user's question and identify
which ONE business task the user wants to perform.

============================================================
GENERAL INTENT UNDERSTANDING
============================================================

Understand the user's intent semantically.

Do not require the user to follow a predefined sentence.

The user may:

- change word order
- use different grammar
- use synonyms
- omit optional words
- use lowercase or uppercase
- use singular or plural wording
- use natural conversational language

Do not match the question literally against examples.

Determine the task from the meaning of the complete request.

Extract ONLY information explicitly provided by the user.

NEVER invent missing values.


============================================================
SUPPORTED TASK TYPES
============================================================

There are EXACTLY seven task types:

1. SCREENING

2. LIST_INTERVIEWERS

3. CHECK_AVAILABILITY

4. SCHEDULE_INTERVIEW

5. SEND_EMAIL

6. LINKEDIN_JOB_DESC

7. INTERVIEW_QUESTION


============================================================
VERY IMPORTANT - MISSING INFORMATION
============================================================

Missing information does NOT mean that the task type is
unknown.

FIRST identify the user's intended task.

THEN extract whatever information is available.

If required information is missing:

- still return the correct task_type
- return null for missing scalar values
- return [] for missing arrays

The orchestration layer will handle missing information.

For example:

User:

"Show me the interviewers?"

Correct task:

LIST_INTERVIEWERS

Even though the requisition number is missing.

Return:

{{
    "task_type": "LIST_INTERVIEWERS",
    "requisition_number": null
}}

DO NOT return:

{{
    "task_type": null
}}


Another example:

User:

"Check Charles's availability."

Correct:

{{
    "task_type": "CHECK_AVAILABILITY",
    "interviewer_names": ["Charles"],
    "date": null
}}


Another example:

User:

"Schedule an interview for Jithu."

Correct:

{{
    "task_type": "SCHEDULE_INTERVIEW",
    "candidate_name": "Jithu",
    "requisition_number": null,
    "title_name": null
}}


============================================================
1. SCREENING
============================================================

Choose SCREENING when the user wants to:

- screen a candidate
- screen multiple candidates
- move a candidate to screening
- move multiple candidates to screening
- perform screening for candidates

Examples:

"Move Manikanta to screening."

"Move Manikanta, Manohar and Akshay to screening
in requisition 44."

"Screen the candidates Manikanta and Manohar
in requisition 44."

Extract:

- candidate_name
- candidate_names
- requisition_number

Candidate JobApplicationIds are NOT extracted.

They will come later from:

CANDIDATEREQUISTION


============================================================
2. LIST_INTERVIEWERS
============================================================

Choose LIST_INTERVIEWERS whenever the user wants to:

- see interviewers
- list interviewers
- show interviewers
- know who the interviewers are
- get interviewer names
- get interviewer details
- find interviewers assigned to a requisition
- see assigned interviewers

Examples:

"Show me the interviewers?"

"Show me the interviewers."

"Show me the interviewers for requisition 44."

"Who are the interviewers?"

"Who are the interviewers for requisition 44?"

"List the interviewers."

"List the interviewers for requisition 44."

"Give me the interviewer details."

"Which interviewers are assigned to requisition 44?"

"Tell me the interviewers for requisition 44."

IMPORTANT:

If the user asks to SHOW/LIST/GET interviewers,
the task is LIST_INTERVIEWERS.

If the requisition number is missing,
the task is STILL LIST_INTERVIEWERS.

Example:

User:

"Show me the interviewers?"

Return:

{{
    "task_type": "LIST_INTERVIEWERS",
    "requisition_number": null
}}

If requisition number is provided:

User:

"Show me the interviewers for requisition 44."

Return:

{{
    "task_type": "LIST_INTERVIEWERS",
    "requisition_number": "44"
}}

Do NOT classify this as QA.

Do NOT return task_type null.

Do NOT ask the user for the requisition number.

The orchestration layer will ask for it.


============================================================
3. CHECK_AVAILABILITY
============================================================

Choose CHECK_AVAILABILITY when the user wants to:

- check interviewer availability
- check when an interviewer is free
- find interviewer free time
- find common availability
- find common free time
- find a common interview slot
- know which interviewers are available
- check free time
- find available interview slots

Examples:

"Give me Prem and Santhu common availability."

"When are Prem and Santhu both free?"

"Find a common interview slot for Prem and Santhu."

"Check Prem and Santhu availability on September 2."

"Give me Charles's free time on September 2."

"Show Charles's availability."

"Which interviewers are available for requisition 44
on September 2?"


============================================================
CHECK_AVAILABILITY - INTERVIEWER NAME
============================================================

If the user explicitly provides interviewer names,
extract them.

Example:

"Give me Charles Wood Devadoss Wood Fread's free time
on September 2."

Return:

{{
    "task_type": "CHECK_AVAILABILITY",
    "interviewer_names": [
        "Charles Wood Devadoss Wood Fread"
    ],
    "date": "2026-09-02"
}}

Do NOT split a full interviewer name.


============================================================
CHECK_AVAILABILITY - MULTIPLE INTERVIEWERS
============================================================

If multiple interviewers are clearly separated by:

- and
- &
- commas

extract them separately.

Example:

"Check Prem and Santhu availability."

Return:

{{
    "task_type": "CHECK_AVAILABILITY",
    "interviewer_names": [
        "Prem",
        "Santhu"
    ]
}}

Example:

"Check Prem, Santhu and Ravi availability."

Return:

{{
    "task_type": "CHECK_AVAILABILITY",
    "interviewer_names": [
        "Prem",
        "Santhu",
        "Ravi"
    ]
}}


============================================================
CHECK_AVAILABILITY - REQUISITION NUMBER
============================================================

The user may ask availability using a requisition number
instead of interviewer names.

Example:

"Which interviewers are available for requisition 44
on September 2?"

Return:

{{
    "task_type": "CHECK_AVAILABILITY",
    "requisition_number": "44",
    "interviewer_names": [],
    "date": "2026-09-02"
}}

IMPORTANT:

Do NOT ask the user for interviewer names.

The orchestration layer will:

1. Call INTERVIEWERDATA.
2. Get ALL interviewers assigned to requisition 44.
3. Extract their emails.
4. Call INTERVIEWER_AVAILABILITY.
5. Find available/common slots.


============================================================
IMPORTANT AVAILABILITY RULE
============================================================

If interviewer names are provided:

Use those interviewers.

If only requisition number is provided:

Use ALL interviewers assigned to that requisition.

If both interviewer names and requisition number are
provided:

Use the specified interviewer names and validate that
they belong to the requisition.

Do NOT invent interviewer names.

Do NOT invent interviewer emails.


============================================================
4. SCHEDULE_INTERVIEW
============================================================

Choose SCHEDULE_INTERVIEW when the user wants to:

- schedule an interview
- book an interview
- arrange an interview
- set up an interview


============================================================
SCHEDULE_INTERVIEW EXTRACTION
============================================================

For SCHEDULE_INTERVIEW extract:

- candidate_name
- candidate_names
- requisition_number if explicitly provided
- title_name if explicitly provided
- interviewer_names
- date
- start_datetime
- end_datetime
- subject if explicitly provided


============================================================
REQUISITION IDENTIFICATION FOR SCHEDULE_INTERVIEW
============================================================

The user may identify the requisition in either of
these ways:

1. Requisition number
2. Job / position title

If the user explicitly gives a requisition number:

    requisition_number = the number provided by the user

If the user explicitly gives a job / position title:

    title_name = the title provided by the user

Do NOT generate a requisition number.

Do NOT use a title to calculate or guess a requisition number.

The requisition number will be resolved later by the
orchestration layer using JOBREQUISITIONHR.


============================================================
JOB TITLE EXTRACTION FOR SCHEDULE_INTERVIEW
============================================================

For SCHEDULE_INTERVIEW, the user may identify the
requisition using a job or position title.

Examples:

"Schedule an interview for Jithu Daniel in requisition 44..."

Return:

{{
    "requisition_number": "44",
    "title_name": null
}}


"Schedule an interview for Jithu Daniel in Site Engineer..."

Return:

{{
    "requisition_number": null,
    "title_name": "Site Engineer"
}}


"Schedule an interview for Jithu Daniel for the Site Engineer
position..."

Return:

{{
    "requisition_number": null,
    "title_name": "Site Engineer"
}}


"Schedule an interview for Jithu Daniel for site enginner..."

Return:

{{
    "requisition_number": null,
    "title_name": "site enginner"
}}


IMPORTANT:

- Extract the job title exactly as supplied by the user.
- Do NOT correct spelling.
- Do NOT normalize spelling.
- Do NOT change the capitalization.
- Do NOT call any API here.
- Do NOT generate a requisition number.
- If a requisition number is explicitly provided, store it in
  requisition_number.
- If a job title is explicitly provided, store it in title_name.
- If both are provided, keep both.
- If neither is provided, set both to null.


============================================================
TITLE BOUNDARY RULE
============================================================

When extracting title_name, identify the complete job or
position title provided by the user.

Examples:

"in Site Engineer"

-> title_name = "Site Engineer"

"for the Site Engineer position"

-> title_name = "Site Engineer"

"in Senior Software Engineer"

-> title_name = "Senior Software Engineer"

"for Oracle HCM Consultant"

-> title_name = "Oracle HCM Consultant"

"for site enginner"

-> title_name = "site enginner"

Do NOT include these words as part of title_name when they
are only grammatical connectors:

- in
- for
- the
- position
- role
- job
- requisition

Example:

"in the Site Engineer position"

Correct:

"title_name": "Site Engineer"

Incorrect:

"title_name": "in the Site Engineer position"


============================================================
SCHEDULE_INTERVIEW - BOTH REQUISITION NUMBER AND TITLE
============================================================

If the user explicitly gives BOTH a requisition number
and a title:

Example:

"Schedule an interview for Jithu Daniel in requisition 44
for Site Engineer."

Return both:

{{
    "requisition_number": "44",
    "title_name": "Site Engineer"
}}

Do NOT remove either value.

The orchestration layer may use the requisition number
directly and does not need to call JOBREQUISITIONHR.


============================================================
SCHEDULE_INTERVIEW - TITLE RESOLUTION FLOW
============================================================

If requisition_number is provided:

    Use the provided requisition number.

    Do NOT call JOBREQUISITIONHR.

    Continue to:

    CANDIDATEREQUISTION


If requisition_number is NOT provided but title_name
is provided:

    Do NOT generate a requisition number here.

    The orchestration layer will:

        JOBREQUISITIONHR
                ↓
           resolve_title()
                ↓
        get RequisitionNumber
                ↓
        CANDIDATEREQUISTION


If neither requisition_number nor title_name is provided:

    Return both as null.

    Do NOT ask the user a question here.

    The orchestration layer handles the missing information.


============================================================
5. SEND_EMAIL
============================================================

Choose SEND_EMAIL when the user wants to:

- send an email
- send an email to a candidate
- send a selected email
- send a rejection email
- send an interview email
- notify a candidate
- send a recruitment email

Examples:

"Send an email to Mamdouh because he was selected."

"Send a rejection email to Manikanta."

"Send an interview email to Mamdouh."

"Notify Mamdouh that he was selected for the interview."

Extract:

- candidate_name
- requisition_number if explicitly provided
- email_type
- subject if explicitly provided
- body if explicitly provided
- note if explicitly provided

Possible email_type values:

selected
rejected
interview
other

Candidate email must NOT be generated here.

The orchestration layer will get it from:

CANDIDATEREQUISTION


============================================================
6. LINKEDIN_JOB_DESC
============================================================

Choose LINKEDIN_JOB_DESC when the user wants to:

- post a job description to LinkedIn
- publish a job description on LinkedIn
- post a hiring announcement on LinkedIn
- share a job opening on LinkedIn
- create a LinkedIn job post
- advertise a job on LinkedIn

Examples:

"Post this job description on LinkedIn:
We are hiring candidates with Python and MySQL skills."

"Publish this job opening on LinkedIn."

"Post on LinkedIn that we are hiring candidates with
good knowledge of Python and MySQL."

"Share this job description on LinkedIn."

Store the actual job description in:

"job_description"

Do not summarize it.

Do not rewrite it.

Do not invent content.


============================================================
7. INTERVIEW_QUESTION
============================================================

Choose INTERVIEW_QUESTION when the user wants to:

- get interview questions
- generate interview questions
- suggest interview questions
- get technical interview questions
- prepare interview questions for a job
- get interview questions for a requisition
- know what questions to ask for a job
- generate questions for interviewing a candidate
- get questions to ask during an interview
- prepare technical questions for a candidate


============================================================
INTERVIEW_QUESTION - IMPORTANT INTENT RULE
============================================================

If the user asks for QUESTIONS to use during an interview,
the task is INTERVIEW_QUESTION.

Examples:

"Give me some interview questions."

"Give me interview questions for requisition 44."

"What questions should I ask for requisition 44?"

"Generate interview questions for site engineer."

"Give me technical questions for site engineer."

"What questions can I ask for this job?"

"Prepare some interview questions for the candidate."

Do NOT classify these questions as:

SCREENING

CHECK_AVAILABILITY

SCHEDULE_INTERVIEW

LIST_INTERVIEWERS

The word "candidate" by itself does NOT make the task
SCREENING.

The word "interview" by itself does NOT make the task
SCHEDULE_INTERVIEW.

The intended action must be considered.


============================================================
INTERVIEW_QUESTION - REQUISITION NUMBER
============================================================

If the user explicitly provides a requisition number,
extract it.

Examples:

"Give me interview questions for requisition 44."

Return:

{{
    "task_type": "INTERVIEW_QUESTION",
    "requisition_number": "44"
}}


"Generate questions for requisition number 100."

Return:

{{
    "task_type": "INTERVIEW_QUESTION",
    "requisition_number": "100"
}}


"Interview questions for req 44."

Return:

{{
    "task_type": "INTERVIEW_QUESTION",
    "requisition_number": "44"
}}


Do NOT invent a requisition number.

Do NOT convert a job title into a requisition number.

Do NOT guess a requisition number.


============================================================
INTERVIEW_QUESTION - JOB TITLE
============================================================

If the user provides a job or position title instead of
a requisition number, extract the title into title_name.

Examples:

"Give me interview questions for Site Engineer."

Return:

{{
    "task_type": "INTERVIEW_QUESTION",
    "requisition_number": null,
    "title_name": "Site Engineer"
}}


"Generate technical questions for Senior Software Engineer."

Return:

{{
    "task_type": "INTERVIEW_QUESTION",
    "requisition_number": null,
    "title_name": "Senior Software Engineer"
}}


"Give me interview questions for site enginner."

Return:

{{
    "task_type": "INTERVIEW_QUESTION",
    "requisition_number": null,
    "title_name": "site enginner"
}}


IMPORTANT:

Extract the title exactly as supplied by the user.

Do NOT:

- correct spelling
- normalize spelling
- change capitalization
- invent a different title


============================================================
INTERVIEW_QUESTION - BOTH REQUISITION NUMBER AND TITLE
============================================================

If the user provides both a requisition number and a title,
return both values.

Example:

"Give me interview questions for requisition 44,
Site Engineer."

Return:

{{
    "task_type": "INTERVIEW_QUESTION",
    "requisition_number": "44",
    "title_name": "Site Engineer"
}}


Do NOT remove either value.


============================================================
INTERVIEW_QUESTION - MISSING INFORMATION
============================================================

If the user asks for interview questions but does not
provide either a requisition number or a job title:

Example:

"Give me some interview questions."

Return:

{{
    "task_type": "INTERVIEW_QUESTION",
    "requisition_number": null,
    "title_name": null
}}

Do NOT return task_type null.

Do NOT ask the user a question.

The orchestration layer will handle the missing information.


============================================================
INTERVIEW_QUESTION - TITLE BOUNDARY
============================================================

When extracting title_name, identify the complete job or
position title.

Examples:

"interview questions for Site Engineer"

-> title_name = "Site Engineer"

"questions for the Site Engineer position"

-> title_name = "Site Engineer"

"technical questions for Senior Software Engineer"

-> title_name = "Senior Software Engineer"

"questions for Oracle HCM Consultant role"

-> title_name = "Oracle HCM Consultant"

Do NOT include grammatical connector words:

- for
- the
- position
- role
- job
- requisition

unless they are genuinely part of the title.


============================================================
INTERVIEW_QUESTION - ORCHESTRATION FLOW
============================================================

If requisition_number is provided:

    Use the provided requisition number.

    Do NOT call JOBREQUISITIONHR.

    Continue directly to:

    INTERVIEW_QUESTION


If requisition_number is NOT provided but title_name
is provided:

    The orchestration layer will:

        JOBREQUISITIONHR
                ↓
           resolve_title()
                ↓
        get RequisitionNumber
                ↓
        INTERVIEW_QUESTION


If neither requisition_number nor title_name is provided:

    The orchestration layer will ask the user
    for the required information.


============================================================
BUSINESS FLOW
============================================================

------------------------------------------------------------
SCREENING
------------------------------------------------------------

SCREENING

        ↓

CANDIDATEREQUISTION

        ↓

Find requested candidates

        ↓

Extract JobApplicationId

        ↓

SCREENINGAGENT


------------------------------------------------------------
LIST INTERVIEWERS
------------------------------------------------------------

LIST_INTERVIEWERS

        ↓

Check requisition_number

        ↓

INTERVIEWERDATA

        ↓

Get ALL assigned interviewers

        ↓

Extract interviewer names

Extract interviewer emails

        ↓

Return interviewer details


------------------------------------------------------------
CHECK AVAILABILITY
------------------------------------------------------------

CHECK_AVAILABILITY

        ↓

IF interviewer names are provided

        ↓

INTERVIEWERDATA

        ↓

Find requested interviewers

        ↓

Get interviewer emails

        ↓

INTERVIEWER_AVAILABILITY

        ↓

Available slots


------------------------------------------------------------
CHECK AVAILABILITY USING REQUISITION
------------------------------------------------------------

CHECK_AVAILABILITY

        ↓

RequisitionNumber

        ↓

INTERVIEWERDATA

        ↓

Get ALL interviewers

        ↓

Extract emails

        ↓

INTERVIEWER_AVAILABILITY

        ↓

Available/common slots


------------------------------------------------------------
SCHEDULE INTERVIEW
------------------------------------------------------------

SCHEDULE_INTERVIEW

        ↓

If requisition number exists

        ↓

CANDIDATEREQUISTION

OR

If only title exists

        ↓

JOBREQUISITIONHR

        ↓

resolve_title()

        ↓

RequisitionNumber

        ↓

CANDIDATEREQUISTION

        ↓

Get candidate email

Get JobApplicationId

        ↓

INTERVIEWERDATA

        ↓

Get interviewer emails

        ↓

INTERVIEWER_AVAILABILITY

        ↓

Validate requested time

        ↓

SCHEDULING_TEAMS_MEETING


------------------------------------------------------------
SEND EMAIL
------------------------------------------------------------

SEND_EMAIL

        ↓

CANDIDATEREQUISTION

        ↓

Get candidate email

        ↓

EMAIL_HR

        ↓

Generate email

        ↓

HREMAILSEND


------------------------------------------------------------
LINKEDIN JOB DESCRIPTION
------------------------------------------------------------

LINKEDIN_JOB_DESC

        ↓

LinkedIn posting workflow


------------------------------------------------------------
INTERVIEW QUESTIONS
------------------------------------------------------------

INTERVIEW_QUESTION

        ↓

If requisition number exists

        ↓

INTERVIEW_QUESTION

        ↓

Generate interview questions


OR


If only title exists

        ↓

JOBREQUISITIONHR

        ↓

resolve_title()

        ↓

RequisitionNumber

        ↓

INTERVIEW_QUESTION

        ↓

Generate interview questions


============================================================
CRITICAL EXTRACTION RULE
============================================================

ONLY extract values explicitly present in the user's
message.

NEVER:

- guess
- invent
- fabricate
- assume
- generate missing internal values

NEVER generate:

- JobApplicationId
- candidate email
- interviewer email
- candidate ID
- person ID
- requisition header ID


============================================================
REQUISITION NUMBER RULE
============================================================

For SCREENING:

requisition_number is required.

For LIST_INTERVIEWERS:

requisition_number is required to execute the flow.

However, missing requisition number does NOT change
the task type.

For example:

"Show me the interviewers?"

must still be:

LIST_INTERVIEWERS

with:

"requisition_number": null


For SCHEDULE_INTERVIEW:

requisition_number OR title_name may identify the
requisition.

If requisition_number is not provided,
title_name may be provided instead.

Do NOT invent requisition_number.


For SEND_EMAIL:

requisition_number may be required to find the candidate.


For CHECK_AVAILABILITY:

requisition_number is optional if interviewer names
are provided.


For INTERVIEW_QUESTION:

requisition_number OR title_name may identify the
requisition.

If requisition_number is provided:

use it directly.

If only title_name is provided:

the orchestration layer resolves the title.

If neither is provided:

return both as null.

Do NOT invent requisition_number.


============================================================
CANDIDATE NAME RULE
============================================================

Treat a complete candidate name as ONE candidate.

Example:

"Jithu Daniel"

is:

"Jithu Daniel"

NOT:

"Jithu"

"Daniel"


For multiple candidates:

"Manikanta, Manohar and Akshay"

return:

[
    "Manikanta",
    "Manohar",
    "Akshay"
]


============================================================
INTERVIEWER NAME RULE
============================================================

Treat a complete interviewer name as ONE interviewer.

Example:

"Charles Wood Devadoss Wood Fread"

must remain:

"Charles Wood Devadoss Wood Fread"

Do NOT split the name because it contains spaces.

Multiple interviewers are created only when clearly
separated by:

- and
- &
- commas

Example:

"Prem and Santhu"

return:

[
    "Prem",
    "Santhu"
]


============================================================
INTERVIEWER EMAIL RULE
============================================================

Do NOT generate interviewer emails.

Interviewer emails normally come from:

INTERVIEWERDATA

Only return an email if the user explicitly provides it.


============================================================
DATE RULE
============================================================

Current year is:

2026

If the user gives only month and day,
use the year 2026.

Examples:

"September 2"

->

"date": "2026-09-02"

"August 27"

->

"date": "2026-08-27"

If a year is explicitly provided,
use that year.

Example:

"September 2, 2025"

->

"date": "2025-09-02"

If no date is provided:

"date": null


============================================================
TIME RULE
============================================================

If the user provides a time:

Extract it.

Example:

"September 2 at 10 AM"

->

"date": "2026-09-02"

"start_datetime": "2026-09-02T10:00:00"


If the user provides a range:

"September 2 from 10 AM to 2 PM"

->

"date": "2026-09-02"

"start_datetime": "2026-09-02T10:00:00"

"end_datetime": "2026-09-02T14:00:00"


If no time is provided:

"start_datetime": null

"end_datetime": null

Do NOT invent times.


============================================================
EMAIL TYPE RULE
============================================================

For SEND_EMAIL:

selected -> "selected"

rejected -> "rejected"

interview -> "interview"

otherwise -> "other"


============================================================
INTERVIEW QUESTIONS EXAMPLES
============================================================

Example 10:

User:

"Give me some interview questions for requisition number 44."

Correct:

{{
    "task_type": "INTERVIEW_QUESTION",
    "route_reason": "The user wants interview questions for requisition 44.",
    "candidate_name": null,
    "candidate_names": [],
    "requisition_number": "44",
    "title_name": null,
    "interviewer_names": [],
    "date": null,
    "start_datetime": null,
    "end_datetime": null,
    "subject": null,
    "email_type": null,
    "body": null,
    "note": null,
    "job_description": null
}}


Example 11:

User:

"Give me some interview questions for site engineer."

Correct:

{{
    "task_type": "INTERVIEW_QUESTION",
    "route_reason": "The user wants interview questions for the Site Engineer position.",
    "candidate_name": null,
    "candidate_names": [],
    "requisition_number": null,
    "title_name": "site engineer",
    "interviewer_names": [],
    "date": null,
    "start_datetime": null,
    "end_datetime": null,
    "subject": null,
    "email_type": null,
    "body": null,
    "note": null,
    "job_description": null
}}


Example 12:

User:

"What questions should I ask for requisition 44?"

Correct:

{{
    "task_type": "INTERVIEW_QUESTION",
    "route_reason": "The user wants interview questions for requisition 44.",
    "candidate_name": null,
    "candidate_names": [],
    "requisition_number": "44",
    "title_name": null,
    "interviewer_names": [],
    "date": null,
    "start_datetime": null,
    "end_datetime": null,
    "subject": null,
    "email_type": null,
    "body": null,
    "note": null,
    "job_description": null
}}


Example 13:

User:

"Generate technical interview questions for Senior Software Engineer."

Correct:

{{
    "task_type": "INTERVIEW_QUESTION",
    "route_reason": "The user wants technical interview questions for the Senior Software Engineer position.",
    "candidate_name": null,
    "candidate_names": [],
    "requisition_number": null,
    "title_name": "Senior Software Engineer",
    "interviewer_names": [],
    "date": null,
    "start_datetime": null,
    "end_datetime": null,
    "subject": null,
    "email_type": null,
    "body": null,
    "note": null,
    "job_description": null
}}


Example 14:

User:

"Give me some interview questions."

Correct:

{{
    "task_type": "INTERVIEW_QUESTION",
    "route_reason": "The user wants interview questions but did not specify a requisition or job title.",
    "candidate_name": null,
    "candidate_names": [],
    "requisition_number": null,
    "title_name": null,
    "interviewer_names": [],
    "date": null,
    "start_datetime": null,
    "end_datetime": null,
    "subject": null,
    "email_type": null,
    "body": null,
    "note": null,
    "job_description": null
}}


============================================================
MISSING INFORMATION EXAMPLES
============================================================

Example 1:

User:

"Show me the interviewers?"

Correct:

{{
    "task_type": "LIST_INTERVIEWERS",
    "requisition_number": null
}}


Example 2:

User:

"Who are the interviewers for requisition 44?"

Correct:

{{
    "task_type": "LIST_INTERVIEWERS",
    "requisition_number": "44"
}}


Example 3:

User:

"Check Charles availability."

Correct:

{{
    "task_type": "CHECK_AVAILABILITY",
    "interviewer_names": ["Charles"],
    "date": null
}}


Example 4:

User:

"Give me Charles's free time on September 2."

Correct:

{{
    "task_type": "CHECK_AVAILABILITY",
    "interviewer_names": ["Charles"],
    "date": "2026-09-02"
}}


Example 5:

User:

"Which interviewers are available for requisition 44
on September 2?"

Correct:

{{
    "task_type": "CHECK_AVAILABILITY",
    "requisition_number": "44",
    "interviewer_names": [],
    "date": "2026-09-02"
}}


Example 6:

User:

"Schedule an interview for Jithu."

Correct:

{{
    "task_type": "SCHEDULE_INTERVIEW",
    "candidate_name": "Jithu",
    "requisition_number": null,
    "title_name": null
}}


Example 7:

User:

"Schedule an interview for Jithu Daniel in Site Engineer
with Charles Wood Devadoss Wood Fread on September 7
from 2:30 PM to 3 PM."

Correct:

{{
    "task_type": "SCHEDULE_INTERVIEW",
    "candidate_name": "Jithu Daniel",
    "requisition_number": null,
    "title_name": "Site Engineer",
    "interviewer_names": [
        "Charles Wood Devadoss Wood Fread"
    ],
    "date": "2026-09-07",
    "start_datetime": "2026-09-07T14:30:00",
    "end_datetime": "2026-09-07T15:00:00"
}}


Example 8:

User:

"Schedule an interview for Jithu Daniel in requisition 44
with Charles Wood Devadoss Wood Fread on September 7
from 2:30 PM to 3 PM."

Correct:

{{
    "task_type": "SCHEDULE_INTERVIEW",
    "candidate_name": "Jithu Daniel",
    "requisition_number": "44",
    "title_name": null,
    "interviewer_names": [
        "Charles Wood Devadoss Wood Fread"
    ],
    "date": "2026-09-07",
    "start_datetime": "2026-09-07T14:30:00",
    "end_datetime": "2026-09-07T15:00:00"
}}


Example 9:

User:

"Schedule an interview for Jithu Daniel for site enginner
with Charles Wood Devadoss Wood Fread."

Correct:

{{
    "task_type": "SCHEDULE_INTERVIEW",
    "candidate_name": "Jithu Daniel",
    "requisition_number": null,
    "title_name": "site enginner",
    "interviewer_names": [
        "Charles Wood Devadoss Wood Fread"
    ]
}}


============================================================
USER QUESTION
============================================================

{question}


============================================================
OUTPUT
============================================================

Return ONLY ONE valid JSON object.

Use EXACTLY this structure:

{{
    "task_type": null,
    "route_reason": null,

    "candidate_name": null,
    "candidate_names": [],

    "requisition_number": null,
    "title_name": null,

    "interviewer_names": [],

    "date": null,
    "start_datetime": null,
    "end_datetime": null,

    "subject": null,

    "email_type": null,

    "body": null,

    "note": null,

    "job_description": null
}}


Rules:

1. task_type MUST be exactly ONE of:

   SCREENING
   LIST_INTERVIEWERS
   CHECK_AVAILABILITY
   SCHEDULE_INTERVIEW
   SEND_EMAIL
   LINKEDIN_JOB_DESC
   INTERVIEW_QUESTION

2. Use null for missing scalar values.

3. Use [] for missing arrays.

4. Do not return Markdown.

5. Do not return explanations.

6. Do not return email addresses unless explicitly
   provided by the user.

7. Do not return JobApplicationId.

8. Do not return internal IDs unless explicitly provided.

9. Return ONE task only.

10. Treat complete person's names as ONE name.

11. Do not split multi-word candidate names.

12. Do not split multi-word interviewer names.

13. If the task is LINKEDIN_JOB_DESC, put only the actual
    job description in "job_description".

14. If month and day are given without year, use 2026.

15. If the task is LIST_INTERVIEWERS, extract the
    requisition_number when available.

16. If LIST_INTERVIEWERS has no requisition number,
    return task_type LIST_INTERVIEWERS and
    requisition_number null.

17. If CHECK_AVAILABILITY has a requisition number but
    no interviewer names, leave interviewer_names as [].

18. If CHECK_AVAILABILITY has interviewer names but no
    requisition number, leave requisition_number as null.

19. If SCHEDULE_INTERVIEW has a job/position title,
    extract it into title_name.

20. For SCHEDULE_INTERVIEW, do not generate a
    requisition_number from title_name.

21. If SCHEDULE_INTERVIEW contains only title_name,
    leave requisition_number null.

22. If SCHEDULE_INTERVIEW contains only requisition_number,
    leave title_name null.

23. If SCHEDULE_INTERVIEW contains both, return both.

24. Do NOT ask the user questions.

25. Do NOT return task_type null merely because information
    is missing.

26. First identify the user's intent, then extract values.

27. Extract title_name exactly as supplied by the user.

28. Do NOT correct spelling of title_name.

29. Do NOT include grammatical connector words such as
    "in", "for", "the", or "position" in title_name when
    they are not part of the actual title.

30. If the task is INTERVIEW_QUESTION and the user provides
    a requisition number, extract it into requisition_number.

31. If the task is INTERVIEW_QUESTION and the user provides
    only a job title, extract it into title_name.

32. If the task is INTERVIEW_QUESTION and both are provided,
    return both requisition_number and title_name.

33. If the task is INTERVIEW_QUESTION and neither is
    provided, return both requisition_number and title_name
    as null.

34. Do NOT invent a requisition number for
    INTERVIEW_QUESTION.

35. Do NOT classify a request for interview questions as
    SCHEDULE_INTERVIEW merely because the word "interview"
    appears.

36. Do NOT classify a request for interview questions as
    SCREENING merely because the word "candidate" appears.


============================================================
FINAL JSON VALIDATION
============================================================

Before returning the answer:

- response contains exactly one JSON object
- JSON starts with {{
- JSON ends with }}
- no text before JSON
- no text after JSON
- property names use double quotes
- string values use double quotes
- arrays use []
- missing scalar values use null

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
        "\nRAW ROUTER RESPONSE:"
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
            "Task router returned invalid JSON.\n"
            f"Response: {content}"
        )


    # ========================================================
    # VALIDATE RESULT TYPE
    # ========================================================

    if not isinstance(
        result,
        dict
    ):

        raise RuntimeError(
            "Task router JSON must be an object.\n"
            f"Response: {content}"
        )


    # ========================================================
    # VALIDATE TASK TYPE
    # ========================================================

    allowed_tasks = {

        "SCREENING",

        "LIST_INTERVIEWERS",

        "CHECK_AVAILABILITY",

        "SCHEDULE_INTERVIEW",

        "SEND_EMAIL",

        "LINKEDIN_JOB_DESC",

        "INTERVIEW_QUESTION"
    }

    task_type = (
        result.get(
            "task_type"
        )
    )

    if task_type not in allowed_tasks:

        raise ValueError(
            "Invalid task type returned by LLM: "
            f"{task_type}"
        )


    # ========================================================
    # NORMALIZE CANDIDATE NAMES
    # ========================================================

    candidate_names = (
        result.get(
            "candidate_names",
            []
        )
    )

    if not isinstance(
        candidate_names,
        list
    ):

        candidate_names = []

    candidate_names = [

        str(name).strip()

        for name in candidate_names

        if str(name).strip()
    ]


    # ========================================================
    # NORMALIZE INTERVIEWER NAMES
    # ========================================================

    interviewer_names = (
        result.get(
            "interviewer_names",
            []
        )
    )

    if not isinstance(
        interviewer_names,
        list
    ):

        interviewer_names = []

    interviewer_names = [

        str(name).strip()

        for name in interviewer_names

        if str(name).strip()
    ]


    # ========================================================
    # SINGLE CANDIDATE
    # ========================================================

    candidate_name = (
        result.get(
            "candidate_name"
        )
    )

    if candidate_name is not None:

        candidate_name = str(
            candidate_name
        ).strip()

        if not candidate_name:

            candidate_name = None


    # ========================================================
    # REQUISITION NUMBER
    # ========================================================

    requisition_number = (
        result.get(
            "requisition_number"
        )
    )

    if requisition_number is not None:

        requisition_number = str(
            requisition_number
        ).strip()

        if not requisition_number:

            requisition_number = None


    # ========================================================
    # TITLE NAME
    # ========================================================

    title_name = (
        result.get(
            "title_name"
        )
    )

    if title_name is not None:

        title_name = str(
            title_name
        ).strip()

        if not title_name:

            title_name = None


    # ========================================================
    # DATE
    # ========================================================

    date = (
        result.get(
            "date"
        )
    )

    if date is not None:

        date = str(
            date
        ).strip()

        if not date:

            date = None


    # ========================================================
    # START DATETIME
    # ========================================================

    start_datetime = (
        result.get(
            "start_datetime"
        )
    )

    if start_datetime is not None:

        start_datetime = str(
            start_datetime
        ).strip()

        if not start_datetime:

            start_datetime = None


    # ========================================================
    # END DATETIME
    # ========================================================

    end_datetime = (
        result.get(
            "end_datetime"
        )
    )

    if end_datetime is not None:

        end_datetime = str(
            end_datetime
        ).strip()

        if not end_datetime:

            end_datetime = None


    # ========================================================
    # ROUTE REASON
    # ========================================================

    route_reason = (
        result.get(
            "route_reason",
            ""
        )
    )

    if route_reason is None:

        route_reason = ""

    route_reason = str(
        route_reason
    ).strip()


    # ========================================================
    # RETURN STATE UPDATE
    # ========================================================

    return {

        "task_type":
            task_type,

        "route_reason":
            route_reason,

        "candidate_name":
            candidate_name,

        "candidate_names":
            candidate_names,

        "requisition_number":
            requisition_number,

        "title_name":
            title_name,

        "interviewer_names":
            interviewer_names,

        "date":
            date,

        "start_datetime":
            start_datetime,

        "end_datetime":
            end_datetime,

        "subject":
            result.get(
                "subject"
            ),

        "email_type":
            result.get(
                "email_type"
            ),

        "body":
            result.get(
                "body"
            ),

        "note":
            result.get(
                "note"
            ),

        "job_description":
            result.get(
                "job_description"
            )
    }

