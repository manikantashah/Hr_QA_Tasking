

import subprocess
import os
import json
import requests
import time
import sys
from dotenv import load_dotenv
from generate_token import get_access_token
load_dotenv()




# ============================================================
# BASE URL
# ============================================================

BASE_URL = os.getenv("BASE_URL")


# ============================================================
# GET ACCESS TOKEN
# ============================================================

def get_bearer_token():

    print("\nGenerating fresh access token...")

    token = get_access_token()

    if not token:
        raise RuntimeError(
            "Access token was not returned."
        )

    print("Access token extracted successfully.")
    print("Token length:", len(token))

    return token


# ============================================================
# 3. CALL ORACLE AI AGENT
# ============================================================

def call_agent(
    agent_name: str,
    body: dict,
    max_attempts: int = 70
):

    print(
        "\n========================================"
    )

    print(
        "CALLING ORACLE AGENT"
    )

    print(
        "Agent:",
        agent_name
    )

    print(
        "========================================"
    )

    # ========================================================
    # 1. Generate fresh bearer token
    # ========================================================

    token = get_access_token()

    # ========================================================
    # 2. Headers
    # ========================================================

    headers = {

        "Authorization":
            f"Bearer {token}",

        "Content-Type":
            "application/json",

        "Accept":
            "application/json"
    }

    # ========================================================
    # 3. POST URL
    # ========================================================

    post_url = (
        f"{BASE_URL}"
        f"/api/fusion-ai/orchestrator/agent/v2/"
        f"{agent_name}/invokeAsync"
    )

    print(
        "\nPOST URL:"
    )

    print(
        post_url
    )

    # ========================================================
    # 4. POST BODY
    # ========================================================

    print(
        "\nPOST BODY:"
    )

    print(
        json.dumps(
            body,
            indent=4
        )
    )

    # ========================================================
    # 5. POST invokeAsync
    # ========================================================

    response = requests.post(
        post_url,
        headers=headers,
        json=body,
        timeout=60
    )

    print(
        "\nInvoke Status Code:",
        response.status_code
    )

    # ========================================================
    # 6. Check POST response
    # ========================================================

    if response.status_code != 202:

        print(
            "\nAgent invocation failed."
        )

        print(
            "Response:"
        )

        print(
            response.text
        )

        raise RuntimeError(
            f"Agent invocation failed. "
            f"HTTP {response.status_code}"
        )

    # ========================================================
    # 7. Get jobId
    # ========================================================

    invoke_result = response.json()

    print(
        "\nInvoke Response:"
    )

    print(
        json.dumps(
            invoke_result,
            indent=4
        )
    )

    job_id = invoke_result.get(
        "jobId"
    )

    if not job_id:

        raise RuntimeError(
            "jobId not found in invoke response."
        )

    print(
        "\nJob ID:"
    )

    print(
        job_id
    )

    # ========================================================
    # 8. Build GET status URL
    # ========================================================

    get_url = (
        f"{BASE_URL}"
        f"/api/fusion-ai/orchestrator/agent/v2/"
        f"{agent_name}/status/{job_id}"
    )

    print(
        "\nGET URL:"
    )

    print(
        get_url
    )

    # ========================================================
    # 9. Poll status
    # ========================================================

    for attempt in range(
        1,
        max_attempts + 1
    ):

        print(
            f"\nChecking status..."
            f" Attempt {attempt}"
        )

        # ----------------------------------------------------
        # GET status
        # ----------------------------------------------------

        status_response = requests.get(
            get_url,
            headers=headers,
            timeout=60
        )

        # ----------------------------------------------------
        # Check GET response
        # ----------------------------------------------------

        if status_response.status_code != 200:

            print(
                "Status API failed:",
                status_response.status_code
            )

            print(
                status_response.text
            )

            raise RuntimeError(
                "Status API failed."
            )

        # ----------------------------------------------------
        # Convert response to JSON
        # ----------------------------------------------------

        status_result = (
            status_response.json()
        )

        # ----------------------------------------------------
        # Get current status
        # ----------------------------------------------------

        current_status = (
            status_result.get(
                "status"
            )
        )

        print(
            "Current Status:",
            current_status
        )

        # ====================================================
        # COMPLETE
        # ====================================================

        if current_status == "COMPLETE":

            print(
                "\n========================================"
            )

            print(
                "AGENT COMPLETED"
            )

            print(
                "========================================"
            )

            agent_output = (
                status_result.get(
                    "output"
                )
            )

            # ------------------------------------------------
            # Output is null
            # ------------------------------------------------

            if agent_output is None:

                print(
                    "Agent output is null."
                )

                return status_result

            # ------------------------------------------------
            # Output may be JSON stored as a string
            # ------------------------------------------------

            if isinstance(
                agent_output,
                str
            ):

                try:

                    agent_output = json.loads(
                        agent_output
                    )

                except json.JSONDecodeError:

                    # It is just normal text
                    pass

            # ------------------------------------------------
            # Print agent output
            # ------------------------------------------------

            print(
                "\nAgent Output:"
            )

            if isinstance(
                agent_output,
                (dict, list)
            ):

                print(
                    json.dumps(
                        agent_output,
                        indent=4
                    )
                )

            else:

                print(
                    agent_output
                )

            # ------------------------------------------------
            # Return full Oracle response
            # ------------------------------------------------

            return status_result

        # ====================================================
        # FAILED
        # ====================================================

        if current_status in [
            "FAILED",
            "ERROR",
            "CANCELLED"
        ]:

            print(
                "\n========================================"
            )

            print(
                "AGENT EXECUTION FAILED"
            )

            print(
                "========================================"
            )

            print(
                "Error:",
                status_result.get(
                    "error"
                )
            )

            print(
                "\nComplete Response:"
            )

            print(
                json.dumps(
                    status_result,
                    indent=4
                )
            )

            raise RuntimeError(
                f"Agent execution failed: "
                f"{status_result}"
            )

        # ====================================================
        # STILL RUNNING
        # ====================================================

        print(
            "Agent is still running..."
        )

        time.sleep(2)

    # ========================================================
    # 10. TIMEOUT
    # ========================================================

    raise TimeoutError(
        f"Agent did not complete within "
        f"{max_attempts} attempts."
    )
