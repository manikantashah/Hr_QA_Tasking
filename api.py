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
    Convert a value into a dictionary safely.

    Supported:

        dict
        JSON string containing an object

    Example:

        '{"status": "FOUND"}'

    becomes:

        {
            "status": "FOUND"
        }

    If the value cannot be converted to a dictionary,
    an empty dictionary is returned.
    """

    # --------------------------------------------------------
    # Already a dictionary
    # --------------------------------------------------------

    if isinstance(value, dict):

        return value

    # --------------------------------------------------------
    # JSON string
    # --------------------------------------------------------

    if isinstance(value, str):

        text = value.strip()

        if not text:

            return {}

        try:

            parsed = json.loads(text)

            if isinstance(parsed, dict):

                return parsed

        except json.JSONDecodeError:

            return {}

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
    """
    Save the current tasking conversation.

    Important:
    We keep only the state required to continue
    the current task.
    """

    if not isinstance(state, dict):

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
    """
    Save an HR Q&A clarification state.
    """

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
    """
    Completely remove the current conversation state.

    This is important after a task is successfully
    completed or cancelled.

    It prevents the next user request from accidentally
    continuing the previous interviewer/candidate confirmation.
    """

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
    """
    Remove temporary confirmation information.

    This is called after the user confirms a suggestion.

    Example:

        User:
            Charles Wood

        System:
            Charles Wood Devadoss Wood Fread
            Would you like to use this interviewer?

        User:
            yes

    After confirmation, these temporary fields should
    not remain active.
    """

    state["awaiting_confirmation"] = False

    state["waiting_for_user"] = False

    state["confirmation_type"] = None

    # Candidate suggestion

    state["suggested_candidate"] = None

    # Interviewer suggestion

    state["suggested_interviewer"] = None

    # Some implementations may use this name

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
    """
    Continue an existing HR Q&A conversation.
    """

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

        # ----------------------------------------------------
        # IMPORTANT:
        # Clear old state BEFORE processing new request.
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Clear old QA state.
        # ----------------------------------------------------

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
                "end_datetime"

            ]:

                value = (
                    conversation_result.get(
                        field
                    )
                )

                if value:

                    previous_state[
                        field
                    ] = value

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

                # If this is a normal clarification,
                # keep confirmation state if required.

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
                # IMPORTANT:
                #
                # The user has answered the previous confirmation.
                #
                # Clear temporary confirmation values before
                # running orchestration again.
                # -------------------------------------------------

                _reset_confirmation_state(
                    previous_state
                )

                # -------------------------------------------------
                # Run orchestration with the updated state.
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
                # If orchestration requires another user response,
                # preserve the state.
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

                    # ------------------------------------------------
                    # TASK COMPLETED.
                    #
                    # VERY IMPORTANT:
                    # Remove the old task state.
                    # The next request will be completely new.
                    # ------------------------------------------------

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

                    # =================================================
                    # CHANGED:
                    # final_response -> result_summary
                    # =================================================

                    "message":
                        previous_state.get(
                            "result_summary"
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
        #
        # If we reach here, there is no active conversation
        # waiting for confirmation.
        #
        # Therefore this request is treated as a NEW request.
        #
        # This is important for:
        #
        # Request 1:
        #   Charles Wood
        #
        # yes
        #
        # Request 2:
        #   Charles Wood Devadoss
        #
        # Request 2 must NOT inherit Request 1.
        #
        # ====================================================

        mode, routed = route_request(
            question
        )

        # ----------------------------------------------------
        # Make sure router output is a dictionary.
        # ----------------------------------------------------

        routed = _ensure_dict(
            routed
        )

        # ====================================================
        # 4. TASKING REQUEST
        # ====================================================

        if mode == "TASKING":

            # ------------------------------------------------
            # Completely fresh task state.
            # ------------------------------------------------

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

            # ------------------------------------------------
            # Add router information.
            # ------------------------------------------------

            state.update(
                routed
            )

            # ------------------------------------------------
            # Run orchestration.
            # ------------------------------------------------

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

                # =================================================
                # CHANGED:
                # final_response -> result_summary
                # =================================================

                "message":
                    state.get(
                        "result_summary"
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