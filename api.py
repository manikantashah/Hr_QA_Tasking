# ============================================================
# api.py
# Unified HR Q&A + HR Tasking API
# ============================================================

import json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from handler import getOutput
from unified_router import route_request
from orchestrator import orchestrate
from conversation import handle_conversation


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Unified HR Recruitment AI"
)


# ============================================================
# IN-MEMORY CONVERSATION STORE
# ============================================================
#
# POC only.
#
# Restarting the server clears this memory.
#
# For now the user does not need to send
# conversation_id.
#
# ============================================================

CONVERSATIONS = {}

CONVERSATION_ID = "default"


# ============================================================
# REQUEST MODEL
# ============================================================

class QuestionRequest(BaseModel):

    question: str


# ============================================================
# SAFE JSON / DICT HELPER
# ============================================================

def _ensure_dict(value):
    """
    Safely convert a value into a dictionary.

    Handles:
        - dict
        - JSON string containing one object
        - JSON string containing extra/trailing content
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
    # JSON string
    # --------------------------------------------------------

    if isinstance(
        value,
        str
    ):

        text = value.strip()

        if not text:

            return {}

        # ----------------------------------------------------
        # First try normal JSON parsing
        # ----------------------------------------------------

        try:

            parsed = json.loads(
                text
            )

            if isinstance(
                parsed,
                dict
            ):

                return parsed

        except json.JSONDecodeError:

            pass

        # ----------------------------------------------------
        # Handle extra data after first JSON object
        # ----------------------------------------------------

        try:

            decoder = json.JSONDecoder()

            parsed, _ = decoder.raw_decode(
                text
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
# HOME
# ============================================================

@app.get("/")
def home():

    return {
        "message":
            "Unified HR Recruitment AI is running"
    }


# ============================================================
# SAVE TASKING STATE
# ============================================================

def _save_tasking_state(
    conversation_id,
    state
):

    if not isinstance(
        state,
        dict
    ):

        return

    state["conversation_mode"] = "TASKING"

    CONVERSATIONS[
        conversation_id
    ] = state


# ============================================================
# SAVE QA STATE
# ============================================================

def _save_qa_state(
    conversation_id,
    response
):

    response = _ensure_dict(
        response
    )

    CONVERSATIONS[
        conversation_id
    ] = {

        "conversation_mode":
            "QA",

        "original_question":
            response.get(
                "original_question"
            ),

        "requested_candidate":
            response.get(
                "requested_candidate"
            ),

        "suggested_candidate":
            response.get(
                "suggested_candidate"
            ),

        "awaiting_candidate":
            response.get(
                "awaiting_candidate",
                False
            )
    }


# ============================================================
# CLEAR CONVERSATION
# ============================================================

def _clear_conversation(
    conversation_id
):

    CONVERSATIONS.pop(
        conversation_id,
        None
    )


# ============================================================
# RESET OLD TASKING CONFIRMATION STATE
# ============================================================

def _reset_confirmation_state(
    state
):

    state["awaiting_confirmation"] = False

    state["waiting_for_user"] = False

    state["confirmation_type"] = None

    # Candidate suggestion

    state["suggested_candidate"] = None

    # Interviewer suggestion

    state["suggested_interviewer"] = None

    state["suggested_interviewers"] = None

    return state


# ============================================================
# QA CONVERSATION RESUME
# ============================================================

def _resume_qa(
    previous_state,
    question,
    conversation_id
):

    previous_state = (
        previous_state
        if isinstance(
            previous_state,
            dict
        )
        else {}
    )

    requested_candidate = previous_state.get(
        "requested_candidate"
    )

    suggested_candidate = previous_state.get(
        "suggested_candidate"
    )

    original_question = previous_state.get(
        "original_question"
    )

    normalized = (
        question
        .strip()
        .lower()
    )

    # ========================================================
    # USER CONFIRMED CANDIDATE
    # ========================================================

    if normalized in {

        "yes",
        "y",
        "yeah",
        "yep",
        "correct",
        "yes this candidate",
        "yes that's correct",
        "yes thats correct"

    }:

        if not all([

            requested_candidate,
            suggested_candidate,
            original_question

        ]):

            _clear_conversation(
                conversation_id
            )

            raise RuntimeError(
                "The previous HR candidate suggestion "
                "could not be recovered."
            )

        corrected_question = (
            original_question.replace(
                requested_candidate,
                suggested_candidate
            )
        )

        _clear_conversation(
            conversation_id
        )

        response = getOutput(
            corrected_question
        )

        response_dict = _ensure_dict(
            response
        )

        if (
            response_dict.get(
                "status"
            )
            ==
            "WAITING_FOR_USER"
        ):

            _save_qa_state(
                conversation_id,
                response_dict
            )

        return {

            "question":
                corrected_question,

            "status":
                "COMPLETED",

            "mode":
                "QA",

            "message":
                response
        }

    # ========================================================
    # USER REJECTED CANDIDATE
    # ========================================================

    if normalized in {

        "no",
        "n",
        "nope",
        "not this one",
        "wrong"

    }:

        previous_state[
            "awaiting_candidate"
        ] = True

        _save_qa_state(
            conversation_id,
            previous_state
        )

        return {

            "question":
                question,

            "status":
                "WAITING_FOR_USER",

            "mode":
                "QA",

            "state":
                previous_state,

            "message":
                "Please provide the correct candidate name."
        }

    # ========================================================
    # USER PROVIDED CORRECT CANDIDATE
    # ========================================================

    if previous_state.get(
        "awaiting_candidate"
    ):

        if (
            not original_question
            or
            not requested_candidate
        ):

            _clear_conversation(
                conversation_id
            )

            raise RuntimeError(
                "The previous HR candidate question "
                "could not be recovered."
            )

        corrected_question = (
            original_question.replace(
                requested_candidate,
                question
            )
        )

        _clear_conversation(
            conversation_id
        )

        response = getOutput(
            corrected_question
        )

        response_dict = _ensure_dict(
            response
        )

        if (
            response_dict.get(
                "status"
            )
            ==
            "WAITING_FOR_USER"
        ):

            _save_qa_state(
                conversation_id,
                response_dict
            )

        return {

            "question":
                corrected_question,

            "status":
                "COMPLETED",

            "mode":
                "QA",

            "message":
                response
        }

    return None


# ============================================================
# EXECUTE
# ============================================================

@app.post("/execute")
def execute(
    request: QuestionRequest
):

    try:

        # ====================================================
        # VALIDATE QUESTION
        # ====================================================

        question = (
            request.question
            .strip()
        )

        if not question:

            raise HTTPException(

                status_code=400,

                detail=
                    "Question cannot be empty."
            )

        # ====================================================
        # CONVERSATION ID
        # ====================================================

        conversation_id = (
            CONVERSATION_ID
        )

        previous_state = (
            CONVERSATIONS.get(
                conversation_id
            )
        )

        # ====================================================
        # 1. CONTINUE EXISTING TASKING CONVERSATION
        # ====================================================

        if (

            previous_state

            and

            previous_state.get(
                "conversation_mode"
            )
            ==
            "TASKING"

            and

            (
                previous_state.get(
                    "waiting_for_user",
                    False
                )

                or

                previous_state.get(
                    "awaiting_confirmation",
                    False
                )
            )

        ):

            conversation_result = (
                handle_conversation(
                    previous_state,
                    question
                )
            )

            conversation_result = _ensure_dict(
                conversation_result
            )

            print(
                "\n========================================"
            )

            print(
                "CONVERSATION RESULT"
            )

            print(
                json.dumps(
                    conversation_result,
                    indent=4,
                    default=str
                )
            )

            print(
                "========================================"
            )

            action = (
                conversation_result.get(
                    "action"
                )
            )

            # =================================================
            # UPDATE TASK VALUES
            # =================================================

            for field in [

                "candidate_name",
                "requisition_number",
                "date",
                "start_datetime",
                "end_datetime",
                "title_name"

            ]:

                value = (
                    conversation_result.get(
                        field
                    )
                )

                if value is not None:

                    if value != "":

                        previous_state[
                            field
                        ] = value

            # =================================================
            # IMPORTANT TITLE UPDATE
            # =================================================
            #
            # If the user supplied a NEW TITLE:
            #
            #     Site Engineer (Trainee)
            #
            # and there is NO selected requisition number,
            # then requisition_number must be cleared.
            #
            # But if the user selected an option:
            #
            #     1
            #
            # conversation.py returns:
            #
            #     title_name = ["Site Engineer"]
            #     requisition_number = "21"
            #
            # In that case DO NOT clear 21.
            #
            # =================================================

            new_title = (
                conversation_result.get(
                    "title_name"
                )
            )

            new_requisition_number = (
                conversation_result.get(
                    "requisition_number"
                )
            )

            if new_title:

                previous_state[
                    "title_name"
                ] = new_title

                # -------------------------------------------------
                # Only clear requisition number when the title was
                # supplied WITHOUT a selected requisition.
                # -------------------------------------------------

                if (
                    new_requisition_number is None
                    or
                    new_requisition_number == ""
                ):

                    previous_state[
                        "requisition_number"
                    ] = None

            # =================================================
            # UPDATE INTERVIEWER NAMES
            # =================================================

            interviewer_names = (
                conversation_result.get(
                    "interviewer_names"
                )
            )

            if interviewer_names:

                previous_state[
                    "interviewer_names"
                ] = interviewer_names

            # =================================================
            # CANCEL
            # =================================================

            if action == "CANCEL":

                _clear_conversation(
                    conversation_id
                )

                return {

                    "question":
                        question,

                    "status":
                        "CANCELLED",

                    "mode":
                        "TASKING",

                    "message":
                        (
                            conversation_result.get(
                                "message"
                            )
                            or
                            "The current task has been cancelled."
                        )
                }

            # =================================================
            # WAIT
            # =================================================

            if action == "WAIT":

                previous_state[
                    "waiting_for_user"
                ] = True

                if (
                    "awaiting_confirmation"
                    not in previous_state
                ):

                    previous_state[
                        "awaiting_confirmation"
                    ] = False

                _save_tasking_state(
                    conversation_id,
                    previous_state
                )

                return {

                    "question":
                        question,

                    "status":
                        "WAITING_FOR_USER",

                    "mode":
                        "TASKING",

                    "state":
                        previous_state,

                    "message":
                        conversation_result.get(
                            "message"
                        )
                }

            # =================================================
            # CONFIRM / CORRECT / UPDATE
            # =================================================

            if action in {

                "CONFIRM",
                "CORRECT",
                "UPDATE"

            }:

                # -------------------------------------------------
                # Clear temporary confirmation flags.
                # -------------------------------------------------

                _reset_confirmation_state(
                    previous_state
                )

                # -------------------------------------------------
                # DEBUG STATE
                # -------------------------------------------------

                print(
                    "\n========================================"
                )

                print(
                    "STATE BEFORE ORCHESTRATION"
                )

                print(
                    json.dumps(
                        {
                            "title_name":
                                previous_state.get(
                                    "title_name"
                                ),

                            "requisition_number":
                                previous_state.get(
                                    "requisition_number"
                                ),

                            "candidate_name":
                                previous_state.get(
                                    "candidate_name"
                                ),

                            "interviewer_names":
                                previous_state.get(
                                    "interviewer_names"
                                ),

                            "start_datetime":
                                previous_state.get(
                                    "start_datetime"
                                ),

                            "end_datetime":
                                previous_state.get(
                                    "end_datetime"
                                )
                        },
                        indent=4,
                        default=str
                    )
                )

                print(
                    "========================================"
                )

                # -------------------------------------------------
                # Run orchestration again.
                # -------------------------------------------------

                orchestration_result = (
                    orchestrate(
                        previous_state
                    )
                )

                orchestration_result = _ensure_dict(
                    orchestration_result
                )

                previous_state.update(
                    orchestration_result
                )

                # -------------------------------------------------
                # If another response is required,
                # preserve state.
                # -------------------------------------------------

                if (

                    previous_state.get(
                        "waiting_for_user",
                        False
                    )

                    or

                    previous_state.get(
                        "awaiting_confirmation",
                        False
                    )

                ):

                    _save_tasking_state(
                        conversation_id,
                        previous_state
                    )

                else:

                    _clear_conversation(
                        conversation_id
                    )

                return {

                    "question":
                        question,

                    "task_type":
                        previous_state.get(
                            "task_type"
                        ),

                    "status":
                        (
                            "WAITING_FOR_USER"
                            if
                            (
                                previous_state.get(
                                    "waiting_for_user",
                                    False
                                )
                                or
                                previous_state.get(
                                    "awaiting_confirmation",
                                    False
                                )
                            )
                            else
                            "COMPLETED"
                        ),

                    "mode":
                        "TASKING",

                    "state":
                        previous_state,

                    "message":
                        (
                            previous_state.get(
                                "result_summary"
                            )
                            or
                            previous_state.get(
                                "final_response"
                            )
                        )
                }

        # ====================================================
        # 2. CONTINUE EXISTING QA CONVERSATION
        # ====================================================

        if (

            previous_state

            and

            previous_state.get(
                "conversation_mode"
            )
            ==
            "QA"

        ):

            resumed = _resume_qa(

                previous_state,
                question,
                conversation_id
            )

            if resumed is not None:

                return resumed

        # ====================================================
        # 3. NEW REQUEST
        # ====================================================

        mode, routed = route_request(
            question
        )

        routed = _ensure_dict(
            routed
        )

        # ====================================================
        # 4. TASKING REQUEST
        # ====================================================

        if mode == "TASKING":

            state = {

                "question":
                    question,

                "conversation_mode":
                    "TASKING",

                "waiting_for_user":
                    False,

                "awaiting_confirmation":
                    False,

                "confirmation_type":
                    None,

                "suggested_candidate":
                    None,

                "suggested_interviewer":
                    None,

                "suggested_interviewers":
                    None

            }

            state.update(
                routed
            )

            orchestration_result = (
                orchestrate(
                    state
                )
            )

            orchestration_result = _ensure_dict(
                orchestration_result
            )

            state.update(
                orchestration_result
            )

            # =================================================
            # WAITING FOR USER
            # =================================================

            if (

                state.get(
                    "waiting_for_user",
                    False
                )

                or

                state.get(
                    "awaiting_confirmation",
                    False
                )

            ):

                _save_tasking_state(
                    conversation_id,
                    state
                )

            # =================================================
            # TASK COMPLETED
            # =================================================

            else:

                _clear_conversation(
                    conversation_id
                )

            return {

                "question":
                    question,

                "mode":
                    "TASKING",

                "task_type":
                    state.get(
                        "task_type"
                    ),

                "route_reason":
                    state.get(
                        "route_reason"
                    ),

                "status":
                    (
                        "WAITING_FOR_USER"
                        if
                        (
                            state.get(
                                "waiting_for_user",
                                False
                            )
                            or
                            state.get(
                                "awaiting_confirmation",
                                False
                            )
                        )
                        else
                        "COMPLETED"
                    ),

                "state":
                    state,

                "message":
                    (
                        state.get(
                            "result_summary"
                        )
                        or
                        state.get(
                            "final_response"
                        )
                    )
            }

        # ====================================================
        # 5. HR Q&A REQUEST
        # ====================================================

        response = getOutput(
            question
        )

        response_dict = _ensure_dict(
            response
        )

        # ====================================================
        # Q&A WAITING FOR USER
        # ====================================================

        if (
            response_dict.get(
                "status"
            )
            ==
            "WAITING_FOR_USER"
        ):

            _save_qa_state(
                conversation_id,
                response_dict
            )

            return {

                "question":
                    question,

                "mode":
                    "QA",

                "status":
                    "WAITING_FOR_USER",

                "state":
                    response_dict,

                "message":
                    response_dict.get(
                        "message"
                    )
            }

        # ====================================================
        # Q&A COMPLETED
        # ====================================================

        _clear_conversation(
            conversation_id
        )

        return {

            "question":
                question,

            "mode":
                "QA",

            "status":
                "COMPLETED",

            "message":
                response
        }

    # ========================================================
    # HTTP EXCEPTION
    # ========================================================

    except HTTPException:

        raise

    # ========================================================
    # GENERAL ERROR
    # ========================================================

    except Exception as exc:

        print(
            "\nERROR:"
        )

        print(
            str(exc)
        )

        raise HTTPException(

            status_code=500,

            detail=str(
                exc
            )

        ) from exc
