
# ============================================================
# conversation.py
# ============================================================

import json
import re

from main import llm_intent


# ============================================================
# SAFE JSON PARSER
# ============================================================

def _safe_json_loads(value):
    """
    Safely parse JSON returned by the LLM.

    Handles:
        1. Normal JSON
        2. Markdown ```json fences
        3. Extra text after the first JSON object
        4. Multiple JSON values where the first object is valid
    """

    # --------------------------------------------------------
    # Already a dictionary
    # --------------------------------------------------------

    if isinstance(
        value,
        dict
    ):

        return value

    # --------------------------------------------------------
    # Must be a string
    # --------------------------------------------------------

    if not isinstance(
        value,
        str
    ):

        return {}

    content = value.strip()

    if not content:

        return {}

    # --------------------------------------------------------
    # Remove markdown fences
    # --------------------------------------------------------

    if content.startswith(
        "```"
    ):

        content = content.replace(
            "```json",
            ""
        )

        content = content.replace(
            "```",
            ""
        )

        content = content.strip()

    # --------------------------------------------------------
    # Normal JSON parsing
    # --------------------------------------------------------

    try:

        parsed = json.loads(
            content
        )

        if isinstance(
            parsed,
            dict
        ):

            return parsed

    except json.JSONDecodeError:

        pass

    # --------------------------------------------------------
    # Handle extra data after first JSON object
    # --------------------------------------------------------

    try:

        decoder = json.JSONDecoder()

        parsed, _ = decoder.raw_decode(
            content
        )

        if isinstance(
            parsed,
            dict
        ):

            return parsed

    except (
        json.JSONDecodeError,
        TypeError
    ):

        pass

    return {}


# ============================================================
# CLEAN TITLE INPUT
# ============================================================

def _clean_title_input(
    user_message
):
    """
    Remove a requisition number when the user includes it
    together with the title.

    Examples:

        Site Engineer
            ->
        Site Engineer

        Site Engineer (Trainee)
            ->
        Site Engineer (Trainee)

        Site Engineer (Trainee) (Requisition 44)
            ->
        Site Engineer (Trainee)

        Site Engineer (Trainee) - Requisition 44
            ->
        Site Engineer (Trainee)

        Site Engineer (Trainee), Requisition 44
            ->
        Site Engineer (Trainee)
    """

    title = str(
        user_message
    ).strip()

    if not title:

        return ""

    # --------------------------------------------------------
    # Remove:
    #
    # (Requisition 44)
    # (Requisition Number 44)
    #
    # from the end
    # --------------------------------------------------------

    title = re.sub(
        r"\s*\(\s*requisition\s*"
        r"(?:number\s*)?\d+\s*\)\s*$",
        "",
        title,
        flags=re.IGNORECASE
    ).strip()

    # --------------------------------------------------------
    # Remove:
    #
    # - Requisition 44
    # , Requisition 44
    #
    # from the end
    # --------------------------------------------------------

    title = re.sub(
        r"\s*[-,]\s*requisition\s*"
        r"(?:number\s*)?\d+\s*$",
        "",
        title,
        flags=re.IGNORECASE
    ).strip()

    # --------------------------------------------------------
    # Remove duplicate spaces
    # --------------------------------------------------------

    title = re.sub(
        r"\s+",
        " ",
        title
    ).strip()

    return title


# ============================================================
# HANDLE TITLE MULTIPLE
# ============================================================

def _handle_title_multiple(
    previous_state,
    user_message
):
    """
    Handle continuation when multiple job titles/requisitions
    were found.

    Supported user responses:

        1
        2
        3

    Requisition number:

        21
        102
        44

    Exact displayed option:

        Site Engineer (Requisition 21)

    Exact title:

        Site Engineer (Trainee)

    A new title is sent back through JOB_REQUISITIONS.
    """

    user_input = str(
        user_message
    ).strip()

    # ========================================================
    # EMPTY INPUT
    # ========================================================

    if not user_input:

        return {
            "action": "WAIT",
            "candidate_name": None,
            "interviewer_names": [],
            "requisition_number": None,
            "title_name": None,
            "date": None,
            "start_datetime": None,
            "end_datetime": None,
            "cancelled": False,
            "message": (
                "Please provide the option number, "
                "requisition number, or job title."
            )
        }

    normalized = user_input.lower()

    # ========================================================
    # CANCEL
    # ========================================================

    cancel_words = {
        "cancel",
        "cancel it",
        "forget it",
        "stop",
        "never mind",
        "nevermind"
    }

    if normalized in cancel_words:

        return {
            "action": "CANCEL",
            "candidate_name": None,
            "interviewer_names": [],
            "requisition_number": None,
            "title_name": None,
            "date": None,
            "start_datetime": None,
            "end_datetime": None,
            "cancelled": True,
            "message": "The current task has been cancelled."
        }

    # ========================================================
    # GET STORED TITLE MATCHES
    # ========================================================

    title_matches = previous_state.get(
        "title_matches",
        []
    )

    if not isinstance(
        title_matches,
        list
    ):

        title_matches = []

    # ========================================================
    # OPTION NUMBER
    # ========================================================

    if user_input.isdigit():

        number = int(user_input)

        # ----------------------------------------------------
        # OPTION NUMBER
        # ----------------------------------------------------

        if (
            1 <= number <= len(title_matches)
        ):

            selected = title_matches[
                number - 1
            ]

            if not isinstance(
                selected,
                dict
            ):

                return {
                    "action": "WAIT",
                    "candidate_name": None,
                    "interviewer_names": [],
                    "requisition_number": None,
                    "title_name": None,
                    "date": None,
                    "start_datetime": None,
                    "end_datetime": None,
                    "cancelled": False,
                    "message": (
                        "The selected option could not be recovered. "
                        "Please choose another option."
                    )
                }

            selected_title = selected.get(
                "title"
            )

            selected_requisition = selected.get(
                "requisition_number"
            )

            requisition_data = selected.get(
                "requisition",
                {}
            )

            # ------------------------------------------------
            # FALLBACK
            # ------------------------------------------------

            if (
                not selected_title
                and isinstance(
                    requisition_data,
                    dict
                )
            ):

                selected_title = (
                    requisition_data.get(
                        "Title"
                    )
                )

            if (
                not selected_requisition
                and isinstance(
                    requisition_data,
                    dict
                )
            ):

                selected_requisition = (
                    requisition_data.get(
                        "RequisitionNumber"
                    )
                )

            if (
                selected_title
                and selected_requisition
            ):

                return {
                    "action": "CONFIRM",
                    "candidate_name": None,
                    "interviewer_names": [],
                    "requisition_number": str(
                        selected_requisition
                    ),
                    "title_name": [
                        selected_title
                    ],
                    "date": None,
                    "start_datetime": None,
                    "end_datetime": None,
                    "cancelled": False,
                    "message": ""
                }

        # ----------------------------------------------------
        # DIRECT REQUISITION NUMBER
        # ----------------------------------------------------

        return {
            "action": "UPDATE",
            "candidate_name": None,
            "interviewer_names": [],
            "requisition_number": user_input,
            "title_name": None,
            "date": None,
            "start_datetime": None,
            "end_datetime": None,
            "cancelled": False,
            "message": ""
        }

    # ========================================================
    # EXACT DISPLAYED OPTION
    # ========================================================
    #
    # Example:
    #
    # User:
    #     Site Engineer (Requisition 21)
    #
    # We extract:
    #
    #     title = Site Engineer
    #     requisition = 21
    #
    # ========================================================

    option_match = re.match(
        r"^\s*(.*?)\s*\(\s*requisition(?:\s+number)?\s+(\d+)\s*\)\s*$",
        user_input,
        flags=re.IGNORECASE
    )

    if option_match:

        selected_title = (
            option_match.group(1).strip()
        )

        selected_requisition = (
            option_match.group(2).strip()
        )

        # ----------------------------------------------------
        # Check against stored title matches
        # ----------------------------------------------------

        for match in title_matches:

            if not isinstance(
                match,
                dict
            ):

                continue

            match_title = match.get(
                "title"
            )

            match_requisition = match.get(
                "requisition_number"
            )

            requisition_data = match.get(
                "requisition",
                {}
            )

            if (
                not match_title
                and isinstance(
                    requisition_data,
                    dict
                )
            ):

                match_title = (
                    requisition_data.get(
                        "Title"
                    )
                )

            if (
                not match_requisition
                and isinstance(
                    requisition_data,
                    dict
                )
            ):

                match_requisition = (
                    requisition_data.get(
                        "RequisitionNumber"
                    )
                )

            # ------------------------------------------------
            # Match requisition number first
            # ------------------------------------------------

            if (
                str(
                    match_requisition
                ).strip()
                ==
                selected_requisition
            ):

                return {
                    "action": "CONFIRM",
                    "candidate_name": None,
                    "interviewer_names": [],
                    "requisition_number": str(
                        match_requisition
                    ),
                    "title_name": [
                        match_title
                    ] if match_title else [
                        selected_title
                    ],
                    "date": None,
                    "start_datetime": None,
                    "end_datetime": None,
                    "cancelled": False,
                    "message": ""
                }

        # ----------------------------------------------------
        # Requisition was not found in the stored matches
        # ----------------------------------------------------

        return {
            "action": "WAIT",
            "candidate_name": None,
            "interviewer_names": [],
            "requisition_number": None,
            "title_name": None,
            "date": None,
            "start_datetime": None,
            "end_datetime": None,
            "cancelled": False,
            "message": (
                f"I could not find Requisition "
                f"{selected_requisition} in the options. "
                "Please select one of the listed options."
            )
        }

    # ========================================================
    # USER PROVIDED A TITLE
    # ========================================================

    cleaned_title = _clean_title_input(
        user_input
    )

    if not cleaned_title:

        return {
            "action": "WAIT",
            "candidate_name": None,
            "interviewer_names": [],
            "requisition_number": None,
            "title_name": None,
            "date": None,
            "start_datetime": None,
            "end_datetime": None,
            "cancelled": False,
            "message": (
                "Please provide a valid job title "
                "or requisition number."
            )
        }

    # ========================================================
    # SEND NEW TITLE BACK TO ORCHESTRATOR
    # ========================================================

    return {
        "action": "UPDATE",
        "candidate_name": None,
        "interviewer_names": [],
        "requisition_number": None,
        "title_name": [
            cleaned_title
        ],
        "date": None,
        "start_datetime": None,
        "end_datetime": None,
        "cancelled": False,
        "message": ""
    }

# ============================================================
# HANDLE MULTIPLE CANDIDATES
# ============================================================

def _handle_candidate_multiple(
    previous_state,
    user_message
):
    """
    Handle a continuation when multiple candidates were found.

    Supports:

        1
        2
        3

    or:

        exact candidate name

    or:

        candidate name with extra text

    Example:

        "1"
            ->
        first candidate

        "Jithu Daniel"
            ->
        matching candidate

    The selected candidate name is returned to api.py.

    api.py then updates previous_state and reruns:

        orchestrate()
            ->
        scheduling_flow()

    The requisition number is preserved.
    """

    user_input = str(
        user_message
    ).strip()

    # ========================================================
    # EMPTY INPUT
    # ========================================================

    if not user_input:

        return {

            "action":
                "WAIT",

            "candidate_name":
                None,

            "interviewer_names":
                [],

            "requisition_number":
                None,

            "title_name":
                None,

            "date":
                None,

            "start_datetime":
                None,

            "end_datetime":
                None,

            "cancelled":
                False,

            "message":
                "Please select a candidate by option number."
        }

    normalized = user_input.lower()

    # ========================================================
    # CANCEL
    # ========================================================

    cancel_words = {

        "cancel",
        "cancel it",
        "forget it",
        "stop",
        "never mind",
        "nevermind"
    }

    if normalized in cancel_words:

        return {

            "action":
                "CANCEL",

            "candidate_name":
                None,

            "interviewer_names":
                [],

            "requisition_number":
                None,

            "title_name":
                None,

            "date":
                None,

            "start_datetime":
                None,

            "end_datetime":
                None,

            "cancelled":
                True,

            "message":
                "The current task has been cancelled."
        }

    # ========================================================
    # GET STORED CANDIDATE MATCHES
    # ========================================================

    candidate_matches = previous_state.get(
        "candidate_matches",
        []
    )

    if not isinstance(
        candidate_matches,
        list
    ):

        candidate_matches = []

    # ========================================================
    # OPTION NUMBER
    # ========================================================

    if user_input.isdigit():

        option_number = int(
            user_input
        )

        if (
            1 <= option_number
            <= len(candidate_matches)
        ):

            selected = candidate_matches[
                option_number - 1
            ]

            if not isinstance(
                selected,
                dict
            ):

                return {

                    "action":
                        "WAIT",

                    "candidate_name":
                        None,

                    "interviewer_names":
                        [],

                    "requisition_number":
                        None,

                    "title_name":
                        None,

                    "date":
                        None,

                    "start_datetime":
                        None,

                    "end_datetime":
                        None,

                    "cancelled":
                        False,

                    "message":
                        "The selected candidate could not be recovered. Please choose another option."
                }

            selected_candidate_name = (
                selected.get(
                    "candidate_name"
                )
            )

            if not selected_candidate_name:

                candidate_data = selected.get(
                    "candidate",
                    {}
                )

                if isinstance(
                    candidate_data,
                    dict
                ):

                    selected_candidate_name = (
                        candidate_data.get(
                            "CandidateName"
                        )
                    )

            if selected_candidate_name:

                return {

                    "action":
                        "CONFIRM",

                    "candidate_name":
                        selected_candidate_name,

                    "interviewer_names":
                        [],

                    "requisition_number":
                        None,

                    "title_name":
                        None,

                    "date":
                        None,

                    "start_datetime":
                        None,

                    "end_datetime":
                        None,

                    "cancelled":
                        False,

                    "message":
                        ""
                }

        # ----------------------------------------------------
        # A number that is not an option number is not a
        # valid candidate selection.
        # ----------------------------------------------------

        return {

            "action":
                "WAIT",

            "candidate_name":
                None,

            "interviewer_names":
                [],

            "requisition_number":
                None,

            "title_name":
                None,

            "date":
                None,

            "start_datetime":
                None,

            "end_datetime":
                None,

            "cancelled":
                False,

            "message":
                (
                    "That option number is not valid. "
                    "Please select one of the listed candidates."
                )
        }

    # ========================================================
    # EXACT CANDIDATE NAME
    # ========================================================

    exact_matches = []

    for match in candidate_matches:

        if not isinstance(
            match,
            dict
        ):

            continue

        candidate_name = (
            match.get(
                "candidate_name"
            )
        )

        if not candidate_name:

            candidate_data = match.get(
                "candidate",
                {}
            )

            if isinstance(
                candidate_data,
                dict
            ):

                candidate_name = (
                    candidate_data.get(
                        "CandidateName"
                    )
                )

        if not candidate_name:

            continue

        if (
            str(
                candidate_name
            ).strip().lower()
            ==
            normalized
        ):

            exact_matches.append(
                match
            )

    # ========================================================
    # ONE EXACT NAME
    # ========================================================

    if len(
        exact_matches
    ) == 1:

        selected = exact_matches[0]

        selected_candidate_name = (
            selected.get(
                "candidate_name"
            )
        )

        if not selected_candidate_name:

            candidate_data = selected.get(
                "candidate",
                {}
            )

            if isinstance(
                candidate_data,
                dict
            ):

                selected_candidate_name = (
                    candidate_data.get(
                        "CandidateName"
                    )
                )

        return {

            "action":
                "CONFIRM",

            "candidate_name":
                selected_candidate_name,

            "interviewer_names":
                [],

            "requisition_number":
                None,

            "title_name":
                None,

            "date":
                None,

            "start_datetime":
                None,

            "end_datetime":
                None,

            "cancelled":
                False,

            "message":
                ""
        }

    # ========================================================
    # MULTIPLE SAME-NAME CANDIDATES
    # ========================================================

    if len(
        exact_matches
    ) > 1:

        options = []

        for index, match in enumerate(
            exact_matches,
            start=1
        ):

            candidate_name = (
                match.get(
                    "candidate_name"
                )
            )

            candidate_data = match.get(
                "candidate",
                {}
            )

            if (
                not candidate_name
                and
                isinstance(
                    candidate_data,
                    dict
                )
            ):

                candidate_name = (
                    candidate_data.get(
                        "CandidateName"
                    )
                )

            application_id = (
                match.get(
                    "jobApplicationId"
                )
            )

            if (
                not application_id
                and
                isinstance(
                    candidate_data,
                    dict
                )
            ):

                application_id = (
                    candidate_data.get(
                        "JobApplicationId"
                    )
                )

            if application_id:

                options.append(
                    f"{index}. "
                    f"{candidate_name} "
                    f"(Application {application_id})"
                )

            else:

                options.append(
                    f"{index}. "
                    f"{candidate_name}"
                )

        return {

            "action":
                "WAIT",

            "candidate_name":
                None,

            "interviewer_names":
                [],

            "requisition_number":
                None,

            "title_name":
                None,

            "date":
                None,

            "start_datetime":
                None,

            "end_datetime":
                None,

            "cancelled":
                False,

            "message":
                (
                    "Multiple candidates have that name. "
                    "Please select one:\n\n"
                    +
                    "\n".join(
                        options
                    )
                )
        }

    # ========================================================
    # CANDIDATE NAME NOT FOUND IN STORED MATCHES
    # ========================================================

    return {

        "action":
            "WAIT",

        "candidate_name":
            None,

        "interviewer_names":
            [],

        "requisition_number":
            None,

        "title_name":
            None,

        "date":
            None,

        "start_datetime":
            None,

        "end_datetime":
            None,

        "cancelled":
            False,

        "message":
            (
                f"I could not match '{user_input}' "
                "to the candidate options. "
                "Please select a candidate by option number."
            )
    }


# ============================================================
# HANDLE CONVERSATION RESPONSE
# ============================================================

def handle_conversation(
    previous_state,
    user_message
):

    # ========================================================
    # TITLE MULTIPLE
    # ========================================================
    #
    # User enters a new title.
    #
    # Example:
    #
    #     Site Engineer (Trainee)
    #
    # The title goes back through:
    #
    #     JOB_REQUISITIONS
    #
    # again.
    # ========================================================

    if (
        previous_state.get(
            "confirmation_type"
        )
        ==
        "title_multiple"
    ):

        return _handle_title_multiple(
            previous_state,
            user_message
        )

    # ========================================================
    # MULTIPLE CANDIDATES
    # ========================================================
    #
    # This is deterministic.
    #
    # Example:
    #
    # System:
    #
    #     1. Jithu Daniel
    #     2. Jithu Kumar
    #     3. Jithu Raj
    #
    # User:
    #
    #     1
    #
    # ========================================================

    if (
        previous_state.get(
            "confirmation_type"
        )
        ==
        "candidate_multiple"
    ):

        return _handle_candidate_multiple(
            previous_state,
            user_message
        )

    # ========================================================
    # NORMAL LLM CONVERSATION
    # ========================================================

    prompt = f"""
You are handling a continuing HR recruitment conversation.

The user has an existing pending task.

You must understand the user's latest message using
the previous conversation state.

Do NOT assume that the user only answers yes or no.

The user may:

- confirm a suggestion
- reject a suggestion
- provide a corrected candidate name
- provide a corrected interviewer name
- provide a missing requisition number
- provide a missing date
- provide a missing time
- change an earlier value
- cancel the task
- ask a new question
- provide partial information
- answer naturally in different wording

============================================================
PREVIOUS STATE
============================================================

{json.dumps(
    previous_state,
    indent=4,
    default=str
)}

============================================================
USER MESSAGE
============================================================

{user_message}

============================================================
RULES
============================================================

1. Understand the meaning of the user's message.

2. Do not depend on exact phrases.

3. Ignore capitalization when comparing names.

4. If the user confirms a previously suggested value,
   use that suggested value.

5. If the user rejects a suggested value but provides
   another value, use the new value.

6. If the user rejects a suggestion without providing
   another value, keep the task pending and ask naturally
   for whatever information is needed to continue.

7. If the user changes an existing value, update only
   that value and preserve the rest of the previous task.

8. If the user provides a missing value, add it to the
   previous state.

9. If the user clearly cancels the task, mark the task
   as cancelled.

10. Do not invent candidate names, interviewer names,
    emails, IDs, requisition numbers, dates or times.

11. Do not route the message as a new task unless the
    user clearly starts a new request.

12. Return ONLY ONE JSON object.

13. Do not return multiple JSON objects.

14. Do not return markdown code fences.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

Use this structure:

{{
    "action": "CONFIRM",
    "candidate_name": null,
    "interviewer_names": [],
    "requisition_number": null,
    "date": null,
    "start_datetime": null,
    "end_datetime": null,
    "cancelled": false,
    "message": ""
}}

Allowed actions:

CONFIRM
CORRECT
UPDATE
CANCEL
WAIT

Examples:

User:
"yes"

If previous suggestion was Jithu Daniel:

{{
    "action": "CONFIRM",
    "candidate_name": "Jithu Daniel",
    "interviewer_names": [],
    "requisition_number": null,
    "date": null,
    "start_datetime": null,
    "end_datetime": null,
    "cancelled": false,
    "message": ""
}}

User:
"No, use Mamdouh Salem."

{{
    "action": "CORRECT",
    "candidate_name": "Mamdouh Salem",
    "interviewer_names": [],
    "requisition_number": null,
    "date": null,
    "start_datetime": null,
    "end_datetime": null,
    "cancelled": false,
    "message": ""
}}

User:
"Actually make it 3 PM."

{{
    "action": "UPDATE",
    "candidate_name": null,
    "interviewer_names": [],
    "requisition_number": null,
    "date": null,
    "start_datetime": "updated value",
    "end_datetime": null,
    "cancelled": false,
    "message": ""
}}

User:
"Forget it."

{{
    "action": "CANCEL",
    "candidate_name": null,
    "interviewer_names": [],
    "requisition_number": null,
    "date": null,
    "start_datetime": null,
    "end_datetime": null,
    "cancelled": true,
    "message": ""
}}

If you cannot determine what the user means:

{{
    "action": "WAIT",
    "candidate_name": null,
    "interviewer_names": [],
    "requisition_number": null,
    "date": null,
    "start_datetime": null,
    "end_datetime": null,
    "cancelled": false,
    "message": "A natural clarification question"
}}
"""

    # ========================================================
    # CALL LLM
    # ========================================================

    response = llm_intent.invoke(
        prompt
    )

    # ========================================================
    # GET RESPONSE CONTENT
    # ========================================================

    content = (
        response.content
        if hasattr(
            response,
            "content"
        )
        else str(
            response
        )
    )

    # ========================================================
    # SAFE JSON PARSING
    # ========================================================

    result = _safe_json_loads(
        content
    )

    # ========================================================
    # INVALID LLM RESPONSE
    # ========================================================

    if not result:

        return {

            "action":
                "WAIT",

            "candidate_name":
                None,

            "interviewer_names":
                [],

            "requisition_number":
                None,

            "date":
                None,

            "start_datetime":
                None,

            "end_datetime":
                None,

            "cancelled":
                False,

            "message":
                (
                    "I could not understand that response. "
                    "Please clarify."
                )
        }

    return result
