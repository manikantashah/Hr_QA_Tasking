
# ============================================================
# conversation.py
# ============================================================

import json
import re
from datetime import datetime
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

    if isinstance(value, dict):
        return value

    # --------------------------------------------------------
    # Must be a string
    # --------------------------------------------------------

    if not isinstance(value, str):
        return {}

    content = value.strip()

    if not content:
        return {}

    # --------------------------------------------------------
    # Remove markdown fences
    # --------------------------------------------------------

    if content.startswith("```"):
        content = content.replace("```json", "")
        content = content.replace("```", "")
        content = content.strip()

    # --------------------------------------------------------
    # Normal JSON parsing
    # --------------------------------------------------------

    try:
        parsed = json.loads(content)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------------
    # Handle extra data after first JSON object
    # --------------------------------------------------------

    try:
        decoder = json.JSONDecoder()

        parsed, _ = decoder.raw_decode(content)

        if isinstance(parsed, dict):
            return parsed

    except (
        json.JSONDecodeError,
        TypeError
    ):
        pass

    return {}


# ============================================================
# NORMALIZE DATE / TIME
# ============================================================

def _normalize_datetime_result(
    user_message,
    result
):
    """
    Convert natural-language date/time values returned by the
    LLM into ISO date/time values expected by the scheduling flow.

    Example:

        User:
            September 15 from 09:30 AM to 10:00 AM.

        LLM:
            date = "September 15"
            start_datetime = "09:30 AM"
            end_datetime = "10:00 AM"

        Final:
            date = "2026-09-15"
            start_datetime = "2026-09-15T09:30:00"
            end_datetime = "2026-09-15T10:00:00"

    If the user explicitly gives a year, that year is preserved.
    """

    # --------------------------------------------------------
    # Current year
    # --------------------------------------------------------

    current_year = datetime.now().year

    # --------------------------------------------------------
    # User's latest message
    # --------------------------------------------------------

    user_text = str(
        user_message
    ).strip()

    # --------------------------------------------------------
    # Check whether the user explicitly supplied a year
    #
    # Examples:
    #
    # September 15, 2026
    # September 15 2027
    # 15/09/2026
    # 2028-09-15
    # --------------------------------------------------------

    year_matches = re.findall(
        r"\b(20\d{2})\b",
        user_text
    )

    if year_matches:
        target_year = int(
            year_matches[0]
        )
    else:
        target_year = current_year

    # ========================================================
    # GET VALUES FROM LLM RESULT
    # ========================================================

    date_value = result.get(
        "date"
    )

    start_value = result.get(
        "start_datetime"
    )

    end_value = result.get(
        "end_datetime"
    )

    # ========================================================
    # NORMALIZE DATE
    # ========================================================

    parsed_date = None

    if date_value:

        date_text = str(
            date_value
        ).strip()

        # ----------------------------------------------------
        # Already ISO date
        # ----------------------------------------------------

        try:

            parsed_date = datetime.strptime(
                date_text[:10],
                "%Y-%m-%d"
            )

        except ValueError:

            parsed_date = None

        # ----------------------------------------------------
        # Natural language date
        #
        # September 15
        # September 15, 2026
        # Sep 15
        # Sep 15, 2026
        # ----------------------------------------------------

        if parsed_date is None:

            formats = [
                "%B %d",
                "%B %d, %Y",
                "%b %d",
                "%b %d, %Y"
            ]

            for fmt in formats:

                try:

                    parsed_date = datetime.strptime(
                        date_text,
                        fmt
                    )

                    break

                except ValueError:

                    continue

        # ----------------------------------------------------
        # Apply target year
        # ----------------------------------------------------

        if parsed_date is not None:

            parsed_date = parsed_date.replace(
                year=target_year
            )

            result["date"] = parsed_date.strftime(
                "%Y-%m-%d"
            )

    # ========================================================
    # NORMALIZE START DATETIME
    # ========================================================

    if start_value:

        start_text = str(
            start_value
        ).strip()

        parsed_start = None

        # ----------------------------------------------------
        # Already full ISO datetime
        # ----------------------------------------------------

        try:

            parsed_start = datetime.fromisoformat(
                start_text
            )

        except ValueError:

            parsed_start = None

        # ----------------------------------------------------
        # Natural time
        #
        # 09:30 AM
        # 9:30 AM
        # 14:30
        # 9:30
        # ----------------------------------------------------

        if parsed_start is None:

            time_formats = [
                "%I:%M %p",
                "%I %p",
                "%H:%M"
            ]

            for fmt in time_formats:

                try:

                    parsed_time = datetime.strptime(
                        start_text,
                        fmt
                    )

                    parsed_start = parsed_time

                    break

                except ValueError:

                    continue

        # ----------------------------------------------------
        # Combine time with the extracted date
        # ----------------------------------------------------

        if (
            parsed_start is not None
            and
            parsed_date is not None
        ):

            parsed_start = parsed_start.replace(
                year=target_year,
                month=parsed_date.month,
                day=parsed_date.day
            )

            result["start_datetime"] = (
                parsed_start.strftime(
                    "%Y-%m-%dT%H:%M:%S"
                )
            )

    # ========================================================
    # NORMALIZE END DATETIME
    # ========================================================

    if end_value:

        end_text = str(
            end_value
        ).strip()

        parsed_end = None

        # ----------------------------------------------------
        # Already full ISO datetime
        # ----------------------------------------------------

        try:

            parsed_end = datetime.fromisoformat(
                end_text
            )

        except ValueError:

            parsed_end = None

        # ----------------------------------------------------
        # Natural time
        #
        # 10:00 AM
        # 10 AM
        # 14:30
        # 10:00
        # ----------------------------------------------------

        if parsed_end is None:

            time_formats = [
                "%I:%M %p",
                "%I %p",
                "%H:%M"
            ]

            for fmt in time_formats:

                try:

                    parsed_time = datetime.strptime(
                        end_text,
                        fmt
                    )

                    parsed_end = parsed_time

                    break

                except ValueError:

                    continue

        # ----------------------------------------------------
        # Combine time with the extracted date
        # ----------------------------------------------------

        if (
            parsed_end is not None
            and
            parsed_date is not None
        ):

            parsed_end = parsed_end.replace(
                year=target_year,
                month=parsed_date.month,
                day=parsed_date.day
            )

            result["end_datetime"] = (
                parsed_end.strftime(
                    "%Y-%m-%dT%H:%M:%S"
                )
            )

    return result


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
        r"\s*\(\s*requisition\s*(?:number\s*)?\d+\s*\)\s*$",
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
        r"\s*[-,]\s*requisition\s*(?:number\s*)?\d+\s*$",
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

    Supported responses:

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
            "message": (
                "The current task has been cancelled."
            )
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

        number = int(
            user_input
        )

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

                selected_title = requisition_data.get(
                    "Title"
                )

            if (
                not selected_requisition
                and isinstance(
                    requisition_data,
                    dict
                )
            ):

                selected_requisition = requisition_data.get(
                    "RequisitionNumber"
                )

            if (
                selected_title
                and
                selected_requisition
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
        # Direct requisition number
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
    #
    # Example:
    #
    # Site Engineer (Requisition 21)
    # ========================================================

    option_match = re.match(
        r"^\s*(.*?)\s*\(\s*requisition"
        r"(?:\s+number)?\s+(\d+)\s*\)\s*$",
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

                match_title = requisition_data.get(
                    "Title"
                )

            if (
                not match_requisition
                and isinstance(
                    requisition_data,
                    dict
                )
            ):

                match_requisition = requisition_data.get(
                    "RequisitionNumber"
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
        # Requisition not found
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
                "Please select a candidate by option number."
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
            "message": (
                "The current task has been cancelled."
            )
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
            1 <= option_number <= len(candidate_matches)
        ):

            selected = candidate_matches[
                option_number - 1
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
                        "The selected candidate could not "
                        "be recovered. Please choose another option."
                    )
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
                    "action": "CONFIRM",
                    "candidate_name": selected_candidate_name,
                    "interviewer_names": [],
                    "requisition_number": None,
                    "title_name": None,
                    "date": None,
                    "start_datetime": None,
                    "end_datetime": None,
                    "cancelled": False,
                    "message": ""
                }

        # ----------------------------------------------------
        # Invalid candidate option
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
            "action": "CONFIRM",
            "candidate_name": selected_candidate_name,
            "interviewer_names": [],
            "requisition_number": None,
            "title_name": None,
            "date": None,
            "start_datetime": None,
            "end_datetime": None,
            "cancelled": False,
            "message": ""
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
                "Multiple candidates have that name. "
                "Please select one:\n\n"
                +
                "\n".join(
                    options
                )
            )
        }

    # ========================================================
    # CANDIDATE NAME NOT FOUND
    # ========================================================

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
            f"I could not match '{user_input}' "
            "to the candidate options. "
            "Please select a candidate by option number."
        )
    }


# ============================================================
# HANDLE AVAILABILITY SLOT
# ============================================================

def _handle_availability_slot(
    previous_state,
    user_message
):
    """
    Handle continuation when the originally requested
    interview slot is unavailable.
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
            "confirmation_type": "availability_slot",
            "cancelled": False,
            "message": (
                "Please select a preferred time slot "
                "using its option number."
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
            "confirmation_type": "availability_slot",
            "message": (
                "The current interview scheduling task "
                "has been cancelled."
            )
        }

    # ========================================================
    # GET STORED COMMON SLOTS
    # ========================================================

    common_slots = previous_state.get(
        "common_slots",
        []
    )

    if not isinstance(
        common_slots,
        list
    ):

        common_slots = []

    # ========================================================
    # NO STORED SLOTS
    # ========================================================

    if not common_slots:

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
            "confirmation_type": "availability_slot",
            "message": (
                "There are no available interview slots "
                "stored for selection."
            )
        }

    # ========================================================
    # ACCEPT:
    #
    # 1
    # 2
    # 3
    #
    # OR:
    #
    # slot 1
    # slot 2
    # slot 3
    # ========================================================

    match = re.fullmatch(
        r"(?:slot\s*)?(\d+)",
        user_input,
        flags=re.IGNORECASE
    )

    if match:

        option_number = int(
            match.group(1)
        )

        # ----------------------------------------------------
        # VALID OPTION
        # ----------------------------------------------------

        if (
            1 <= option_number <= len(common_slots)
        ):

            selected_slot = common_slots[
                option_number - 1
            ]

            if not isinstance(
                selected_slot,
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
                    "confirmation_type": "availability_slot",
                    "message": (
                        "The selected time slot could not "
                        "be recovered. Please choose another slot."
                    )
                }

            selected_start = (
                selected_slot.get(
                    "startDateTime"
                )
            )

            selected_end = (
                selected_slot.get(
                    "endDateTime"
                )
            )

            # ------------------------------------------------
            # Lowercase fallback
            # ------------------------------------------------

            if not selected_start:

                selected_start = (
                    selected_slot.get(
                        "start_datetime"
                    )
                )

            if not selected_end:

                selected_end = (
                    selected_slot.get(
                        "end_datetime"
                    )
                )

            # ------------------------------------------------
            # Selected slot must have both times
            # ------------------------------------------------

            if (
                not selected_start
                or
                not selected_end
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
                    "confirmation_type": "availability_slot",
                    "message": (
                        "The selected slot does not contain "
                        "a valid start and end time. "
                        "Please choose another slot."
                    )
                }

            # ------------------------------------------------
            # SUCCESSFUL SELECTION
            # ------------------------------------------------

            return {
                "action": "CONFIRM",
                "candidate_name": None,
                "interviewer_names": [],
                "requisition_number": None,
                "title_name": None,
                "date": None,
                "start_datetime": selected_start,
                "end_datetime": selected_end,
                "cancelled": False,
                "confirmation_type": "availability_slot",
                "selected_slot": selected_slot,
                "selected_slot_index": option_number,
                "message": ""
            }

        # ----------------------------------------------------
        # INVALID OPTION NUMBER
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
            "confirmation_type": "availability_slot",
            "message": (
                f"That slot number is not valid. "
                f"Please select a slot between "
                f"1 and {len(common_slots)}."
            )
        }

    # ========================================================
    # USER DID NOT PROVIDE A SLOT NUMBER
    # ========================================================

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
        "confirmation_type": "availability_slot",
        "message": (
            "Please select a preferred time slot "
            "using its option number."
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
    # TITLE SELECTION / MULTIPLE TITLES
    #
    # IMPORTANT:
    #
    # Support BOTH:
    #
    #     confirmation_type = "title"
    #
    # and:
    #
    #     confirmation_type = "title_multiple"
    #
    # This is required because SEND_EMAIL can use "title".
    # ========================================================

    if (
        previous_state.get(
            "confirmation_type"
        )
        in [
            "title",
            "title_multiple"
        ]
    ):

        return _handle_title_multiple(
            previous_state,
            user_message
        )

    # ========================================================
    # MULTIPLE CANDIDATES
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
    # AVAILABILITY SLOT
    # ========================================================

    if (
        previous_state.get(
            "confirmation_type"
        )
        ==
        "availability_slot"
    ):

        return _handle_availability_slot(
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

15. When the user provides a date without a year,
    extract the month and day correctly.

    Python will determine the year after the response.

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
    # DEBUG: RAW LLM RESPONSE
    # ========================================================

    print(
        "\nRAW LLM CONVERSATION RESPONSE:"
    )

    print(
        content
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
            "action": "WAIT",
            "candidate_name": None,
            "interviewer_names": [],
            "requisition_number": None,
            "date": None,
            "start_datetime": None,
            "end_datetime": None,
            "cancelled": False,
            "message": (
                "I could not understand that response. "
                "Please clarify."
            )
        }

    # ========================================================
    # NORMALIZE DATE / DATETIME
    # ========================================================

    result = _normalize_datetime_result(
        user_message,
        result
    )

    # ========================================================
    # DEBUG: SHOW CORRECTED DATE/TIME
    # ========================================================

    print(
        "\nCORRECTED CONVERSATION DATE/TIME:"
    )

    print(
        json.dumps(
            {
                "date": result.get(
                    "date"
                ),
                "start_datetime": result.get(
                    "start_datetime"
                ),
                "end_datetime": result.get(
                    "end_datetime"
                )
            },
            indent=4,
            default=str
        )
    )

    # ========================================================
    # RETURN FINAL RESULT
    # ========================================================

    return result
