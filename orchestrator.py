# ============================================================
# orchestrator.py
# ============================================================

import json
from datetime import datetime

from agents import AGENTS
from oci_test import call_agent
from state import TaskState

from candidate_resolver import resolve_candidate
from interviewer_resolver import resolve_interviewers
from title_resolver import resolve_title


# ============================================================
# SAFE JSON PARSER
# ============================================================

def safe_json_loads(value):
    """
    Safely parse JSON returned by Oracle AI Agent.

    Handles:
        1. Normal JSON
        2. JSON with surrounding whitespace
        3. JSON followed by extra text
        4. JSON followed by another JSON object
        5. Already parsed dict/list values
    """

    if value is None:
        return None

    if isinstance(value, (dict, list)):
        return value

    if not isinstance(value, str):
        return value

    value = value.strip()

    if not value:
        return None

    try:
        return json.loads(value)

    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()

    try:
        parsed, end_index = decoder.raw_decode(value)

        extra_content = value[end_index:].strip()

        if extra_content:
            print(
                "\nWARNING: Extra data detected in Oracle Agent output."
            )

            print(
                "Ignored content:"
            )

            print(
                repr(extra_content)
            )

        return parsed

    except json.JSONDecodeError as e:

        print(
            "\nJSON PARSING FAILED"
        )

        print(
            "Error:",
            str(e)
        )

        print(
            "Raw value:"
        )

        print(
            repr(value)
        )

        return None


# ============================================================
# GENERAL HELPERS
# ============================================================

def print_agent_result(agent_name, result):

    print(
        "\n========================================"
    )

    print(
        f"{agent_name} RESULT"
    )

    print(
        "========================================"
    )

    print(
        json.dumps(
            result,
            indent=4,
            default=str
        )
    )


# ============================================================
# BUILD AGENT BODY
# ============================================================

def build_agent_body(agent_name, parameters):

    agent_config = AGENTS.get(
        agent_name
    )

    if agent_config is None:

        raise ValueError(
            f"Agent not found in agents.py: {agent_name}"
        )

    body_template = (
        agent_config
        .get("body", {})
        .get("parameters", {})
    )

    body = {
        "parameters": {}
    }

    for parameter_name, template_value in body_template.items():

        # ----------------------------------------------------
        # triggerType is always REST
        # ----------------------------------------------------

        if parameter_name == "triggerType":

            body["parameters"][parameter_name] = "REST"

            continue

        # ----------------------------------------------------
        # Dynamic value
        # ----------------------------------------------------

        if parameter_name in parameters:

            dynamic_value = parameters.get(
                parameter_name
            )

            if dynamic_value is not None:

                body["parameters"][parameter_name] = dynamic_value

                continue

        # ----------------------------------------------------
        # Template/default value
        # ----------------------------------------------------

        body["parameters"][parameter_name] = template_value

    # --------------------------------------------------------
    # Add parameters not present in template
    # --------------------------------------------------------

    for parameter_name, dynamic_value in parameters.items():

        if parameter_name not in body["parameters"]:

            if dynamic_value is not None:

                body["parameters"][parameter_name] = dynamic_value

    return body


# ============================================================
# NORMALIZE LIST
# ============================================================

def normalize_list(value):

    if value is None:
        return []

    if isinstance(value, str):

        value = value.strip()

        if not value:
            return []

        return [value]

    if isinstance(value, (list, tuple, set)):

        result = []

        for item in value:

            if item is None:
                continue

            item = str(item).strip()

            if item:
                result.append(item)

        return result

    return [
        str(value).strip()
    ]


# ============================================================
# VALIDATE INTERVIEW DATE/TIME
# ============================================================

def validate_interview_datetime(
    start_datetime,
    end_datetime
):

    if not start_datetime or not end_datetime:

        return {
            "valid": False,

            "message":
                "Interview start and end time are required."
        }

    try:

        start_dt = datetime.fromisoformat(
            start_datetime
        )

        end_dt = datetime.fromisoformat(
            end_datetime
        )

    except ValueError:

        return {
            "valid": False,

            "message":
                "The interview date/time format is invalid."
        }

    # --------------------------------------------------------
    # START MUST BE BEFORE END
    # --------------------------------------------------------

    if start_dt >= end_dt:

        return {
            "valid": False,

            "message":
                (
                    "The interview start time must be "
                    "before the end time."
                )
        }

    # --------------------------------------------------------
    # CURRENT TIME
    # --------------------------------------------------------

    if start_dt.tzinfo:

        now = datetime.now(
            tz=start_dt.tzinfo
        )

    else:

        now = datetime.now()

    # --------------------------------------------------------
    # CHECK PAST TIME
    # --------------------------------------------------------

    if start_dt < now:

        return {
            "valid": False,

            "message":
                (
                    f"The requested interview time "
                    f"{start_datetime} to {end_datetime} "
                    f"has already passed. "
                    f"Please provide a future date and time."
                )
        }

    return {
        "valid": True
    }


# ============================================================
# UNWRAP AGENT OUTPUT
# ============================================================

def unwrap_agent_output(agent_result):

    if not isinstance(
        agent_result,
        dict
    ):

        return agent_result

    output = agent_result.get(
        "output"
    )

    if output is None:
        return agent_result

    if isinstance(output, str):

        parsed = safe_json_loads(
            output
        )

        if parsed is not None:
            return parsed

        return output

    return output


# ============================================================
# EXTRACT ALL INTERVIEWERS
# ============================================================

def extract_all_interviewers(
    interviewer_result
):

    matches = []

    try:

        output = (
            interviewer_result.get("output")
            if isinstance(
                interviewer_result,
                dict
            )
            else None
        )

        if not output:
            return matches

        # ----------------------------------------------------
        # Parse Oracle string output
        # ----------------------------------------------------

        if isinstance(
            output,
            str
        ):

            output = safe_json_loads(
                output
            )

            if output is None:
                return matches

        if not isinstance(
            output,
            dict
        ):

            return matches

        # ----------------------------------------------------
        # Standard format
        # ----------------------------------------------------

        result = output.get(
            "result",
            []
        )

        # ----------------------------------------------------
        # Sometimes result is JSON string
        # ----------------------------------------------------

        if isinstance(
            result,
            str
        ):

            result = safe_json_loads(
                result
            )

            if result is None:
                return matches

        if isinstance(
            result,
            dict
        ):

            result = result.get(
                "result",
                result.get(
                    "interviewers",
                    []
                )
            )

        if not isinstance(
            result,
            list
        ):

            return matches

        # ----------------------------------------------------
        # Extract interviewer information
        # ----------------------------------------------------

        for interviewer in result:

            if not isinstance(
                interviewer,
                dict
            ):

                continue

            name = (
                interviewer.get("DisplayName")
                or interviewer.get("displayName")
                or interviewer.get("Name")
                or interviewer.get("name")
            )

            email = (
                interviewer.get("WorkEmail")
                or interviewer.get("workEmail")
                or interviewer.get("Email")
                or interviewer.get("email")
            )

            if not name:
                continue

            matches.append(
                {
                    "actual_name":
                        str(name).strip(),

                    "email":
                        str(email).strip()
                        if email
                        else None
                }
            )

        return matches

    except Exception as e:

        print(
            f"Error extracting interviewers: {str(e)}"
        )

        return []


# ============================================================
# INTERVIEWER LIST FLOW
# ============================================================

def interviewer_list_flow(
    state: TaskState
):

    print(
        "\n========================================"
    )

    print(
        "START INTERVIEWER LIST FLOW"
    )

    print(
        "========================================"
    )

    requisition_number = state.get(
        "requisition_number"
    )

    if not requisition_number:

        return {
            "waiting_for_user": True,

            "missing_information":
                ["requisition_number"],

            "result_summary":
                "Please provide the requisition number."
        }

    # ========================================================
    # CALL INTERVIEWERDATA
    # ========================================================

    interviewer_body = build_agent_body(
        "INTERVIEWERDATA",
        {
            "RequisitionNumber":
                requisition_number
        }
    )

    print(
        "\nCalling INTERVIEWERDATA..."
    )

    try:

        interviewer_result = call_agent(
            "INTERVIEWERDATA",
            interviewer_body
        )

    except Exception as e:

        return {
            "waiting_for_user": False,

            "interviewer_result": None,

            "result_summary":
                (
                    f"Unable to retrieve interviewers: "
                    f"{str(e)}"
                )
        }

    print_agent_result(
        "INTERVIEWERDATA",
        interviewer_result
    )

    # ========================================================
    # EXTRACT INTERVIEWERS
    # ========================================================

    interviewers = extract_all_interviewers(
        interviewer_result
    )

    if not interviewers:

        return {
            "interviewer_result":
                interviewer_result,

            "requested_interviewers":
                [],

            "interviewer_emails":
                [],

            "waiting_for_user":
                False,

            "awaiting_confirmation":
                False,

            "result_summary":
                (
                    f"No interviewers were found for "
                    f"requisition {requisition_number}."
                )
        }

    # ========================================================
    # BUILD RESPONSE
    # ========================================================

    interviewer_text = []

    for interviewer in interviewers:

        name = interviewer.get(
            "actual_name"
        )

        email = interviewer.get(
            "email"
        )

        if email:

            interviewer_text.append(
                f"- {name} ({email})"
            )

        else:

            interviewer_text.append(
                f"- {name}"
            )

    return {
        "interviewer_result":
            interviewer_result,

        "requested_interviewers":
            [
                item.get("actual_name")
                for item in interviewers
                if item.get("actual_name")
            ],

        "interviewer_emails":
            [
                item.get("email")
                for item in interviewers
                if item.get("email")
            ],

        "waiting_for_user":
            False,

        "awaiting_confirmation":
            False,

        "result_summary":
            (
                f"Interviewers for requisition "
                f"{requisition_number}:\n"
                +
                "\n".join(
                    interviewer_text
                )
            )
    }


# ============================================================
# EXTRACT COMMON SLOTS
# ============================================================

def extract_common_slots(
    agent_result
):

    data = unwrap_agent_output(
        agent_result
    )

    if isinstance(
        data,
        dict
    ):

        slots = (
            data.get("commonSlots")
            or data.get("common_slots")
            or data.get("meetingTimeSuggestions")
        )

        if isinstance(
            slots,
            str
        ):

            slots = safe_json_loads(
                slots
            )

        if isinstance(
            slots,
            list
        ):

            return slots

        # ----------------------------------------------------
        # Nested result
        # ----------------------------------------------------

        result = data.get(
            "result"
        )

        if isinstance(
            result,
            str
        ):

            result = safe_json_loads(
                result
            )

        if isinstance(
            result,
            dict
        ):

            slots = (
                result.get("commonSlots")
                or result.get("common_slots")
                or result.get("meetingTimeSuggestions")
                or []
            )

            if isinstance(
                slots,
                list
            ):

                return slots

    return []


# ============================================================
# AVAILABILITY FLOW
# ============================================================

def availability_flow(
    state: TaskState
):

    print(
        "\n========================================"
    )

    print(
        "START AVAILABILITY FLOW"
    )

    print(
        "========================================"
    )

    interviewer_names = normalize_list(
        state.get(
            "interviewer_names",
            []
        )
    )

    requisition_number = state.get(
        "requisition_number"
    )

    date = state.get(
        "date"
    )

    # ========================================================
    # REQUIRED DATA
    # ========================================================

    missing = []

    if not requisition_number:
        missing.append(
            "requisition_number"
        )

    if not date:
        missing.append(
            "date"
        )

    if missing:

        return {
            "waiting_for_user": True,

            "missing_information":
                missing,

            "result_summary":
                (
                    "Please provide the requisition "
                    "number and date."
                )
        }

    # ========================================================
    # INTERVIEWERDATA
    # ========================================================

    interviewer_body = build_agent_body(
        "INTERVIEWERDATA",
        {
            "RequisitionNumber":
                requisition_number
        }
    )

    print(
        "\nCalling INTERVIEWERDATA..."
    )

    try:

        interviewer_result = call_agent(
            "INTERVIEWERDATA",
            interviewer_body
        )

    except Exception as e:

        return {
            "waiting_for_user":
                False,

            "result_summary":
                (
                    f"Unable to retrieve interviewer "
                    f"data: {str(e)}"
                )
        }

    print_agent_result(
        "INTERVIEWERDATA",
        interviewer_result
    )

    # ========================================================
    # RESOLVE USER-SPECIFIED INTERVIEWERS
    # ========================================================

    if interviewer_names:

        interviewer_match = resolve_interviewers(
            interviewer_result,
            interviewer_names
        )

        print(
            "\nINTERVIEWER MATCH RESULT:"
        )

        print(
            json.dumps(
                interviewer_match,
                indent=4,
                default=str
            )
        )

        status = interviewer_match.get(
            "status"
        )

        # ----------------------------------------------------
        # NOT FOUND
        # ----------------------------------------------------

        if status == "NOT_FOUND":

            not_found = interviewer_match.get(
                "not_found",
                interviewer_names
            )

            return {
                "interviewer_result":
                    interviewer_result,

                "requested_interviewers":
                    interviewer_names,

                "interviewer_emails":
                    [],

                "waiting_for_user":
                    True,

                "awaiting_confirmation":
                    False,

                "confirmation_type":
                    "interviewer",

                "original_interviewer_input":
                    interviewer_names,

                "result_summary":
                    (
                        "I could not find the following "
                        "interviewer(s): "
                        +
                        ", ".join(
                            not_found
                        )
                    )
            }

        # ----------------------------------------------------
        # SUGGESTION
        # ----------------------------------------------------

        if status == "SUGGEST":

            suggestions = interviewer_match.get(
                "suggestions",
                []
            )

            suggested_names = []

            for suggestion in suggestions:

                if not isinstance(
                    suggestion,
                    dict
                ):

                    continue

                actual_name = (
                    suggestion.get("actual_name")
                    or suggestion.get("name")
                    or suggestion.get("DisplayName")
                )

                if (
                    actual_name
                    and
                    actual_name not in suggested_names
                ):

                    suggested_names.append(
                        actual_name
                    )

            if not suggested_names:

                return {
                    "interviewer_result":
                        interviewer_result,

                    "requested_interviewers":
                        interviewer_names,

                    "waiting_for_user":
                        True,

                    "awaiting_confirmation":
                        False,

                    "confirmation_type":
                        "interviewer",

                    "original_interviewer_input":
                        interviewer_names,

                    "requisition_number":
                        requisition_number,

                    "date":
                        date,

                    "result_summary":
                        (
                            "I could not find an interviewer "
                            "matching "
                            +
                            ", ".join(
                                interviewer_names
                            )
                        )
                }

            # ------------------------------------------------
            # Single suggestion
            # ------------------------------------------------

            if len(
                suggested_names
            ) == 1:

                suggested_name = suggested_names[0]

                return {
                    "interviewer_result":
                        interviewer_result,

                    "requested_interviewers":
                        interviewer_names,

                    "waiting_for_user":
                        True,

                    "awaiting_confirmation":
                        True,

                    "confirmation_type":
                        "interviewer",

                    "original_interviewer_input":
                        interviewer_names,

                    "suggested_interviewer":
                        suggested_name,

                    "suggested_interviewers":
                        suggested_names,

                    "requisition_number":
                        requisition_number,

                    "interviewer_names":
                        interviewer_names,

                    "date":
                        date,

                    "result_summary":
                        (
                            f"I couldn't find an exact "
                            f"match for "
                            f"'{', '.join(interviewer_names)}'. "
                            f"Did you mean "
                            f"'{suggested_name}'?"
                        )
                }

            # ------------------------------------------------
            # Multiple suggestions
            # ------------------------------------------------

            options_text = "\n".join(
                f"{index + 1}. {name}"
                for index, name
                in enumerate(
                    suggested_names
                )
            )

            return {
                "interviewer_result":
                    interviewer_result,

                "requested_interviewers":
                    interviewer_names,

                "waiting_for_user":
                    True,

                "awaiting_confirmation":
                    True,

                "confirmation_type":
                    "interviewer",

                "original_interviewer_input":
                    interviewer_names,

                "suggested_interviewers":
                    suggested_names,

                "requisition_number":
                    requisition_number,

                "interviewer_names":
                    interviewer_names,

                "date":
                    date,

                "result_summary":
                    (
                        f"I found multiple interviewers "
                        f"matching "
                        f"'{', '.join(interviewer_names)}'. "
                        f"Please select one:\n\n"
                        f"{options_text}"
                    )
            }

        matches = interviewer_match.get(
            "matches",
            []
        )

    else:

        # ====================================================
        # NO INTERVIEWER SPECIFIED
        # Use ALL interviewers
        # ====================================================

        matches = extract_all_interviewers(
            interviewer_result
        )

        if not matches:

            return {
                "interviewer_result":
                    interviewer_result,

                "requested_interviewers":
                    [],

                "interviewer_emails":
                    [],

                "waiting_for_user":
                    False,

                "result_summary":
                    (
                        "No interviewers were found for "
                        f"requisition {requisition_number}."
                    )
            }

    # ========================================================
    # CANONICAL NAMES
    # ========================================================

    canonical_names = []

    for item in matches:

        if not isinstance(
            item,
            dict
        ):

            continue

        name = item.get(
            "actual_name"
        )

        if (
            name
            and
            name not in canonical_names
        ):

            canonical_names.append(
                name
            )

    # ========================================================
    # EMAILS
    # ========================================================

    interviewer_emails = []

    for item in matches:

        if not isinstance(
            item,
            dict
        ):

            continue

        email = item.get(
            "email"
        )

        if (
            email
            and
            email not in interviewer_emails
        ):

            interviewer_emails.append(
                email
            )

    if not interviewer_emails:

        return {
            "interviewer_result":
                interviewer_result,

            "requested_interviewers":
                canonical_names,

            "interviewer_emails":
                [],

            "waiting_for_user":
                False,

            "result_summary":
                (
                    "No email addresses were found "
                    "for the interviewers."
                )
        }

    # ========================================================
    # AVAILABILITY AGENT
    # ========================================================

    availability_parameters = {
        "interviewer_emails":
            interviewer_emails,

        "date":
            date,

        "meeting_duration_minutes":
            30
    }

    availability_body = build_agent_body(
        "INTERVIEWER_AVAILABILITY",
        availability_parameters
    )

    print(
        "\nCalling INTERVIEWER_AVAILABILITY..."
    )

    print(
        json.dumps(
            availability_body,
            indent=4,
            default=str
        )
    )

    try:

        availability_result = call_agent(
            "INTERVIEWER_AVAILABILITY",
            availability_body
        )

    except Exception as e:

        return {
            "interviewer_result":
                interviewer_result,

            "interviewer_names":
                canonical_names,

            "interviewer_emails":
                interviewer_emails,

            "availability_result":
                None,

            "waiting_for_user":
                False,

            "result_summary":
                (
                    "Interviewer availability check "
                    f"failed: {str(e)}"
                )
        }

    print_agent_result(
        "INTERVIEWER_AVAILABILITY",
        availability_result
    )

    # ========================================================
    # COMMON SLOTS
    # ========================================================

    common_slots = extract_common_slots(
        availability_result
    )

    if not common_slots:

        return {
            "interviewer_result":
                interviewer_result,

            "requested_interviewers":
                canonical_names,

            "interviewer_emails":
                interviewer_emails,

            "availability_result":
                availability_result,

            "common_slots":
                [],

            "waiting_for_user":
                False,

            "result_summary":
                (
                    "No common free time was found for "
                    f"the interviewer(s) on {date}."
                )
        }

    return {
        "interviewer_result":
            interviewer_result,

        "requested_interviewers":
            canonical_names,

        "interviewer_emails":
            interviewer_emails,

        "availability_result":
            availability_result,

        "common_slots":
            common_slots,

        "waiting_for_user":
            False,

        "awaiting_confirmation":
            False,

        "result_summary":
            (
                f"Available common slots found for "
                f"{date}."
            )
    }


# ============================================================
# CHECK REQUESTED SLOT
# ============================================================

def is_requested_slot_available(
    availability_result,
    requested_start,
    requested_end
):

    try:

        data = unwrap_agent_output(
            availability_result
        )

        if not isinstance(
            data,
            dict
        ):

            return False

        # ----------------------------------------------------
        # Find common slots
        # ----------------------------------------------------

        common_slots = (
            data.get("commonSlots")
            or data.get("common_slots")
        )

        if common_slots is None:

            result = data.get(
                "result"
            )

            if isinstance(
                result,
                str
            ):

                result = safe_json_loads(
                    result
                )

            if isinstance(
                result,
                dict
            ):

                common_slots = (
                    result.get("commonSlots")
                    or result.get("common_slots")
                )

        if not isinstance(
            common_slots,
            list
        ):

            return False

        requested_start_dt = datetime.fromisoformat(
            normalize_datetime_string(
                requested_start
            )
        )

        requested_end_dt = datetime.fromisoformat(
            normalize_datetime_string(
                requested_end
            )
        )

        # ----------------------------------------------------
        # Compare requested slot
        # ----------------------------------------------------

        for slot in common_slots:

            if not isinstance(
                slot,
                dict
            ):

                continue

            slot_start = (
                slot.get("startDateTime")
                or slot.get("start_datetime")
            )

            slot_end = (
                slot.get("endDateTime")
                or slot.get("end_datetime")
            )

            if not slot_start or not slot_end:
                continue

            slot_start_dt = datetime.fromisoformat(
                normalize_datetime_string(
                    slot_start
                )
            )

            slot_end_dt = datetime.fromisoformat(
                normalize_datetime_string(
                    slot_end
                )
            )

            # ------------------------------------------------
            # Exact match
            # ------------------------------------------------

            if (
                slot_start_dt == requested_start_dt
                and
                slot_end_dt == requested_end_dt
            ):

                print(
                    "\nREQUESTED SLOT IS AVAILABLE"
                )

                print(
                    "Requested:",
                    requested_start,
                    "to",
                    requested_end
                )

                print(
                    "Matched:",
                    slot_start,
                    "to",
                    slot_end
                )

                return True

            # ------------------------------------------------
            # Requested slot fits inside larger slot
            # ------------------------------------------------

            if (
                slot_start_dt <= requested_start_dt
                and
                slot_end_dt >= requested_end_dt
            ):

                print(
                    "\nREQUESTED SLOT FITS INSIDE AVAILABLE SLOT"
                )

                print(
                    "Available:",
                    slot_start,
                    "to",
                    slot_end
                )

                print(
                    "Requested:",
                    requested_start,
                    "to",
                    requested_end
                )

                return True

        print(
            "\nREQUESTED SLOT IS NOT AVAILABLE"
        )

        return False

    except Exception as e:

        print(
            "\nERROR CHECKING REQUESTED SLOT:"
        )

        print(
            str(e)
        )

        return False


# ============================================================
# NORMALIZE DATETIME STRING
# ============================================================

def normalize_datetime_string(
    value
):

    if not isinstance(
        value,
        str
    ):

        return value

    value = value.strip()

    try:

        parsed = datetime.fromisoformat(
            value
        )

        return parsed.isoformat()

    except ValueError:

        return value


# ============================================================
# SCHEDULING FLOW
# ============================================================

def scheduling_flow(
    state: TaskState
):

    print(
        "\n========================================"
    )

    print(
        "START SCHEDULING FLOW"
    )

    print(
        "========================================"
    )

    # ========================================================
    # GET STATE VALUES
    # ========================================================

    candidate_name = state.get(
        "candidate_name"
    )

    # --------------------------------------------------------
    # Requisition number may be directly provided
    # --------------------------------------------------------

    requisition_number = state.get(
        "requisition_number"
    )

    # --------------------------------------------------------
    # IMPORTANT FIX:
    #
    # Read TITLE from title_name.
    #
    # Previously this incorrectly used:
    #
    # state.get("interviewer_names", [])
    #
    # That caused:
    #
    # interviewer = "Wood Charles"
    #
    # to become:
    #
    # title_name = "Wood Charles"
    # --------------------------------------------------------

    title_name = normalize_list(
        state.get(
            "title_name",
            []
        )
    )

    # --------------------------------------------------------
    # The JOB_REQUISITIONS agent expects one title string.
    #
    # Keep title_name as a list in state if your TaskState
    # defines it that way, but use title_query when calling
    # the title resolver / Oracle agent.
    # --------------------------------------------------------

    title_query = (
        title_name[0]
        if title_name
        else None
    )

    # --------------------------------------------------------
    # Normalize interviewer names separately
    # --------------------------------------------------------

    interviewer_names = normalize_list(
        state.get(
            "interviewer_names",
            []
        )
    )

    start_datetime = state.get(
        "start_datetime"
    )

    end_datetime = state.get(
        "end_datetime"
    )

    subject = state.get(
        "subject"
    ) or "Java Interview"

    print(
        "\nSCHEDULING INPUT:"
    )

    print(
        json.dumps(
            {
                "candidate_name":
                    candidate_name,

                "requisition_number":
                    requisition_number,

                "title_name":
                    title_name,

                "title_query":
                    title_query,

                "interviewer_names":
                    interviewer_names,

                "start_datetime":
                    start_datetime,

                "end_datetime":
                    end_datetime,

                "subject":
                    subject
            },
            indent=4,
            default=str
        )
    )

    # ========================================================
    # BASIC VALIDATION
    # ========================================================

    if not candidate_name:

        return {
            "waiting_for_user":
                True,

            "missing_information":
                [
                    "candidate_name"
                ],

            "final_response":
                "Candidate name is required."
        }

    # ========================================================
    # INTERVIEWER VALIDATION
    # ========================================================

    if not interviewer_names:

        return {
            "waiting_for_user":
                True,

            "missing_information":
                [
                    "interviewer_name"
                ],

            "title_name":
                title_name,

            "result_summary":
                (
                    "Which interviewer would you like "
                    "to schedule with?"
                )
        }

    # ========================================================
    # DATE/TIME VALIDATION
    # ========================================================

    if not start_datetime or not end_datetime:

        return {
            "waiting_for_user":
                True,

            "missing_information":
                [
                    "start_datetime",
                    "end_datetime"
                ],

            "candidate_name":
                candidate_name,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "interviewer_names":
                interviewer_names,

            "subject":
                subject,

            "final_response":
                "Please provide the interview date and time."
        }

    # ========================================================
    # VALIDATE FUTURE DATE/TIME
    # ========================================================

    datetime_validation = validate_interview_datetime(
        start_datetime,
        end_datetime
    )

    if not datetime_validation["valid"]:

        return {
            "waiting_for_user":
                True,

            "missing_information":
                [
                    "future_interview_datetime"
                ],

            "candidate_name":
                candidate_name,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "interviewer_names":
                interviewer_names,

            "start_datetime":
                start_datetime,

            "end_datetime":
                end_datetime,

            "subject":
                subject,

            "final_response":
                datetime_validation["message"]
        }

        # ========================================================
    # REQUISITION RESOLUTION
    #
    # CASE 1:
    # User provided requisition number
    #
    #     -> DO NOT CALL JOB_REQUISITIONS
    #
    # CASE 2:
    # User provided title
    #
    #     -> CALL JOB_REQUISITIONS
    #     -> Resolve title
    #     -> Get requisition number
    # ========================================================

    if not requisition_number:

        # ----------------------------------------------------
        # No requisition number AND no title
        # ----------------------------------------------------

        if not title_query:

            return {
                "waiting_for_user":
                    True,

                "missing_information":
                    [
                        "requisition_number_or_title"
                    ],

                "candidate_name":
                    candidate_name,

                "interviewer_names":
                    interviewer_names,

                "start_datetime":
                    start_datetime,

                "end_datetime":
                    end_datetime,

                "subject":
                    subject,

                "final_response":
                    (
                        "Please provide either the requisition "
                        "number or the job title."
                    )
            }

        # ====================================================
        # JOB_REQUISITIONS
        # ====================================================

        # IMPORTANT:
        # Send STRING, not ["Site Engineer"]

        title_parameters = {
            "UserInput":
                title_query
        }

        title_body = build_agent_body(
            "JOB_REQUISITIONS",
            title_parameters
        )

        print(
            "\nCalling JOB_REQUISITIONS..."
        )

        print(
            "\nJOB_REQUISITIONS BODY:"
        )

        print(
            json.dumps(
                title_body,
                indent=4,
                default=str
            )
        )

        try:

            title_result = call_agent(
                "JOB_REQUISITIONS",
                title_body
            )

        except Exception as e:

            return {
                "waiting_for_user":
                    False,

                "title_name":
                    title_name,

                "candidate_name":
                    candidate_name,

                "interviewer_names":
                    interviewer_names,

                "result_summary":
                    (
                        "Job requisition lookup failed: "
                        f"{str(e)}"
                    )
            }

        print_agent_result(
            "JOB_REQUISITIONS",
            title_result
        )

        # ====================================================
        # RESOLVE TITLE
        # ====================================================

        title_match = resolve_title(
            title_result,
            title_query
        )

        print(
            "\nTITLE RESOLUTION:"
        )

        print(
            json.dumps(
                title_match,
                indent=4,
                default=str
            )
        )

        # ====================================================
        # TITLE RESULT VALIDATION
        # ====================================================

        if not title_match:

            return {
                "waiting_for_user":
                    True,

                "title_name":
                    title_name,

                "candidate_name":
                    candidate_name,

                "interviewer_names":
                    interviewer_names,

                "start_datetime":
                    start_datetime,

                "end_datetime":
                    end_datetime,

                "subject":
                    subject,

                "final_response":
                    (
                        f"I could not find a job requisition "
                        f"matching '{title_query}'. "
                        "Please provide another job title."
                    )
            }

        title_status = title_match.get(
            "status"
        )

        # ====================================================
        # TITLE NOT FOUND
        # ====================================================

        if title_status == "NOT_FOUND":

            return {
                "waiting_for_user":
                    True,

                "awaiting_confirmation":
                    False,

                "confirmation_type":
                    "title",

                "original_title_input":
                    title_name,

                "candidate_name":
                    candidate_name,

                "title_name":
                    title_name,

                "requisition_number":
                    None,

                "interviewer_names":
                    interviewer_names,

                "start_datetime":
                    start_datetime,

                "end_datetime":
                    end_datetime,

                "subject":
                    subject,

                "final_response":
                    (
                        f"I could not resolve the job title "
                        f"'{title_query}'. "
                        "Please provide another job title."
                    )
            }

        # ====================================================
        # TITLE SUGGESTION
        #
        # Example:
        #
        # Site Enginner
        #     ->
        # Site Engineer
        # ====================================================

        if title_status == "SUGGEST":

            suggested_titles = []

            # ------------------------------------------------
            # suggested_titles
            # ------------------------------------------------

            raw_suggestions = title_match.get(
                "suggested_titles",
                []
            )

            if isinstance(
                raw_suggestions,
                list
            ):

                for suggestion in raw_suggestions:

                    if isinstance(
                        suggestion,
                        str
                    ):

                        value = suggestion.strip()

                    elif isinstance(
                        suggestion,
                        dict
                    ):

                        value = (
                            suggestion.get(
                                "title"
                            )
                            or
                            suggestion.get(
                                "Title"
                            )
                            or
                            suggestion.get(
                                "matched_title"
                            )
                            or
                            suggestion.get(
                                "suggested_title"
                            )
                        )

                        if value:
                            value = str(
                                value
                            ).strip()

                    else:

                        value = None

                    if (
                        value
                        and
                        value not in suggested_titles
                    ):

                        suggested_titles.append(
                            value
                        )

            # ------------------------------------------------
            # Single suggestion fallback
            # ------------------------------------------------

            suggested_title = title_match.get(
                "suggested_title"
            )

            if suggested_title:

                suggested_title = str(
                    suggested_title
                ).strip()

                if (
                    suggested_title
                    and
                    suggested_title
                    not in suggested_titles
                ):

                    suggested_titles.append(
                        suggested_title
                    )

            # ------------------------------------------------
            # suggestions fallback
            # ------------------------------------------------

            suggestions = title_match.get(
                "suggestions",
                []
            )

            if isinstance(
                suggestions,
                list
            ):

                for suggestion in suggestions:

                    if isinstance(
                        suggestion,
                        str
                    ):

                        value = suggestion.strip()

                    elif isinstance(
                        suggestion,
                        dict
                    ):

                        value = (
                            suggestion.get(
                                "title"
                            )
                            or
                            suggestion.get(
                                "Title"
                            )
                            or
                            suggestion.get(
                                "matched_title"
                            )
                            or
                            suggestion.get(
                                "suggested_title"
                            )
                        )

                        if value:
                            value = str(
                                value
                            ).strip()

                    else:

                        value = None

                    if (
                        value
                        and
                        value not in suggested_titles
                    ):

                        suggested_titles.append(
                            value
                        )

            # ------------------------------------------------
            # No suggestion
            # ------------------------------------------------

            if not suggested_titles:

                return {
                    "waiting_for_user":
                        True,

                    "awaiting_confirmation":
                        False,

                    "confirmation_type":
                        "title",

                    "original_title_input":
                        title_name,

                    "candidate_name":
                        candidate_name,

                    "title_name":
                        title_name,

                    "requisition_number":
                        None,

                    "interviewer_names":
                        interviewer_names,

                    "start_datetime":
                        start_datetime,

                    "end_datetime":
                        end_datetime,

                    "subject":
                        subject,

                    "final_response":
                        (
                            f"I could not resolve the job title "
                            f"'{title_query}'. "
                            "Please provide another job title."
                        )
                }

            # ------------------------------------------------
            # Single suggestion
            # ------------------------------------------------

            if len(
                suggested_titles
            ) == 1:

                suggested_title = (
                    suggested_titles[0]
                )

                suggested_requisition_number = (
                    title_match.get(
                        "requisition_number"
                    )
                )

                return {
                    "waiting_for_user":
                        True,

                    "awaiting_confirmation":
                        True,

                    "confirmation_type":
                        "title",

                    "original_title_input":
                        title_name,

                    "suggested_title":
                        suggested_title,

                    "suggested_titles":
                        suggested_titles,

                    "suggested_requisition_number":
                        suggested_requisition_number,

                    "candidate_name":
                        candidate_name,

                    "title_name":
                        title_name,

                    "requisition_number":
                        None,

                    "interviewer_names":
                        interviewer_names,

                    "start_datetime":
                        start_datetime,

                    "end_datetime":
                        end_datetime,

                    "subject":
                        subject,

                    "final_response":
                        (
                            f"I couldn't find an exact match "
                            f"for '{title_query}'. "
                            f"Did you mean "
                            f"'{suggested_title}'?"
                        )
                }

            # ------------------------------------------------
            # Multiple title suggestions
            # ------------------------------------------------

            options_text = "\n".join(
                f"{index + 1}. {title}"
                for index, title
                in enumerate(
                    suggested_titles
                )
            )

            return {
                "waiting_for_user":
                    True,

                "awaiting_confirmation":
                    True,

                "confirmation_type":
                    "title",

                "original_title_input":
                    title_name,

                "suggested_titles":
                    suggested_titles,

                "candidate_name":
                    candidate_name,

                "title_name":
                    title_name,

                "requisition_number":
                    None,

                "interviewer_names":
                    interviewer_names,

                "start_datetime":
                    start_datetime,

                "end_datetime":
                    end_datetime,

                "subject":
                    subject,

                "result_summary":
                    (
                        f"I found multiple job titles "
                        f"matching '{title_query}'. "
                        f"Please select one:\n\n"
                        f"{options_text}"
                    ),

                "final_response":
                    (
                        f"I found multiple job titles "
                        f"matching '{title_query}'. "
                        f"Please select one:\n\n"
                        f"{options_text}"
                    )
            }

        # ====================================================
        # MULTIPLE TITLE MATCH
        #
        # THIS IS THE IMPORTANT NEW PART
        #
        # Example:
        #
        # Site Engine
        #
        # 1. Site Engineer - Requisition 21
        # 2. Site Engineer - Requisition 102
        # 3. Site Engineer (Trainee) - Requisition 44
        # 4. Senior Site Engineer - Requisition 94
        # ====================================================

        if title_status == "MULTIPLE":

            matches = title_match.get(
                "matches",
                []
            )

            valid_matches = []

            if isinstance(
                matches,
                list
            ):

                for match in matches:

                    if not isinstance(
                        match,
                        dict
                    ):
                        continue

                    matched_title = (
                        match.get(
                            "title"
                        )
                        or
                        match.get(
                            "Title"
                        )
                        or
                        match.get(
                            "matched_title"
                        )
                    )

                    requisition_number_match = (
                        match.get(
                            "requisition_number"
                        )
                        or
                        match.get(
                            "RequisitionNumber"
                        )
                    )

                    if not matched_title:
                        continue

                    matched_title = str(
                        matched_title
                    ).strip()

                    if (
                        requisition_number_match
                        is not None
                    ):

                        requisition_number_match = str(
                            requisition_number_match
                        ).strip()

                    valid_matches.append(
                        {
                            "title":
                                matched_title,

                            "requisition_number":
                                requisition_number_match,

                            "score":
                                match.get(
                                    "score",
                                    0.0
                                ),

                            "match_type":
                                match.get(
                                    "match_type"
                                ),

                            "requisition":
                                match.get(
                                    "requisition"
                                )
                        }
                    )

            # ------------------------------------------------
            # No valid matches
            # ------------------------------------------------

            if not valid_matches:

                return {
                    "waiting_for_user":
                        True,

                    "awaiting_confirmation":
                        False,

                    "confirmation_type":
                        "title",

                    "original_title_input":
                        title_name,

                    "candidate_name":
                        candidate_name,

                    "title_name":
                        title_name,

                    "requisition_number":
                        None,

                    "interviewer_names":
                        interviewer_names,

                    "start_datetime":
                        start_datetime,

                    "end_datetime":
                        end_datetime,

                    "subject":
                        subject,

                    "final_response":
                        (
                            f"I could not resolve the job title "
                            f"'{title_query}'. "
                            "Please provide another job title."
                        )
                }

            # ------------------------------------------------
            # Build options for user
            # ------------------------------------------------

            options = []

            for index, match in enumerate(
                valid_matches,
                start=1
            ):

                matched_title = match.get(
                    "title"
                )

                requisition_number_match = (
                    match.get(
                        "requisition_number"
                    )
                )

                if requisition_number_match:

                    option_text = (
                        f"{index}. "
                        f"{matched_title} "
                        f"(Requisition "
                        f"{requisition_number_match})"
                    )

                else:

                    option_text = (
                        f"{index}. "
                        f"{matched_title}"
                    )

                options.append(
                    option_text
                )

            options_text = "\n".join(
                options
            )

            # ------------------------------------------------
            # IMPORTANT:
            #
            # We store title_matches so conversation.py
            # can later resolve:
            #
            # "1"
            # "2"
            # "44"
            # "102"
            #
            # without losing the original scheduling data.
            # ------------------------------------------------

            return {
                "waiting_for_user":
                    True,

                "awaiting_confirmation":
                    True,

                "confirmation_type":
                    "title_multiple",

                "original_title_input":
                    title_name,

                "requested_title":
                    title_query,

                "title_matches":
                    valid_matches,

                "suggested_titles":
                    [
                        match.get(
                            "title"
                        )
                        for match
                        in valid_matches
                    ],

                "candidate_name":
                    candidate_name,

                "title_name":
                    title_name,

                "requisition_number":
                    None,

                "interviewer_names":
                    interviewer_names,

                "start_datetime":
                    start_datetime,

                "end_datetime":
                    end_datetime,

                "subject":
                    subject,

                "result_summary":
                    (
                        f"I found multiple job titles "
                        f"matching '{title_query}'. "
                        f"Please select one:\n\n"
                        f"{options_text}\n\n"
                        "You can reply with the option number "
                        "or the requisition number."
                    ),

                "final_response":
                    (
                        f"I found multiple job titles "
                        f"matching '{title_query}'. "
                        f"Please select one:\n\n"
                        f"{options_text}\n\n"
                        "You can reply with the option number "
                        "or the requisition number."
                    )
            }

        # ====================================================
        # EXACT TITLE MATCH
        # ====================================================

        if title_status == "EXACT":

            matched_title = title_match.get(
                "matched_title"
            )

            requisition_number = (
                title_match.get(
                    "requisition_number"
                )
            )

            if not requisition_number:

                return {
                    "waiting_for_user":
                        False,

                    "candidate_name":
                        candidate_name,

                    "title_name":
                        (
                            [matched_title]
                            if matched_title
                            else title_name
                        ),

                    "interviewer_names":
                        interviewer_names,

                    "final_response":
                        (
                            f"The job title "
                            f"'{matched_title or title_query}' "
                            "was found, but its requisition number "
                            "could not be determined."
                        )
                }

            # ------------------------------------------------
            # Store canonical title as list
            # ------------------------------------------------

            if matched_title:

                title_name = [
                    str(
                        matched_title
                    ).strip()
                ]

            print(
                "\nTITLE MATCHED:"
            )

            print(
                "Requested:",
                title_query
            )

            print(
                "Matched:",
                title_name
            )

            print(
                "Requisition Number:",
                requisition_number
            )

        # ====================================================
        # UNKNOWN STATUS
        # ====================================================

        elif title_status not in (
            "EXACT",
            "SUGGEST",
            "MULTIPLE",
            "NOT_FOUND"
        ):

            return {
                "waiting_for_user":
                    True,

                "title_name":
                    title_name,

                "candidate_name":
                    candidate_name,

                "interviewer_names":
                    interviewer_names,

                "start_datetime":
                    start_datetime,

                "end_datetime":
                    end_datetime,

                "subject":
                    subject,

                "final_response":
                    (
                        f"I could not resolve the job title "
                        f"'{title_query}'. "
                        "Please provide another job title."
                    )
            }

    else:

        # ====================================================
        # REQUISITION NUMBER ALREADY PROVIDED
        #
        # DO NOT CALL JOB_REQUISITIONS
        # ====================================================

        print(
            "\nRequisition number provided directly:"
        )

        print(
            requisition_number
        )

    # ========================================================
    # SAFETY CHECK
    # ========================================================

    if not requisition_number:

        return {
            "waiting_for_user":
                True,

            "missing_information":
                [
                    "requisition_number"
                ],

            "candidate_name":
                candidate_name,

            "title_name":
                title_name,

            "interviewer_names":
                interviewer_names,

            "start_datetime":
                start_datetime,

            "end_datetime":
                end_datetime,

            "subject":
                subject,

            "final_response":
                (
                    "I could not determine the requisition "
                    "number. Please provide a requisition "
                    "number or job title."
                )
        }

    # ========================================================
    # CANDIDATEREQUISTION
    # ========================================================

    candidate_body = build_agent_body(
        "CANDIDATEREQUISTION",
        {
            "RequisitionNumber":
                requisition_number
        }
    )

    print(
        "\nCalling CANDIDATEREQUISTION..."
    )

    try:

        candidate_result = call_agent(
            "CANDIDATEREQUISTION",
            candidate_body
        )

    except Exception as e:

        return {
            "waiting_for_user":
                False,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "final_response":
                (
                    "Candidate lookup failed: "
                    f"{str(e)}"
                )
        }

    print_agent_result(
        "CANDIDATEREQUISTION",
        candidate_result
    )


    # ========================================================
    # RESOLVE CANDIDATE
    # ========================================================

    candidate_match = resolve_candidate(
        candidate_result,
        candidate_name
    )

    print(
        "\nCANDIDATE MATCH RESULT:"
    )

    print(
        json.dumps(
            candidate_match,
            indent=4,
            default=str
        )
    )

    candidate_status = (
        candidate_match.get(
            "status"
        )
    )


    # ========================================================
    # CANDIDATE NOT FOUND
    # ========================================================

    if candidate_status == "NOT_FOUND":

        return {
            "candidate_result":
                candidate_result,

            "waiting_for_user":
                True,

            "awaiting_confirmation":
                False,

            "confirmation_type":
                "candidate",

            "original_candidate_input":
                candidate_name,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "candidate_name":
                candidate_name,

            "interviewer_names":
                interviewer_names,

            "start_datetime":
                start_datetime,

            "end_datetime":
                end_datetime,

            "subject":
                subject,

            "final_response":
                (
                    f"I could not find a candidate matching "
                    f"'{candidate_name}' in requisition "
                    f"{requisition_number}. "
                    "Please provide another candidate name."
                ),

            "result_summary":
                (
                    f"I could not find a candidate matching "
                    f"'{candidate_name}' in requisition "
                    f"{requisition_number}. "
                    "Please provide another candidate name."
                )
        }


    # ========================================================
    # MULTIPLE CANDIDATE MATCHES
    #
    # Example:
    #
    # Jithu
    #
    # 1. Jithu Daniel
    # 2. Jithu Kumar
    # 3. Jithu Raj
    #
    # We DO NOT choose automatically.
    # ========================================================

    if candidate_status == "MULTIPLE":

        matches = candidate_match.get(
            "matches",
            []
        )

        valid_matches = []

        if isinstance(
            matches,
            list
        ):

            for match in matches:

                if not isinstance(
                    match,
                    dict
                ):

                    continue

                candidate_data = match.get(
                    "candidate"
                )

                if not isinstance(
                    candidate_data,
                    dict
                ):

                    continue

                candidate_actual_name = (
                    match.get(
                        "candidate_name"
                    )
                    or
                    candidate_data.get(
                        "CandidateName"
                    )
                )

                candidate_email = (
                    match.get(
                        "email"
                    )
                    or
                    candidate_data.get(
                        "Email"
                    )
                )

                job_application_id = (
                    match.get(
                        "jobApplicationId"
                    )
                    or
                    candidate_data.get(
                        "JobApplicationId"
                    )
                )

                if not candidate_actual_name:

                    continue

                valid_matches.append(
                    {
                        "candidate_name":
                            str(
                                candidate_actual_name
                            ).strip(),

                        "email":
                            candidate_email,

                        "jobApplicationId":
                            job_application_id,

                        "score":
                            match.get(
                                "score",
                                0.0
                            ),

                        "candidate":
                            candidate_data
                    }
                )

        # ====================================================
        # NO VALID MATCHES
        # ====================================================

        if not valid_matches:

            return {

                "candidate_result":
                    candidate_result,

                "waiting_for_user":
                    True,

                "awaiting_confirmation":
                    False,

                "confirmation_type":
                    "candidate",

                "original_candidate_input":
                    candidate_name,

                "requisition_number":
                    requisition_number,

                "title_name":
                    title_name,

                "candidate_name":
                    candidate_name,

                "interviewer_names":
                    interviewer_names,

                "start_datetime":
                    start_datetime,

                "end_datetime":
                    end_datetime,

                "subject":
                    subject,

                "final_response":
                    (
                        f"I found no usable candidate "
                        f"match for '{candidate_name}'. "
                        "Please provide another candidate name."
                    ),

                "result_summary":
                    (
                        f"I found no usable candidate "
                        f"match for '{candidate_name}'. "
                        "Please provide another candidate name."
                    )
            }

        # ====================================================
        # BUILD OPTIONS
        # ====================================================

        options = []

        for index, match in enumerate(
            valid_matches,
            start=1
        ):

            candidate_actual_name = (
                match.get(
                    "candidate_name"
                )
            )

            candidate_email = (
                match.get(
                    "email"
                )
            )

            job_application_id = (
                match.get(
                    "jobApplicationId"
                )
            )

            option = (
                f"{index}. "
                f"{candidate_actual_name}"
            )

            if candidate_email:

                option += (
                    f" ({candidate_email})"
                )

            if job_application_id:

                option += (
                    f" - Application "
                    f"{job_application_id}"
                )

            options.append(
                option
            )

        options_text = "\n".join(
            options
        )

        # ====================================================
        # WAIT FOR USER
        # ====================================================

        return {

            "candidate_result":
                candidate_result,

            "waiting_for_user":
                True,

            "awaiting_confirmation":
                True,

            "confirmation_type":
                "candidate_multiple",

            "original_candidate_input":
                candidate_name,

            "candidate_matches":
                valid_matches,

            "suggested_candidates":
                [
                    match.get(
                        "candidate_name"
                    )
                    for match
                    in valid_matches
                ],

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "candidate_name":
                candidate_name,

            "interviewer_names":
                interviewer_names,

            "start_datetime":
                start_datetime,

            "end_datetime":
                end_datetime,

            "subject":
                subject,

            "final_response":
                (
                    f"I found multiple candidates matching "
                    f"'{candidate_name}' in requisition "
                    f"{requisition_number}.\n\n"
                    f"{options_text}\n\n"
                    "Please select one by option number."
                ),

            "result_summary":
                (
                    f"I found multiple candidates matching "
                    f"'{candidate_name}' in requisition "
                    f"{requisition_number}.\n\n"
                    f"{options_text}\n\n"
                    "Please select one by option number."
                )
        }


    # ========================================================
    # SINGLE CANDIDATE SUGGESTION
    # ========================================================

    if candidate_status == "SUGGEST":

        suggested_name = (
            candidate_match.get(
                "candidate_name"
            )
        )

        return {

            "candidate_result":
                candidate_result,

            "waiting_for_user":
                True,

            "awaiting_confirmation":
                True,

            "confirmation_type":
                "candidate",

            "original_candidate_input":
                candidate_name,

            "suggested_candidate":
                suggested_name,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "candidate_name":
                candidate_name,

            "interviewer_names":
                interviewer_names,

            "start_datetime":
                start_datetime,

            "end_datetime":
                end_datetime,

            "subject":
                subject,

            "final_response":
                (
                    f"I couldn't find an exact match for "
                    f"'{candidate_name}'. "
                    f"Did you mean "
                    f"'{suggested_name}'?"
                ),

            "result_summary":
                (
                    f"I couldn't find an exact match for "
                    f"'{candidate_name}'. "
                    f"Did you mean "
                    f"'{suggested_name}'?"
                )
        }


    # ========================================================
    # CANONICAL CANDIDATE DATA
    # ========================================================

    canonical_candidate_name = (
        candidate_match.get(
            "candidate_name"
        )
    )

    candidate_email = (
        candidate_match.get(
            "email"
        )
    )

    job_application_id = (
        candidate_match.get(
            "jobApplicationId"
        )
    )


    # ========================================================
    # CANDIDATE EMAIL CHECK
    # ========================================================

    if not candidate_email:

        return {
            "candidate_result":
                candidate_result,

            "candidate_name":
                canonical_candidate_name,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "job_application_id":
                job_application_id,

            "waiting_for_user":
                False,

            "final_response":
                (
                    f"Candidate "
                    f"'{canonical_candidate_name}' "
                    "was found, but the email address "
                    "could not be found."
                )
        }

    # ========================================================
    # JOB APPLICATION ID CHECK
    # ========================================================

    if not job_application_id:

        return {
            "candidate_result":
                candidate_result,

            "candidate_name":
                canonical_candidate_name,

            "candidate_email":
                candidate_email,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "final_response":
                (
                    f"JobApplicationId was not found "
                    f"for {canonical_candidate_name}."
                )
        }

    print(
        "\nCANDIDATE MATCHED:"
    )

    print(
        canonical_candidate_name
    )

    print(
        "Email:",
        candidate_email
    )

    print(
        "JobApplicationId:",
        job_application_id
    )

    # ========================================================
    # INTERVIEWERDATA
    # ========================================================

    interviewer_body = build_agent_body(
        "INTERVIEWERDATA",
        {
            "RequisitionNumber":
                requisition_number
        }
    )

    print(
        "\nCalling INTERVIEWERDATA..."
    )

    try:

        interviewer_result = call_agent(
            "INTERVIEWERDATA",
            interviewer_body
        )

    except Exception as e:

        return {
            "candidate_result":
                candidate_result,

            "candidate_name":
                canonical_candidate_name,

            "candidate_email":
                candidate_email,

            "job_application_id":
                job_application_id,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "waiting_for_user":
                False,

            "result_summary":
                (
                    f"Unable to retrieve interviewer data: "
                    f"{str(e)}"
                )
        }

    print_agent_result(
        "INTERVIEWERDATA",
        interviewer_result
    )

    # ========================================================
    # RESOLVE INTERVIEWERS
    # ========================================================

    interviewer_match = resolve_interviewers(
        interviewer_result,
        interviewer_names
    )

    print(
        "\nINTERVIEWER MATCH RESULT:"
    )

    print(
        json.dumps(
            interviewer_match,
            indent=4,
            default=str
        )
    )

    status = interviewer_match.get(
        "status"
    )

    # ========================================================
    # INTERVIEWER NOT FOUND
    # ========================================================

    if status == "NOT_FOUND":

        not_found = interviewer_match.get(
            "not_found",
            interviewer_names
        )

        return {
            "candidate_result":
                candidate_result,

            "interviewer_result":
                interviewer_result,

            "waiting_for_user":
                True,

            "awaiting_confirmation":
                False,

            "confirmation_type":
                "interviewer",

            "original_interviewer_input":
                interviewer_names,

            "interviewer_names":
                interviewer_names,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "start_datetime":
                start_datetime,

            "end_datetime":
                end_datetime,

            "subject":
                subject,

            "candidate_name":
                canonical_candidate_name,

            "candidate_email":
                candidate_email,

            "job_application_id":
                job_application_id,

            "result_summary":
                (
                    "I could not find the following "
                    "interviewer(s): "
                    +
                    ", ".join(
                        not_found
                    )
                )
        }

    # ========================================================
    # INTERVIEWER SUGGESTION
    # ========================================================

    if status == "SUGGEST":

        suggestions = interviewer_match.get(
            "suggestions",
            []
        )

        suggested_names = []

        for suggestion in suggestions:

            if not isinstance(
                suggestion,
                dict
            ):

                continue

            name = (
                suggestion.get("actual_name")
                or suggestion.get("name")
                or suggestion.get("DisplayName")
            )

            if (
                name
                and
                name not in suggested_names
            ):

                suggested_names.append(
                    name
                )

        if not suggested_names:

            return {
                "candidate_result":
                    candidate_result,

                "interviewer_result":
                    interviewer_result,

                "waiting_for_user":
                    True,

                "awaiting_confirmation":
                    False,

                "confirmation_type":
                    "interviewer",

                "original_interviewer_input":
                    interviewer_names,

                "interviewer_names":
                    interviewer_names,

                "title_name":
                    title_name,

                "requisition_number":
                    requisition_number,

                "start_datetime":
                    start_datetime,

                "end_datetime":
                    end_datetime,

                "subject":
                    subject,

                "candidate_name":
                    canonical_candidate_name,

                "candidate_email":
                    candidate_email,

                "job_application_id":
                    job_application_id,

                "result_summary":
                    (
                        "I could not resolve the "
                        "requested interviewer."
                    )
            }

        # ----------------------------------------------------
        # SINGLE INTERVIEWER SUGGESTION
        # ----------------------------------------------------

        if len(
            suggested_names
        ) == 1:

            suggested_name = (
                suggested_names[0]
            )

            return {
                "candidate_result":
                    candidate_result,

                "interviewer_result":
                    interviewer_result,

                "waiting_for_user":
                    True,

                "awaiting_confirmation":
                    True,

                "confirmation_type":
                    "interviewer",

                "original_interviewer_input":
                    interviewer_names,

                "suggested_interviewer":
                    suggested_name,

                "suggested_interviewers":
                    suggested_names,

                "title_name":
                    title_name,

                "requisition_number":
                    requisition_number,

                "interviewer_names":
                    interviewer_names,

                "start_datetime":
                    start_datetime,

                "end_datetime":
                    end_datetime,

                "subject":
                    subject,

                "candidate_name":
                    canonical_candidate_name,

                "candidate_email":
                    candidate_email,

                "job_application_id":
                    job_application_id,

                "result_summary":
                    (
                        f"I couldn't find an exact match for "
                        f"'{', '.join(interviewer_names)}'. "
                        f"Did you mean "
                        f"'{suggested_name}'?"
                    )
            }

        # ----------------------------------------------------
        # MULTIPLE INTERVIEWER SUGGESTIONS
        # ----------------------------------------------------

        options_text = "\n".join(
            f"{index + 1}. {name}"
            for index, name
            in enumerate(
                suggested_names
            )
        )

        return {
            "candidate_result":
                candidate_result,

            "interviewer_result":
                interviewer_result,

            "waiting_for_user":
                True,

            "awaiting_confirmation":
                True,

            "confirmation_type":
                "interviewer",

            "original_interviewer_input":
                interviewer_names,

            "suggested_interviewers":
                suggested_names,

            "title_name":
                title_name,

            "requisition_number":
                requisition_number,

            "interviewer_names":
                interviewer_names,

            "start_datetime":
                start_datetime,

            "end_datetime":
                end_datetime,

            "subject":
                subject,

            "candidate_name":
                canonical_candidate_name,

            "candidate_email":
                candidate_email,

            "job_application_id":
                job_application_id,

            "result_summary":
                (
                    f"I found multiple interviewers matching "
                    f"'{', '.join(interviewer_names)}'. "
                    f"Please select one:\n\n"
                    f"{options_text}"
                )
        }

    # ========================================================
    # EXACT INTERVIEWER MATCHES
    # ========================================================

    matches = interviewer_match.get(
        "matches",
        []
    )

    if not matches:

        return {
            "candidate_result":
                candidate_result,

            "interviewer_result":
                interviewer_result,

            "waiting_for_user":
                True,

            "awaiting_confirmation":
                False,

            "confirmation_type":
                "interviewer",

            "interviewer_names":
                interviewer_names,

            "title_name":
                title_name,

            "requisition_number":
                requisition_number,

            "start_datetime":
                start_datetime,

            "end_datetime":
                end_datetime,

            "subject":
                subject,

            "candidate_name":
                canonical_candidate_name,

            "candidate_email":
                candidate_email,

            "job_application_id":
                job_application_id,

            "result_summary":
                (
                    "I could not resolve the "
                    "requested interviewer."
                )
        }

    # ========================================================
    # CANONICAL INTERVIEWER NAMES
    # ========================================================

    canonical_interviewer_names = []

    for item in matches:

        if not isinstance(
            item,
            dict
        ):

            continue

        name = item.get(
            "actual_name"
        )

        if (
            name
            and
            name not in canonical_interviewer_names
        ):

            canonical_interviewer_names.append(
                name
            )

    # ========================================================
    # INTERVIEWER EMAILS
    # ========================================================

    interviewer_emails = []

    for item in matches:

        if not isinstance(
            item,
            dict
        ):

            continue

        email = item.get(
            "email"
        )

        if (
            email
            and
            email not in interviewer_emails
        ):

            interviewer_emails.append(
                email
            )

    if not interviewer_emails:

        return {
            "candidate_result":
                candidate_result,

            "interviewer_result":
                interviewer_result,

            "interviewer_names":
                canonical_interviewer_names,

            "title_name":
                title_name,

            "requisition_number":
                requisition_number,

            "waiting_for_user":
                False,

            "result_summary":
                (
                    "Interviewer email addresses "
                    "could not be found."
                )
        }

    if len(
        interviewer_emails
    ) != len(
        canonical_interviewer_names
    ):

        return {
            "candidate_result":
                candidate_result,

            "interviewer_result":
                interviewer_result,

            "interviewer_names":
                canonical_interviewer_names,

            "interviewer_emails":
                interviewer_emails,

            "title_name":
                title_name,

            "requisition_number":
                requisition_number,

            "waiting_for_user":
                False,

            "result_summary":
                (
                    "I could not find email addresses "
                    "for all requested interviewers."
                )
        }

    # ========================================================
    # AVAILABILITY
    # ========================================================

    availability_parameters = {
        "interviewer_emails":
            interviewer_emails,

        "date":
            start_datetime[:10],

        "meeting_duration_minutes":
            30
    }

    availability_body = build_agent_body(
        "INTERVIEWER_AVAILABILITY",
        availability_parameters
    )

    print(
        "\nCalling INTERVIEWER_AVAILABILITY..."
    )

    try:

        availability_result = call_agent(
            "INTERVIEWER_AVAILABILITY",
            availability_body
        )

    except Exception as e:

        return {
            "candidate_result":
                candidate_result,

            "candidate_name":
                canonical_candidate_name,

            "candidate_email":
                candidate_email,

            "job_application_id":
                job_application_id,

            "interviewer_result":
                interviewer_result,

            "interviewer_names":
                canonical_interviewer_names,

            "interviewer_emails":
                interviewer_emails,

            "title_name":
                title_name,

            "requisition_number":
                requisition_number,

            "waiting_for_user":
                False,

            "result_summary":
                (
                    f"Availability check failed: "
                    f"{str(e)}"
                )
        }

    print_agent_result(
        "INTERVIEWER_AVAILABILITY",
        availability_result
    )

    # ========================================================
    # VERIFY REQUESTED SLOT
    # ========================================================

    slot_available = (
        is_requested_slot_available(
            availability_result,
            start_datetime,
            end_datetime
        )
    )

    if not slot_available:

        common_slots = extract_common_slots(
            availability_result
        )

        return {
            "candidate_result":
                candidate_result,

            "candidate_name":
                canonical_candidate_name,

            "candidate_email":
                candidate_email,

            "job_application_id":
                job_application_id,

            "interviewer_result":
                interviewer_result,

            "interviewers":
                canonical_interviewer_names,

            "interviewer_emails":
                interviewer_emails,

            "availability_result":
                availability_result,

            "common_slots":
                common_slots,

            "title_name":
                title_name,

            "requisition_number":
                requisition_number,

            "waiting_for_user":
                False,

            "result_summary":
                (
                    f"The requested interview time "
                    f"{start_datetime} to "
                    f"{end_datetime} "
                    "is not available for all "
                    "requested interviewer(s)."
                )
        }

    # ========================================================
    # SCHEDULING_TEAMS_MEETING
    # ========================================================

    scheduling_parameters = {

        "candidateName":
            canonical_candidate_name,

        "email":
            candidate_email,

        "startDateTime":
            start_datetime,

        "endDateTime":
            end_datetime,

        "subject":
            subject,

        "interviewers":
            canonical_interviewer_names,

        "interviewersEmail":
            interviewer_emails,

        "JobApplicationId":
            int(job_application_id)
    }

    scheduling_body = build_agent_body(
        "SCHEDULING_TEAMS_MEETING",
        scheduling_parameters
    )

    print(
        "\nSCHEDULING_TEAMS_MEETING BODY"
    )

    print(
        json.dumps(
            scheduling_body,
            indent=4,
            default=str
        )
    )

    # ========================================================
    # CALL SCHEDULING AGENT
    # ========================================================

    try:

        scheduling_result = call_agent(
            "SCHEDULING_TEAMS_MEETING",
            scheduling_body
        )

    except Exception as e:

        return {
            "candidate_result":
                candidate_result,

            "interviewer_result":
                interviewer_result,

            "availability_result":
                availability_result,

            "title_name":
                title_name,

            "requisition_number":
                requisition_number,

            "final_response":
                (
                    "Interview scheduling failed: "
                    f"{str(e)}"
                )
        }

    print_agent_result(
        "SCHEDULING_TEAMS_MEETING",
        scheduling_result
    )

    # ========================================================
    # SUCCESS
    # ========================================================

    return {

        "candidate_result":
            candidate_result,

        "candidate_name":
            canonical_candidate_name,

        "candidate_email":
            candidate_email,

        "job_application_id":
            job_application_id,

        "requisition_number":
            requisition_number,

        "title_name":
            title_name,

        "interviewer_result":
            interviewer_result,

        "interviewers":
            canonical_interviewer_names,

        "interviewer_emails":
            interviewer_emails,

        "availability_result":
            availability_result,

        "scheduling_result":
            scheduling_result,

        "waiting_for_user":
            False,

        "awaiting_confirmation":
            False,

        "result_summary":
            "Interview scheduled successfully."
    }


# ============================================================
# SCREENING FLOW
# ============================================================

def screening_flow(
    state: TaskState
):

    print(
        "\n========================================"
    )

    print(
        "START SCREENING FLOW"
    )

    print(
        "========================================"
    )

    requisition_number = state.get(
        "requisition_number"
    )

    candidate_names = normalize_list(
        state.get(
            "candidate_names",
            []
        )
    )

    # ========================================================
    # REQUIRED INFORMATION
    # ========================================================

    if not requisition_number:

        return {
            "waiting_for_user":
                True,

            "missing_information":
                ["requisition_number"],

            "result_summary":
                (
                    "Which requisition number are "
                    "these candidates associated with?"
                )
        }

    if not candidate_names:

        return {
            "waiting_for_user":
                True,

            "missing_information":
                ["candidate_names"],

            "result_summary":
                "Please provide the candidate name(s) to screen."
        }

    # ========================================================
    # CANDIDATEREQUISTION
    # ========================================================

    candidate_body = build_agent_body(
        "CANDIDATEREQUISTION",
        {
            "RequisitionNumber":
                requisition_number
        }
    )

    print(
        "\nCalling CANDIDATEREQUISTION..."
    )

    try:

        candidate_result = call_agent(
            "CANDIDATEREQUISTION",
            candidate_body
        )

    except Exception as e:

        return {
            "waiting_for_user":
                False,

            "result_summary":
                (
                    f"Unable to retrieve candidates: "
                    f"{str(e)}"
                )
        }

    print_agent_result(
        "CANDIDATEREQUISTION",
        candidate_result
    )

    # ========================================================
    # RESOLVE EVERY CANDIDATE
    # ========================================================

    job_application_ids = []

    matched_candidates = []

    for requested_name in candidate_names:

        candidate_match = resolve_candidate(
            candidate_result,
            requested_name
        )

        # ----------------------------------------------------
        # NOT FOUND
        # ----------------------------------------------------

        if (
            not candidate_match
            or
            candidate_match.get(
                "status"
            ) == "NOT_FOUND"
        ):

            return {
                "candidate_result":
                    candidate_result,

                "candidate_name":
                    requested_name,

                "waiting_for_user":
                    False,

                "result_summary":
                    (
                        f"I could not find a candidate matching "
                        f"'{requested_name}' in requisition "
                        f"{requisition_number}."
                    )
            }

        # ----------------------------------------------------
        # SUGGESTION
        # ----------------------------------------------------

        if candidate_match.get(
            "status"
        ) == "SUGGEST":

            suggested_name = candidate_match.get(
                "candidate_name"
            )

            return {
                "candidate_result":
                    candidate_result,

                "waiting_for_user":
                    True,

                "awaiting_confirmation":
                    True,

                "confirmation_type":
                    "candidate",

                "original_candidate_input":
                    requested_name,

                "suggested_candidate":
                    suggested_name,

                "candidate_names":
                    candidate_names,

                "requisition_number":
                    requisition_number,

                "result_summary":
                    (
                        f"I couldn't find an exact match for "
                        f"'{requested_name}'. "
                        f"Did you mean '{suggested_name}'?"
                    )
            }

        # ----------------------------------------------------
        # MATCHED CANDIDATE
        # ----------------------------------------------------

        candidate = candidate_match.get(
            "candidate"
        )

        job_application_id = (
            candidate_match.get(
                "jobApplicationId"
            )
        )

        if not job_application_id:

            return {
                "candidate_result":
                    candidate_result,

                "candidate_name":
                    requested_name,

                "waiting_for_user":
                    False,

                "result_summary":
                    (
                        f"JobApplicationId was not found for "
                        f"{candidate_match.get('candidate_name')}."
                    )
            }

        job_application_id = str(
            job_application_id
        )

        if job_application_id not in job_application_ids:

            job_application_ids.append(
                job_application_id
            )

        matched_candidates.append(
            candidate
            if isinstance(
                candidate,
                dict
            )
            else {}
        )

    # ========================================================
    # SCREENING AGENT
    # ========================================================

    screening_body = build_agent_body(
        "SCREENINGAGENT",
        {
            "JobApplicationId":
                job_application_ids
        }
    )

    print(
        "\nCalling SCREENINGAGENT..."
    )

    try:

        screening_result = call_agent(
            "SCREENINGAGENT",
            screening_body
        )

    except Exception as e:

        return {
            "candidate_result":
                candidate_result,

            "job_application_ids":
                job_application_ids,

            "waiting_for_user":
                False,

            "result_summary":
                (
                    f"Candidate screening failed: "
                    f"{str(e)}"
                )
        }

    print_agent_result(
        "SCREENINGAGENT",
        screening_result
    )

    return {
        "candidate_result":
            candidate_result,

        "candidate_names":
            [
                candidate.get(
                    "CandidateName"
                )
                for candidate in matched_candidates
                if candidate.get(
                    "CandidateName"
                )
            ],

        "job_application_ids":
            job_application_ids,

        "screening_result":
            screening_result,

        "waiting_for_user":
            False,

        "awaiting_confirmation":
            False,

        "result_summary":
            "Candidate screening completed successfully."
    }


# ============================================================
# EXTRACT EMAIL CONTENT
# ============================================================

def extract_email_content(
    agent_result
):

    if not isinstance(
        agent_result,
        dict
    ):

        return {}

    output = agent_result.get(
        "output"
    )

    if not output:
        return {}

    if isinstance(
        output,
        str
    ):

        output = safe_json_loads(
            output
        )

        if output is None:
            return {}

    if not isinstance(
        output,
        dict
    ):

        return {}

    result = output.get(
        "result",
        {}
    )

    if isinstance(
        result,
        str
    ):

        result = safe_json_loads(
            result
        )

        if result is None:
            return {}

    if not isinstance(
        result,
        dict
    ):

        return {}

    nested_result = result.get(
        "result",
        result
    )

    if isinstance(
        nested_result,
        str
    ):

        nested_result = safe_json_loads(
            nested_result
        )

        if nested_result is None:
            return {}

    if not isinstance(
        nested_result,
        dict
    ):

        return {}

    emails = nested_result.get(
        "emails",
        []
    )

    if (
        not isinstance(
            emails,
            list
        )
        or
        not emails
    ):

        return {}

    email_data = emails[0]

    if not isinstance(
        email_data,
        dict
    ):

        return {}

    return {
        "name":
            email_data.get(
                "name"
            ),

        "subject":
            email_data.get(
                "subject"
            ),

        "body1":
            email_data.get(
                "body1"
            ),

        "body2":
            email_data.get(
                "body2"
            )
    }


# ============================================================
# EMAIL FLOW
# ============================================================

def email_flow(
    state: TaskState
):

    print(
        "\n========================================"
    )

    print(
        "START EMAIL FLOW"
    )

    print(
        "========================================"
    )

    # ========================================================
    # GET INPUT VALUES
    # ========================================================

    candidate_name = state.get(
        "candidate_name"
    )

    requisition_number = state.get(
        "requisition_number"
    )

    title_name = state.get(
        "title_name",
        []
    )

    email_type = (
        state.get(
            "email_type"
        )
        or
        "other"
    )

    subject = state.get(
        "subject"
    )

    body = state.get(
        "body"
    )

    note = (
        state.get(
            "note"
        )
        or
        ""
    )

    interviewer_names = state.get(
        "interviewer_names",
        []
    )

    # ========================================================
    # NORMALIZE TITLE
    # ========================================================

    if isinstance(
        title_name,
        list
    ):

        title_query = (
            title_name[0]
            if title_name
            else None
        )

    elif title_name:

        title_query = str(
            title_name
        ).strip()

    else:

        title_query = None

    # ========================================================
    # BASIC VALIDATION
    # ========================================================

    missing = []

    if not candidate_name:

        missing.append(
            "candidate_name"
        )

    if (
        not requisition_number
        and
        not title_query
    ):

        missing.append(
            "requisition_number_or_title"
        )

    if missing:

        return {

            "waiting_for_user":
                True,

            "missing_information":
                missing,

            "candidate_name":
                candidate_name,

            "title_name":
                title_name,

            "requisition_number":
                requisition_number,

            "email_type":
                email_type,

            "subject":
                subject,

            "body":
                body,

            "note":
                note,

            "final_response":
                (
                    "Please provide the candidate name "
                    "and either the requisition number "
                    "or the job title."
                ),

            "result_summary":
                (
                    "Please provide the candidate name "
                    "and either the requisition number "
                    "or the job title."
                )
        }

    # ========================================================
    # REQUISITION RESOLUTION
    # ========================================================
    #
    # CASE 1:
    # User provided requisition number
    #
    #     -> DO NOT CALL JOB_REQUISITIONS
    #
    # CASE 2:
    # User provided title
    #
    #     -> CALL JOB_REQUISITIONS
    #     -> RESOLVE TITLE
    #     -> GET REQUISITION NUMBER
    #
    # ========================================================

    if not requisition_number:

        # ====================================================
        # JOB_REQUISITIONS
        # ====================================================

        title_parameters = {
            "UserInput":
                title_query
        }

        title_body = build_agent_body(
            "JOB_REQUISITIONS",
            title_parameters
        )

        print(
            "\nCalling JOB_REQUISITIONS..."
        )

        print(
            "\nJOB_REQUISITIONS BODY:"
        )

        print(
            json.dumps(
                title_body,
                indent=4,
                default=str
            )
        )

        try:

            title_result = call_agent(
                "JOB_REQUISITIONS",
                title_body
            )

        except Exception as e:

            return {

                "waiting_for_user":
                    False,

                "candidate_name":
                    candidate_name,

                "title_name":
                    title_name,

                "requisition_number":
                    None,

                "result_summary":
                    (
                        "Job requisition lookup failed: "
                        f"{str(e)}"
                    ),

                "final_response":
                    (
                        "Job requisition lookup failed: "
                        f"{str(e)}"
                    )
            }

        print_agent_result(
            "JOB_REQUISITIONS",
            title_result
        )

        # ====================================================
        # RESOLVE TITLE
        # ====================================================

        title_match = resolve_title(
            title_result,
            title_query
        )

        print(
            "\nTITLE RESOLUTION:"
        )

        print(
            json.dumps(
                title_match,
                indent=4,
                default=str
            )
        )

        # ====================================================
        # TITLE RESULT VALIDATION
        # ====================================================

        if not title_match:

            message = (
                f"I could not find a job requisition "
                f"matching '{title_query}'. "
                "Please provide another job title."
            )

            return {

                "waiting_for_user":
                    True,

                "awaiting_confirmation":
                    False,

                "confirmation_type":
                    "title",

                "original_title_input":
                    title_name,

                "candidate_name":
                    candidate_name,

                "title_name":
                    title_name,

                "requisition_number":
                    None,

                "email_type":
                    email_type,

                "subject":
                    subject,

                "body":
                    body,

                "note":
                    note,

                "final_response":
                    message,

                "result_summary":
                    message
            }

        title_status = title_match.get(
            "status"
        )

        # ====================================================
        # TITLE NOT FOUND
        # ====================================================

        if title_status == "NOT_FOUND":

            message = (
                f"I could not resolve the job title "
                f"'{title_query}'. "
                "Please provide another job title."
            )

            return {

                "waiting_for_user":
                    True,

                "awaiting_confirmation":
                    False,

                "confirmation_type":
                    "title",

                "original_title_input":
                    title_name,

                "candidate_name":
                    candidate_name,

                "title_name":
                    title_name,

                "requisition_number":
                    None,

                "email_type":
                    email_type,

                "subject":
                    subject,

                "body":
                    body,

                "note":
                    note,

                "final_response":
                    message,

                "result_summary":
                    message
            }

        # ====================================================
        # TITLE SUGGESTION
        # ====================================================

        if title_status == "SUGGEST":

            suggested_titles = []

            raw_suggestions = title_match.get(
                "suggested_titles",
                []
            )

            # ------------------------------------------------
            # Get suggested titles
            # ------------------------------------------------

            if isinstance(
                raw_suggestions,
                list
            ):

                for suggestion in raw_suggestions:

                    if isinstance(
                        suggestion,
                        str
                    ):

                        value = suggestion.strip()

                    elif isinstance(
                        suggestion,
                        dict
                    ):

                        value = (
                            suggestion.get(
                                "title"
                            )
                            or
                            suggestion.get(
                                "Title"
                            )
                            or
                            suggestion.get(
                                "matched_title"
                            )
                            or
                            suggestion.get(
                                "suggested_title"
                            )
                        )

                        if value:

                            value = str(
                                value
                            ).strip()

                    else:

                        value = None

                    if (
                        value
                        and
                        value not in suggested_titles
                    ):

                        suggested_titles.append(
                            value
                        )

            # ------------------------------------------------
            # Single suggestion fallback
            # ------------------------------------------------

            suggested_title = title_match.get(
                "suggested_title"
            )

            if suggested_title:

                suggested_title = str(
                    suggested_title
                ).strip()

                if (
                    suggested_title
                    and
                    suggested_title not in suggested_titles
                ):

                    suggested_titles.append(
                        suggested_title
                    )

            # ------------------------------------------------
            # suggestions fallback
            # ------------------------------------------------

            suggestions = title_match.get(
                "suggestions",
                []
            )

            if isinstance(
                suggestions,
                list
            ):

                for suggestion in suggestions:

                    if isinstance(
                        suggestion,
                        str
                    ):

                        value = suggestion.strip()

                    elif isinstance(
                        suggestion,
                        dict
                    ):

                        value = (
                            suggestion.get(
                                "title"
                            )
                            or
                            suggestion.get(
                                "Title"
                            )
                            or
                            suggestion.get(
                                "matched_title"
                            )
                            or
                            suggestion.get(
                                "suggested_title"
                            )
                        )

                        if value:

                            value = str(
                                value
                            ).strip()

                    else:

                        value = None

                    if (
                        value
                        and
                        value not in suggested_titles
                    ):

                        suggested_titles.append(
                            value
                        )

            # ------------------------------------------------
            # No suggestion
            # ------------------------------------------------

            if not suggested_titles:

                message = (
                    f"I could not resolve the job title "
                    f"'{title_query}'. "
                    "Please provide another job title."
                )

                return {

                    "waiting_for_user":
                        True,

                    "awaiting_confirmation":
                        False,

                    "confirmation_type":
                        "title",

                    "original_title_input":
                        title_name,

                    "candidate_name":
                        candidate_name,

                    "title_name":
                        title_name,

                    "requisition_number":
                        None,

                    "email_type":
                        email_type,

                    "subject":
                        subject,

                    "body":
                        body,

                    "note":
                        note,

                    "final_response":
                        message,

                    "result_summary":
                        message
                }

            # ------------------------------------------------
            # Single suggestion
            # ------------------------------------------------

            if len(
                suggested_titles
            ) == 1:

                suggested_title = (
                    suggested_titles[0]
                )

                suggested_requisition_number = (
                    title_match.get(
                        "requisition_number"
                    )
                )

                message = (
                    f"I couldn't find an exact match "
                    f"for '{title_query}'. "
                    f"Did you mean "
                    f"'{suggested_title}'?"
                )

                return {

                    "waiting_for_user":
                        True,

                    "awaiting_confirmation":
                        True,

                    "confirmation_type":
                        "title",

                    "original_title_input":
                        title_name,

                    "suggested_title":
                        suggested_title,

                    "suggested_titles":
                        suggested_titles,

                    "suggested_requisition_number":
                        suggested_requisition_number,

                    "candidate_name":
                        candidate_name,

                    "title_name":
                        title_name,

                    "requisition_number":
                        None,

                    "email_type":
                        email_type,

                    "subject":
                        subject,

                    "body":
                        body,

                    "note":
                        note,

                    "final_response":
                        message,

                    "result_summary":
                        message
                }

            # ------------------------------------------------
            # Multiple suggestions
            # ------------------------------------------------

            options_text = "\n".join(

                f"{index + 1}. {title}"

                for index, title
                in enumerate(
                    suggested_titles
                )
            )

            message = (
                f"I found multiple job titles "
                f"matching '{title_query}'. "
                f"Please select one:\n\n"
                f"{options_text}"
            )

            return {

                "waiting_for_user":
                    True,

                "awaiting_confirmation":
                    True,

                "confirmation_type":
                    "title",

                "original_title_input":
                    title_name,

                "suggested_titles":
                    suggested_titles,

                "candidate_name":
                    candidate_name,

                "title_name":
                    title_name,

                "requisition_number":
                    None,

                "email_type":
                    email_type,

                "subject":
                    subject,

                "body":
                    body,

                "note":
                    note,

                "final_response":
                    message,

                "result_summary":
                    message
            }

        # ====================================================
        # MULTIPLE TITLE MATCH
        # ====================================================

        if title_status == "MULTIPLE":

            matches = title_match.get(
                "matches",
                []
            )

            valid_matches = []

            if isinstance(
                matches,
                list
            ):

                for match in matches:

                    if not isinstance(
                        match,
                        dict
                    ):
                        continue

                    matched_title = (
                        match.get(
                            "title"
                        )
                        or
                        match.get(
                            "Title"
                        )
                        or
                        match.get(
                            "matched_title"
                        )
                    )

                    requisition_number_match = (
                        match.get(
                            "requisition_number"
                        )
                        or
                        match.get(
                            "RequisitionNumber"
                        )
                    )

                    if not matched_title:
                        continue

                    matched_title = str(
                        matched_title
                    ).strip()

                    if (
                        requisition_number_match
                        is not None
                    ):

                        requisition_number_match = str(
                            requisition_number_match
                        ).strip()

                    valid_matches.append(
                        {
                            "title":
                                matched_title,

                            "requisition_number":
                                requisition_number_match,

                            "score":
                                match.get(
                                    "score",
                                    0.0
                                ),

                            "match_type":
                                match.get(
                                    "match_type"
                                ),

                            "requisition":
                                match.get(
                                    "requisition"
                                )
                        }
                    )

            # ------------------------------------------------
            # No valid matches
            # ------------------------------------------------

            if not valid_matches:

                message = (
                    f"I could not resolve the job title "
                    f"'{title_query}'. "
                    "Please provide another job title."
                )

                return {

                    "waiting_for_user":
                        True,

                    "awaiting_confirmation":
                        False,

                    "confirmation_type":
                        "title",

                    "original_title_input":
                        title_name,

                    "candidate_name":
                        candidate_name,

                    "title_name":
                        title_name,

                    "requisition_number":
                        None,

                    "email_type":
                        email_type,

                    "subject":
                        subject,

                    "body":
                        body,

                    "note":
                        note,

                    "final_response":
                        message,

                    "result_summary":
                        message
                }

            # ------------------------------------------------
            # Build options
            # ------------------------------------------------

            options = []

            for index, match in enumerate(
                valid_matches,
                start=1
            ):

                matched_title = match.get(
                    "title"
                )

                requisition_number_match = (
                    match.get(
                        "requisition_number"
                    )
                )

                if requisition_number_match:

                    option_text = (
                        f"{index}. "
                        f"{matched_title} "
                        f"(Requisition "
                        f"{requisition_number_match})"
                    )

                else:

                    option_text = (
                        f"{index}. "
                        f"{matched_title}"
                    )

                options.append(
                    option_text
                )

            options_text = "\n".join(
                options
            )

            message = (
                f"I found multiple job titles "
                f"matching '{title_query}'. "
                f"Please select one:\n\n"
                f"{options_text}\n\n"
                "You can reply with the option number "
                "or the requisition number."
            )

            return {

                "waiting_for_user":
                    True,

                "awaiting_confirmation":
                    True,

                "confirmation_type":
                    "title_multiple",

                "original_title_input":
                    title_name,

                "requested_title":
                    title_query,

                "title_matches":
                    valid_matches,

                "suggested_titles":
                    [
                        match.get(
                            "title"
                        )
                        for match in valid_matches
                    ],

                "candidate_name":
                    candidate_name,

                "title_name":
                    title_name,

                "requisition_number":
                    None,

                "email_type":
                    email_type,

                "subject":
                    subject,

                "body":
                    body,

                "note":
                    note,

                "final_response":
                    message,

                "result_summary":
                    message
            }

        # ====================================================
        # UNKNOWN TITLE STATUS
        # ====================================================

        return {

            "waiting_for_user":
                True,

            "awaiting_confirmation":
                False,

            "confirmation_type":
                "title",

            "candidate_name":
                candidate_name,

            "title_name":
                title_name,

            "requisition_number":
                None,

            "email_type":
                email_type,

            "subject":
                subject,

            "body":
                body,

            "note":
                note,

            "final_response":
                (
                    f"I could not resolve the job title "
                    f"'{title_query}'. "
                    "Please provide another job title."
                ),

            "result_summary":
                (
                    f"I could not resolve the job title "
                    f"'{title_query}'. "
                    "Please provide another job title."
                )
        }

    else:

        # ====================================================
        # REQUISITION NUMBER PROVIDED DIRECTLY
        #
        # DO NOT CALL JOB_REQUISITIONS
        # ====================================================

        print(
            "\nRequisition number provided directly:"
        )

        print(
            requisition_number
        )

    # ========================================================
    # SAFETY CHECK
    # ========================================================

    if not requisition_number:

        message = (
            "I could not determine the requisition "
            "number. Please provide a requisition "
            "number or job title."
        )

        return {

            "waiting_for_user":
                True,

            "candidate_name":
                candidate_name,

            "title_name":
                title_name,

            "requisition_number":
                None,

            "email_type":
                email_type,

            "subject":
                subject,

            "body":
                body,

            "note":
                note,

            "final_response":
                message,

            "result_summary":
                message
        }

    # ========================================================
    # CANDIDATEREQUISTION
    # ========================================================

    candidate_body = build_agent_body(
        "CANDIDATEREQUISTION",
        {
            "RequisitionNumber":
                requisition_number
        }
    )

    print(
        "\nCalling CANDIDATEREQUISTION..."
    )

    try:

        candidate_result = call_agent(
            "CANDIDATEREQUISTION",
            candidate_body
        )

    except Exception as e:

        message = (
            "Candidate lookup failed: "
            f"{str(e)}"
        )

        return {

            "waiting_for_user":
                False,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "candidate_name":
                candidate_name,

            "email_type":
                email_type,

            "final_response":
                message,

            "result_summary":
                message
        }

    print_agent_result(
        "CANDIDATEREQUISTION",
        candidate_result
    )

    # ========================================================
    # RESOLVE CANDIDATE
    # ========================================================

    candidate_match = resolve_candidate(
        candidate_result,
        candidate_name
    )

    print(
        "\nCANDIDATE MATCH RESULT:"
    )

    print(
        json.dumps(
            candidate_match,
            indent=4,
            default=str
        )
    )

    # ========================================================
    # INVALID CANDIDATE RESULT
    # ========================================================

    if not candidate_match:

        message = (
            f"I could not find a candidate matching "
            f"'{candidate_name}' in requisition "
            f"{requisition_number}. "
            "Please provide another candidate name."
        )

        return {

            "candidate_result":
                candidate_result,

            "waiting_for_user":
                True,

            "awaiting_confirmation":
                False,

            "confirmation_type":
                "candidate",

            "original_candidate_input":
                candidate_name,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "candidate_name":
                candidate_name,

            "email_type":
                email_type,

            "subject":
                subject,

            "body":
                body,

            "note":
                note,

            "final_response":
                message,

            "result_summary":
                message
        }

    candidate_status = (
        candidate_match.get(
            "status"
        )
    )

    # ========================================================
    # CANDIDATE NOT FOUND
    # ========================================================

    if candidate_status == "NOT_FOUND":

        message = (
            f"I could not find a candidate matching "
            f"'{candidate_name}' in requisition "
            f"{requisition_number}. "
            "Please provide another candidate name."
        )

        return {

            "candidate_result":
                candidate_result,

            "waiting_for_user":
                True,

            "awaiting_confirmation":
                False,

            "confirmation_type":
                "candidate",

            "original_candidate_input":
                candidate_name,

            "suggested_candidate":
                None,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "candidate_name":
                candidate_name,

            "email_type":
                email_type,

            "subject":
                subject,

            "body":
                body,

            "note":
                note,

            "final_response":
                message,

            "result_summary":
                message
        }

    # ========================================================
    # SINGLE CANDIDATE SUGGESTION
    # ========================================================

    if candidate_status == "SUGGEST":

        suggested_name = (
            candidate_match.get(
                "candidate_name"
            )
        )

        message = (
            f"I couldn't find an exact match for "
            f"'{candidate_name}' "
            f"under '{title_query or requisition_number}'. "
            f"Did you mean '{suggested_name}'?"
        )

        return {

            "candidate_result":
                candidate_result,

            "waiting_for_user":
                True,

            "awaiting_confirmation":
                True,

            "confirmation_type":
                "candidate",

            "original_candidate_input":
                candidate_name,

            "suggested_candidate":
                suggested_name,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "candidate_name":
                candidate_name,

            "email_type":
                email_type,

            "subject":
                subject,

            "body":
                body,

            "note":
                note,

            "final_response":
                message,

            "result_summary":
                message
        }

    # ========================================================
    # MULTIPLE CANDIDATE MATCHES
    # ========================================================

    if candidate_status == "MULTIPLE":

        matches = candidate_match.get(
            "matches",
            []
        )

        valid_matches = []

        if isinstance(
            matches,
            list
        ):

            for match in matches:

                if not isinstance(
                    match,
                    dict
                ):
                    continue

                candidate_data = match.get(
                    "candidate"
                )

                if not isinstance(
                    candidate_data,
                    dict
                ):
                    continue

                # ------------------------------------------------
                # Candidate Name
                # ------------------------------------------------

                candidate_actual_name = (
                    match.get(
                        "candidate_name"
                    )
                    or
                    candidate_data.get(
                        "CandidateName"
                    )
                )

                # ------------------------------------------------
                # Candidate Email
                # ------------------------------------------------

                candidate_email = (
                    match.get(
                        "email"
                    )
                    or
                    candidate_data.get(
                        "Email"
                    )
                )

                # ------------------------------------------------
                # Job Application ID
                # ------------------------------------------------

                job_application_id = (
                    match.get(
                        "jobApplicationId"
                    )
                    or
                    candidate_data.get(
                        "JobApplicationId"
                    )
                )

                # ------------------------------------------------
                # Candidate Title
                #
                # If candidate-level title exists, use it.
                # Otherwise use the resolved requisition title.
                # ------------------------------------------------

                candidate_title = (
                    match.get(
                        "title"
                    )
                    or
                    match.get(
                        "Title"
                    )
                    or
                    candidate_data.get(
                        "Title"
                    )
                    or
                    candidate_data.get(
                        "JobTitle"
                    )
                    or
                    candidate_data.get(
                        "PositionTitle"
                    )
                )

                if not candidate_title:

                    if isinstance(
                        title_name,
                        list
                    ) and title_name:

                        candidate_title = (
                            title_name[0]
                        )

                    elif title_name:

                        candidate_title = (
                            str(
                                title_name
                            ).strip()
                        )

                # ------------------------------------------------
                # Candidate requisition
                # ------------------------------------------------

                candidate_requisition = (
                    match.get(
                        "requisition_number"
                    )
                    or
                    candidate_data.get(
                        "RequisitionNumber"
                    )
                    or
                    requisition_number
                )

                if not candidate_actual_name:
                    continue

                valid_matches.append(
                    {
                        "candidate_name":
                            str(
                                candidate_actual_name
                            ).strip(),

                        "title":
                            (
                                str(
                                    candidate_title
                                ).strip()
                                if candidate_title
                                else None
                            ),

                        "email":
                            candidate_email,

                        "jobApplicationId":
                            job_application_id,

                        "requisition_number":
                            candidate_requisition,

                        "score":
                            match.get(
                                "score",
                                0.0
                            ),

                        "candidate":
                            candidate_data
                    }
                )

        # ====================================================
        # NO VALID MATCHES
        # ====================================================

        if not valid_matches:

            message = (
                f"I found no usable candidate "
                f"match for '{candidate_name}'. "
                "Please provide another candidate name."
            )

            return {

                "candidate_result":
                    candidate_result,

                "waiting_for_user":
                    True,

                "awaiting_confirmation":
                    False,

                "confirmation_type":
                    "candidate",

                "original_candidate_input":
                    candidate_name,

                "requisition_number":
                    requisition_number,

                "title_name":
                    title_name,

                "candidate_name":
                    candidate_name,

                "email_type":
                    email_type,

                "subject":
                    subject,

                "body":
                    body,

                "note":
                    note,

                "final_response":
                    message,

                "result_summary":
                    message
            }

        # ====================================================
        # BUILD CANDIDATE OPTIONS
        # ====================================================

        options = []

        for index, match in enumerate(
            valid_matches,
            start=1
        ):

            candidate_actual_name = (
                match.get(
                    "candidate_name"
                )
            )

            candidate_title = (
                match.get(
                    "title"
                )
            )

            candidate_email = (
                match.get(
                    "email"
                )
            )

            job_application_id = (
                match.get(
                    "jobApplicationId"
                )
            )

            candidate_requisition = (
                match.get(
                    "requisition_number"
                )
            )

            # ------------------------------------------------
            # Candidate name
            # ------------------------------------------------

            option = (
                f"{index}. "
                f"{candidate_actual_name}"
            )

            # ------------------------------------------------
            # Title
            # ------------------------------------------------

            if candidate_title:

                option += (
                    f" - {candidate_title}"
                )

            # ------------------------------------------------
            # Requisition
            # ------------------------------------------------

            if candidate_requisition:

                option += (
                    f" (Requisition "
                    f"{candidate_requisition})"
                )

            # ------------------------------------------------
            # Email
            # ------------------------------------------------

            if candidate_email:

                option += (
                    f" ({candidate_email})"
                )

            # ------------------------------------------------
            # Application
            # ------------------------------------------------

            if job_application_id:

                option += (
                    f" - Application "
                    f"{job_application_id}"
                )

            options.append(
                option
            )

        options_text = "\n".join(
            options
        )

        message = (
            f"I found multiple candidates matching "
            f"'{candidate_name}'"
        )

        if title_query:

            message += (
                f" for '{title_query}'"
            )

        message += (
            ".\n\n"
            f"{options_text}\n\n"
            "Please select one by option number."
        )

        # ====================================================
        # STORE MULTIPLE CANDIDATES
        # ====================================================

        return {

            "candidate_result":
                candidate_result,

            "waiting_for_user":
                True,

            "awaiting_confirmation":
                True,

            "confirmation_type":
                "candidate_multiple",

            "original_candidate_input":
                candidate_name,

            "candidate_matches":
                valid_matches,

            "suggested_candidates":
                [
                    match.get(
                        "candidate_name"
                    )
                    for match in valid_matches
                ],

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "candidate_name":
                candidate_name,

            "interviewer_names":
                interviewer_names,

            "email_type":
                email_type,

            "subject":
                subject,

            "body":
                body,

            "note":
                note,

            "final_response":
                message,

            "result_summary":
                message
        }

    # ========================================================
    # CANONICAL CANDIDATE DATA
    # ========================================================

    canonical_candidate_name = (
        candidate_match.get(
            "candidate_name"
        )
    )

    candidate_email = (
        candidate_match.get(
            "email"
        )
    )

    job_application_id = (
        candidate_match.get(
            "jobApplicationId"
        )
    )

    # ========================================================
    # CANDIDATE EMAIL CHECK
    # ========================================================

    if not candidate_email:

        message = (
            f"Candidate "
            f"'{canonical_candidate_name}' "
            "was found, but the email address "
            "could not be found."
        )

        return {

            "candidate_result":
                candidate_result,

            "candidate_name":
                canonical_candidate_name,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "job_application_id":
                job_application_id,

            "waiting_for_user":
                False,

            "final_response":
                message,

            "result_summary":
                message
        }

    # ========================================================
    # EMAIL HR
    # ========================================================

    email_parameters = {

        "Type":
            email_type,

        "Tone":
            "professional",

        "Email":
            candidate_email,

        "subject":
            subject,

        "body":
            body,

        "Note":
            note
    }

    email_body = build_agent_body(
        "EMAIL_HR",
        email_parameters
    )

    print(
        "\nCalling EMAIL_HR..."
    )

    print(
        "\nEMAIL_HR BODY:"
    )

    print(
        json.dumps(
            email_body,
            indent=4,
            default=str
        )
    )

    try:

        email_result = call_agent(
            "EMAIL_HR",
            email_body
        )

    except Exception as e:

        message = (
            f"Email generation failed: "
            f"{str(e)}"
        )

        return {

            "candidate_result":
                candidate_result,

            "candidate_name":
                canonical_candidate_name,

            "candidate_email":
                candidate_email,

            "job_application_id":
                job_application_id,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "waiting_for_user":
                False,

            "final_response":
                message,

            "result_summary":
                message
        }

    print_agent_result(
        "EMAIL_HR",
        email_result
    )

    # ========================================================
    # EXTRACT GENERATED EMAIL
    # ========================================================

    generated_email = extract_email_content(
        email_result
    )

    email_subject = generated_email.get(
        "subject"
    )

    email_text = generated_email.get(
        "body2"
    )

    # ========================================================
    # SUBJECT VALIDATION
    # ========================================================

    if not email_subject:

        message = (
            "EMAIL_HR did not return a subject."
        )

        return {

            "candidate_result":
                candidate_result,

            "email_generation_result":
                email_result,

            "candidate_name":
                canonical_candidate_name,

            "candidate_email":
                candidate_email,

            "job_application_id":
                job_application_id,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "waiting_for_user":
                False,

            "final_response":
                message,

            "result_summary":
                message
        }

    # ========================================================
    # BODY VALIDATION
    # ========================================================

    if not email_text:

        message = (
            "EMAIL_HR did not return a body."
        )

        return {

            "candidate_result":
                candidate_result,

            "email_generation_result":
                email_result,

            "candidate_name":
                canonical_candidate_name,

            "candidate_email":
                candidate_email,

            "job_application_id":
                job_application_id,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "waiting_for_user":
                False,

            "final_response":
                message,

            "result_summary":
                message
        }

    # ========================================================
    # HREMAILSEND
    # ========================================================

    send_parameters = {

        "email":
            candidate_email,

        "subject":
            email_subject,

        "body":
            email_text
    }

    send_body = build_agent_body(
        "HREMAILSEND",
        send_parameters
    )

    print(
        "\nHREMAILSEND BODY"
    )

    print(
        json.dumps(
            send_body,
            indent=4,
            default=str
        )
    )

    try:

        send_result = call_agent(
            "HREMAILSEND",
            send_body
        )

    except Exception as e:

        message = (
            f"HREMAILSEND failed: "
            f"{str(e)}"
        )

        return {

            "candidate_result":
                candidate_result,

            "candidate_name":
                canonical_candidate_name,

            "candidate_email":
                candidate_email,

            "job_application_id":
                job_application_id,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "email_generation_result":
                email_result,

            "email_send_result":
                None,

            "waiting_for_user":
                False,

            "final_response":
                message,

            "result_summary":
                message
        }

    print_agent_result(
        "HREMAILSEND",
        send_result
    )

    # ========================================================
    # SUCCESS
    # ========================================================

    return {

        "candidate_result":
            candidate_result,

        "candidate_name":
            canonical_candidate_name,

        "candidate_email":
            candidate_email,

        "job_application_id":
            job_application_id,

        "requisition_number":
            requisition_number,

        "title_name":
            title_name,

        "email_generation_result":
            email_result,

        "email_send_result":
            send_result,

        "waiting_for_user":
            False,

        "awaiting_confirmation":
            False,

        "confirmation_type":
            None,

        "result_summary":
            "Email sent successfully.",

        "final_response":
            "Email sent successfully."
    }



# ============================================================
# LINKEDIN JOB DESCRIPTION FLOW
# ============================================================

def linkedin_job_desc_flow(
    state: TaskState
):

    print(
        "\n========================================"
    )

    print(
        "START LINKEDIN JOB DESCRIPTION FLOW"
    )

    print(
        "========================================"
    )

    job_description = state.get(
        "job_description"
    )

    if not job_description:

        return {
            "waiting_for_user":
                True,

            "missing_information":
                ["job_description"],

            "result_summary":
                (
                    "Please provide the job description "
                    "you want to post on LinkedIn."
                )
        }

    linkedin_parameters = {
        "jobDescription":
            job_description
    }

    linkedin_body = build_agent_body(
        "LINKEDIN_JOB_DESC",
        linkedin_parameters
    )

    print(
        "\nLINKEDIN_JOB_DESC BODY"
    )

    print(
        json.dumps(
            linkedin_body,
            indent=4,
            default=str
        )
    )

    print(
        "\nCalling LINKEDIN_JOB_DESC..."
    )

    try:

        linkedin_result = call_agent(
            "LINKEDIN_JOB_DESC",
            linkedin_body
        )

    except Exception as e:

        return {
            "linkedin_result":
                None,

            "waiting_for_user":
                False,

            "result_summary":
                (
                    "LinkedIn job posting failed: "
                    f"{str(e)}"
                )
        }

    print_agent_result(
        "LINKEDIN_JOB_DESC",
        linkedin_result
    )

    return {
        "linkedin_result":
            linkedin_result,

        "job_description":
            job_description,

        "waiting_for_user":
            False,

        "awaiting_confirmation":
            False,

        "result_summary":
            (
                "The job description was posted "
                "to LinkedIn successfully."
            )
    }

# ============================================================
# INTERVIEW QUESTIONS FLOW
# ============================================================

def interview_questions(
    state: TaskState
):

    print(
        "\n========================================"
    )

    print(
        "START INTERVIEW QUESTIONS FLOW"
    )

    print(
        "========================================"
    )

    # ========================================================
    # 1. GET REQUIRED VALUES FROM STATE
    # ========================================================

    requisition_number = state.get(
        "requisition_number"
    )

    title_name = normalize_list(
        state.get(
            "title_name",
            []
        )
    )

    # --------------------------------------------------------
    # JOB_REQUISITIONS expects one title string
    # --------------------------------------------------------

    title_query = (
        title_name[0]
        if title_name
        else None
    )

    print(
        "\nINPUT VALUES:"
    )

    print(
        "Requisition Number:",
        requisition_number
    )

    print(
        "Title Name:",
        title_name
    )

    print(
        "Title Query:",
        title_query
    )

    # ========================================================
    # 2. TITLE PROVIDED
    #
    # If requisition number is not available but title is
    # provided, first find the requisition number using
    # JOB_REQUISITIONS.
    # ========================================================

    if (
        not requisition_number
        and title_query
    ):

        print(
            "\n========================================"
        )

        print(
            "TITLE PROVIDED"
        )

        print(
            "Calling JOB_REQUISITIONS..."
        )

        print(
            "========================================"
        )

        # ====================================================
        # 3. BUILD JOB_REQUISITIONS PARAMETERS
        # ====================================================

        title_parameters = {

            "UserInput":
                title_query
        }

        print(
            "\nJOB_REQUISITIONS PARAMETERS:"
        )

        print(
            json.dumps(
                title_parameters,
                indent=4,
                default=str
            )
        )

        # ====================================================
        # 4. BUILD JOB_REQUISITIONS BODY
        # ====================================================

        title_body = build_agent_body(
            "JOB_REQUISITIONS",
            title_parameters
        )

        print(
            "\nJOB_REQUISITIONS BODY:"
        )

        print(
            json.dumps(
                title_body,
                indent=4,
                default=str
            )
        )

        # ====================================================
        # 5. CALL JOB_REQUISITIONS
        # ====================================================

        try:

            title_result = call_agent(
                "JOB_REQUISITIONS",
                title_body
            )

        except Exception as e:

            print(
                "\nJOB_REQUISITIONS ERROR:"
            )

            print(
                str(e)
            )

            return {

                "waiting_for_user":
                    False,

                "title_name":
                    title_name,

                "requisition_number":
                    None,

                "interview_questions_result":
                    None,

                "final_response":
                    (
                        "Job requisition lookup failed: "
                        f"{str(e)}"
                    )
            }

        # ====================================================
        # 6. PRINT JOB REQUISITIONS RESULT
        # ====================================================

        print_agent_result(
            "JOB_REQUISITIONS",
            title_result
        )

        # ====================================================
        # 7. RESOLVE TITLE
        # ====================================================

        title_match = resolve_title(
            title_result,
            title_query
        )

        print(
            "\nTITLE RESOLUTION:"
        )

        print(
            json.dumps(
                title_match,
                indent=4,
                default=str
            )
        )

        # ====================================================
        # 8. TITLE NOT FOUND
        # ====================================================

        if not title_match:

            return {

                "waiting_for_user":
                    True,

                "awaiting_confirmation":
                    False,

                "confirmation_type":
                    "title",

                "original_title_input":
                    title_name,

                "title_name":
                    title_name,

                "requisition_number":
                    None,

                "interview_questions_result":
                    None,

                "final_response":
                    (
                        f"I could not find a job requisition "
                        f"matching '{title_query}'. "
                        "Please provide another job title."
                    )
            }

        # ====================================================
        # 9. GET TITLE STATUS
        # ====================================================

        title_status = title_match.get(
            "status"
        )

        print(
            "\nTITLE STATUS:"
        )

        print(
            title_status
        )

        # ====================================================
        # 10. MULTIPLE TITLE SUGGESTIONS
        #
        # Example:
        #
        # Site Engineer
        # Site Engineer (Trainee)
        # ====================================================

        if title_status == "SUGGEST":

            suggested_titles = []

            # ------------------------------------------------
            # suggested_titles
            # ------------------------------------------------

            raw_suggestions = title_match.get(
                "suggested_titles",
                []
            )

            if isinstance(
                raw_suggestions,
                list
            ):

                for suggestion in raw_suggestions:

                    if isinstance(
                        suggestion,
                        str
                    ):

                        value = suggestion.strip()

                    elif isinstance(
                        suggestion,
                        dict
                    ):

                        value = (
                            suggestion.get("title")
                            or
                            suggestion.get("Title")
                            or
                            suggestion.get("matched_title")
                            or
                            suggestion.get("suggested_title")
                        )

                        if value:

                            value = str(
                                value
                            ).strip()

                    else:

                        value = None

                    if (
                        value
                        and
                        value not in suggested_titles
                    ):

                        suggested_titles.append(
                            value
                        )

            # ------------------------------------------------
            # suggested_title fallback
            # ------------------------------------------------

            suggested_title = title_match.get(
                "suggested_title"
            )

            if suggested_title:

                suggested_title = str(
                    suggested_title
                ).strip()

                if (
                    suggested_title
                    and
                    suggested_title not in suggested_titles
                ):

                    suggested_titles.append(
                        suggested_title
                    )

            # ------------------------------------------------
            # suggestions fallback
            # ------------------------------------------------

            suggestions = title_match.get(
                "suggestions",
                []
            )

            if isinstance(
                suggestions,
                list
            ):

                for suggestion in suggestions:

                    if isinstance(
                        suggestion,
                        str
                    ):

                        value = suggestion.strip()

                    elif isinstance(
                        suggestion,
                        dict
                    ):

                        value = (
                            suggestion.get("title")
                            or
                            suggestion.get("Title")
                            or
                            suggestion.get("matched_title")
                            or
                            suggestion.get("suggested_title")
                        )

                        if value:

                            value = str(
                                value
                            ).strip()

                    else:

                        value = None

                    if (
                        value
                        and
                        value not in suggested_titles
                    ):

                        suggested_titles.append(
                            value
                        )

            # =================================================
            # NO SUGGESTIONS FOUND
            # =================================================

            if not suggested_titles:

                return {

                    "waiting_for_user":
                        True,

                    "awaiting_confirmation":
                        False,

                    "confirmation_type":
                        "title",

                    "original_title_input":
                        title_name,

                    "title_name":
                        title_name,

                    "requisition_number":
                        None,

                    "interview_questions_result":
                        None,

                    "final_response":
                        (
                            f"I could not resolve the job title "
                            f"'{title_query}'. "
                            "Please provide another job title."
                        )
                }

            # =================================================
            # BUILD OPTIONS
            # =================================================

            options_text = "\n".join(

                f"{index + 1}. {title}"

                for index, title
                in enumerate(
                    suggested_titles
                )
            )

            print(
                "\nTITLE SUGGESTIONS:"
            )

            print(
                options_text
            )

            # =================================================
            # WAIT FOR USER
            #
            # DO NOT CALL INTERVIEWQUESTIONS YET
            # =================================================

            return {

                "waiting_for_user":
                    True,

                "awaiting_confirmation":
                    True,

                "confirmation_type":
                    "title",

                "original_title_input":
                    title_name,

                "suggested_titles":
                    suggested_titles,

                "title_name":
                    title_name,

                "requisition_number":
                    None,

                "interview_questions_result":
                    None,

                "result_summary":
                    (
                        f"I found multiple job titles "
                        f"matching '{title_query}'. "
                        f"Please select one:\n\n"
                        f"{options_text}"
                    ),

                "final_response":
                    (
                        f"I found multiple job titles "
                        f"matching '{title_query}'. "
                        f"Please select one:\n\n"
                        f"{options_text}"
                    )
            }

        # ====================================================
        # 11. EXACT TITLE MATCH
        # ====================================================

        if title_status == "EXACT":

            matched_title = title_match.get(
                "matched_title"
            )

            requisition_number = (
                title_match.get(
                    "requisition_number"
                )
            )

            print(
                "\nEXACT TITLE MATCH"
            )

            print(
                "Matched Title:",
                matched_title
            )

            print(
                "Requisition Number:",
                requisition_number
            )

            # ------------------------------------------------
            # Requisition number missing
            # ------------------------------------------------

            if not requisition_number:

                return {

                    "waiting_for_user":
                        True,

                    "awaiting_confirmation":
                        False,

                    "title_name":
                        (
                            [matched_title]
                            if matched_title
                            else title_name
                        ),

                    "requisition_number":
                        None,

                    "interview_questions_result":
                        None,

                    "final_response":
                        (
                            f"The job title "
                            f"'{matched_title or title_query}' "
                            "was found, but its requisition "
                            "number could not be determined."
                        )
                }

            # ------------------------------------------------
            # Store canonical title
            # ------------------------------------------------

            if matched_title:

                title_name = [

                    str(
                        matched_title
                    ).strip()

                ]

            print(
                "\nTITLE MATCHED:"
            )

            print(
                "Requested:",
                title_query
            )

            print(
                "Matched:",
                title_name
            )

            print(
                "Requisition Number:",
                requisition_number
            )

        # ====================================================
        # 12. UNKNOWN STATUS
        # ====================================================

        elif title_status not in (
            "EXACT",
            "SUGGEST"
        ):

            return {

                "waiting_for_user":
                    True,

                "title_name":
                    title_name,

                "requisition_number":
                    None,

                "interview_questions_result":
                    None,

                "final_response":
                    (
                        f"I could not resolve the job title "
                        f"'{title_query}'. "
                        "Please provide another job title."
                    )
            }

    # ========================================================
    # 13. SAFETY CHECK
    #
    # By this point we MUST have a requisition number.
    # ========================================================

    if not requisition_number:

        return {

            "waiting_for_user":
                True,

            "missing_information":
                [
                    "requisition_number"
                ],

            "title_name":
                title_name,

            "requisition_number":
                None,

            "interview_questions_result":
                None,

            "final_response":
                (
                    "I could not determine the requisition "
                    "number. Please provide a requisition "
                    "number or job title."
                )
        }

    # ========================================================
    # 14. CALL INTERVIEWQUESTIONS
    # ========================================================

    print(
        "\n========================================"
    )

    print(
        "CALLING INTERVIEWQUESTIONS"
    )

    print(
        "========================================"
    )

    interview_questions_parameters = {

        "AgentName":
            "interview_questions",

        "RequisitionNumberInt":
            str(
                requisition_number
            )
    }

    print(
        "\nINTERVIEW QUESTIONS PARAMETERS:"
    )

    print(
        json.dumps(
            interview_questions_parameters,
            indent=4,
            default=str
        )
    )

    # ========================================================
    # 15. BUILD INTERVIEWQUESTIONS BODY
    # ========================================================

    interview_questions_body = build_agent_body(

        "INTERVIEWQUESTIONS",

        interview_questions_parameters

    )

    print(
        "\nINTERVIEWQUESTIONS BODY:"
    )

    print(
        json.dumps(
            interview_questions_body,
            indent=4,
            default=str
        )
    )

    # ========================================================
    # 16. CALL INTERVIEWQUESTIONS
    # ========================================================

    try:

        interview_questions_result = call_agent(

            "INTERVIEWQUESTIONS",

            interview_questions_body

        )

    except Exception as e:

        print(
            "\nINTERVIEWQUESTIONS ERROR:"
        )

        print(
            str(e)
        )

        return {

            "waiting_for_user":
                False,

            "requisition_number":
                requisition_number,

            "title_name":
                title_name,

            "interview_questions_result":
                None,

            "final_response":
                (
                    "Failed to generate interview "
                    "questions: "
                    f"{str(e)}"
                )
        }

    # ========================================================
    # 17. PRINT RESULT
    # ========================================================

    print(
        "\n========================================"
    )

    print(
        "INTERVIEWQUESTIONS RESULT"
    )

    print(
        "========================================"
    )

    print(
        json.dumps(
            interview_questions_result,
            indent=4,
            default=str
        )
    )

    # ========================================================
    # 18. RETURN FINAL RESULT
    # ========================================================

    return {

        "interview_questions_result":
            interview_questions_result,

        "requisition_number":
            requisition_number,

        "title_name":
            title_name,

        "waiting_for_user":
            False,

        "awaiting_confirmation":
            False,

        "final_response":
            interview_questions_result
    }


# ============================================================
# MAIN ORCHESTRATOR
# ============================================================

def orchestrate(
    state: TaskState
):

    task_type = state.get(
        "task_type"
    )

    print(
        "\n========================================"
    )

    print(
        "ORCHESTRATOR"
    )

    print(
        "TASK:",
        task_type
    )

    print(
        "========================================"
    )

    if task_type == "SCREENING":

        return screening_flow(
            state
        )

    elif task_type == "LIST_INTERVIEWERS":

        return interviewer_list_flow(
            state
        )

    elif task_type == "CHECK_AVAILABILITY":

        return availability_flow(
            state
        )

    elif task_type == "SCHEDULE_INTERVIEW":

        return scheduling_flow(
            state
        )

    elif task_type == "SEND_EMAIL":

        return email_flow(
            state
        )

    elif task_type == "INTERVIEWQUESTIONS":
        return interview_questions(
            state
        )

    elif task_type == "LINKEDIN_JOB_DESC":

        return linkedin_job_desc_flow(
            state
        )

    raise ValueError(
        f"Unsupported task type: {task_type}"
    )


# ============================================================
# OPTIONAL EXTRACTION HELPERS
# ============================================================

def extract_job_application_ids(
    agent_result,
    candidate_names
):

    if not isinstance(
        agent_result,
        dict
    ):

        return []

    output = agent_result.get(
        "output"
    )

    if output is None:
        return []

    if isinstance(
        output,
        str
    ):

        output = safe_json_loads(
            output
        )

        if output is None:
            return []

    if not isinstance(
        output,
        dict
    ):

        return []

    result = output.get(
        "result",
        {}
    )

    if isinstance(
        result,
        str
    ):

        result = safe_json_loads(
            result
        )

        if result is None:
            return []

    if not isinstance(
        result,
        dict
    ):

        return []

    requisitions = result.get(
        "requisitions",
        []
    )

    if not isinstance(
        requisitions,
        list
    ):

        return []

    requested_names = {
        str(name).strip().lower()
        for name in normalize_list(
            candidate_names
        )
    }

    job_application_ids = []

    for candidate in requisitions:

        if not isinstance(
            candidate,
            dict
        ):

            continue

        candidate_name = candidate.get(
            "CandidateName"
        )

        if not candidate_name:
            continue

        if (
            str(candidate_name)
            .strip()
            .lower()
            in requested_names
        ):

            job_application_id = candidate.get(
                "JobApplicationId"
            )

            if job_application_id:

                value = str(
                    job_application_id
                )

                if value not in job_application_ids:

                    job_application_ids.append(
                        value
                    )

    return job_application_ids


# ============================================================
# EXTRACT CANDIDATE DATA
# ============================================================

def extract_candidate_data(
    agent_result,
    candidate_name
):

    if not isinstance(
        agent_result,
        dict
    ):

        return {}

    output = agent_result.get(
        "output"
    )

    if output is None:
        return {}

    if isinstance(
        output,
        str
    ):

        output = safe_json_loads(
            output
        )

        if output is None:
            return {}

    if not isinstance(
        output,
        dict
    ):

        return {}

    result = output.get(
        "result",
        {}
    )

    if isinstance(
        result,
        str
    ):

        result = safe_json_loads(
            result
        )

        if result is None:
            return {}

    if not isinstance(
        result,
        dict
    ):

        return {}

    requisitions = result.get(
        "requisitions",
        []
    )

    if not isinstance(
        requisitions,
        list
    ):

        return {}

    target_name = (
        str(candidate_name)
        .strip()
        .lower()
    )

    for candidate in requisitions:

        if not isinstance(
            candidate,
            dict
        ):

            continue

        candidate_name_from_api = (
            candidate.get(
                "CandidateName"
            )
        )

        if not candidate_name_from_api:
            continue

        if (
            str(candidate_name_from_api)
            .strip()
            .lower()
            ==
            target_name
        ):

            return {
                "candidate_name":
                    candidate_name_from_api,

                "email":
                    candidate.get(
                        "Email"
                    ),

                "jobApplicationId":
                    candidate.get(
                        "JobApplicationId"
                    )
            }

    return {}


# ============================================================
# EXTRACT INTERVIEWER EMAILS
# ============================================================

def extract_interviewer_emails(
    agent_result,
    interviewer_names
):

    interviewers = extract_all_interviewers(
        agent_result
    )

    requested_names = {
        str(name).strip().lower()
        for name in normalize_list(
            interviewer_names
        )
    }

    emails = []

    for interviewer in interviewers:

        display_name = str(
            interviewer.get(
                "actual_name",
                ""
            )
        ).strip().lower()

        work_email = interviewer.get(
            "email"
        )

        if (
            display_name
            in requested_names
            and
            work_email
        ):

            emails.append(
                work_email
            )

    return list(
        dict.fromkeys(
            emails
        )
    )
