# ============================================================
# conversation.py
# ============================================================

import json

from llm import llm


# ============================================================
# HANDLE CONVERSATION RESPONSE
# ============================================================

def handle_conversation(
    previous_state,
    user_message
):

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

{json.dumps(previous_state, indent=4, default=str)}

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

    response = llm.invoke(
        prompt
    )

    content = response.content.strip()

    # Remove markdown fences if the model adds them
    if content.startswith("```"):

        content = content.replace(
            "```json",
            ""
        )

        content = content.replace(
            "```",
            ""
        )

        content = content.strip()

    return json.loads(
        content
    )