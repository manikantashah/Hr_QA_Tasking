# ============================================================
# oci_test.py
# ============================================================

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

    print(
        "\nGenerating fresh access token..."
    )

    token_start = time.perf_counter()

    token = get_access_token()

    token_time = (
        time.perf_counter()
        - token_start
    )

    print(
        f"[TIMING] ACCESS TOKEN: "
        f"{token_time:.2f} seconds"
    )

    if not token:
        raise RuntimeError(
            "Access token was not returned."
        )

    print(
        "Access token extracted successfully."
    )

    print(
        "Token length:",
        len(token)
    )

    return token


# ============================================================
# CALL ORACLE AI AGENT
# ============================================================

def call_agent(
    agent_name: str,
    body: dict,
    max_attempts: int = 70,
    bearer_token: str = None
):

    # ========================================================
    # TOTAL START TIME
    # ========================================================

    total_start = time.perf_counter()

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
    # 1. GET BEARER TOKEN
    # ========================================================

    if bearer_token:

        # ----------------------------------------------------
        # Reuse existing token
        # ----------------------------------------------------

        token = bearer_token

        print(
            f"\n[TIMING] {agent_name} "
            f"| ACCESS TOKEN: REUSED"
        )

        print(
            "Using existing bearer token."
        )

    else:

        # ----------------------------------------------------
        # Generate fresh token
        # ----------------------------------------------------

        print(
            "\nGenerating fresh access token..."
        )

        token_start = time.perf_counter()

        token = get_access_token()

        token_time = (
            time.perf_counter()
            - token_start
        )

        print(
            f"\n[TIMING] {agent_name} "
            f"| ACCESS TOKEN: "
            f"{token_time:.2f} seconds"
        )

    # ========================================================
    # TOKEN VALIDATION
    # ========================================================

    if not token:

        raise RuntimeError(
            "Access token was not returned."
        )

    # ========================================================
    # 2. HEADERS
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

    print(
        f"\n[TIMING] {agent_name} "
        f"| Starting invokeAsync..."
    )

    post_start = time.perf_counter()

    try:

        response = requests.post(
            post_url,
            headers=headers,
            json=body,
            timeout=60
        )

    except requests.exceptions.Timeout as e:

        post_time = (
            time.perf_counter()
            - post_start
        )

        total_time = (
            time.perf_counter()
            - total_start
        )

        print(
            f"[TIMING] {agent_name} "
            f"| invokeAsync TIMEOUT: "
            f"{post_time:.2f} seconds"
        )

        print(
            f"[TIMING] {agent_name} "
            f"| TOTAL TIME: "
            f"{total_time:.2f} seconds"
        )

        print(
            "\ninvokeAsync request timed out."
        )

        raise RuntimeError(
            f"invokeAsync request timed out: {e}"
        )

    except requests.exceptions.RequestException as e:

        post_time = (
            time.perf_counter()
            - post_start
        )

        total_time = (
            time.perf_counter()
            - total_start
        )

        print(
            f"[TIMING] {agent_name} "
            f"| invokeAsync REQUEST ERROR: "
            f"{post_time:.2f} seconds"
        )

        print(
            f"[TIMING] {agent_name} "
            f"| TOTAL TIME: "
            f"{total_time:.2f} seconds"
        )

        print(
            "\nRequest Exception:"
        )

        print(
            str(e)
        )

        raise

    post_time = (
        time.perf_counter()
        - post_start
    )

    print(
        f"[TIMING] {agent_name} "
        f"| invokeAsync POST: "
        f"{post_time:.2f} seconds"
    )

    print(
        "\nInvoke Status Code:",
        response.status_code
    )

    # ========================================================
    # 6. CHECK POST RESPONSE
    # ========================================================

    if response.status_code != 202:

        total_time = (
            time.perf_counter()
            - total_start
        )

        print(
            "\n========================================"
        )

        print(
            "AGENT INVOCATION FAILED"
        )

        print(
            "========================================"
        )

        print(
            "Agent:",
            agent_name
        )

        print(
            "HTTP Status:",
            response.status_code
        )

        print(
            f"[TIMING] {agent_name} "
            f"| FAILED TOTAL: "
            f"{total_time:.2f} seconds"
        )

        # ----------------------------------------------------
        # RESPONSE HEADERS
        # ----------------------------------------------------

        print(
            "\nResponse Headers:"
        )

        try:

            print(
                json.dumps(
                    dict(
                        response.headers
                    ),
                    indent=4,
                    default=str
                )
            )

        except Exception:

            print(
                response.headers
            )

        # ----------------------------------------------------
        # RESPONSE BODY
        # ----------------------------------------------------

        print(
            "\nResponse Body:"
        )

        print(
            response.text
        )

        # ----------------------------------------------------
        # TRY JSON RESPONSE
        # ----------------------------------------------------

        try:

            error_json = response.json()

            print(
                "\nResponse JSON:"
            )

            print(
                json.dumps(
                    error_json,
                    indent=4,
                    default=str
                )
            )

        except Exception:

            print(
                "\nResponse is not JSON."
            )

        raise RuntimeError(
            f"Agent invocation failed. "
            f"HTTP {response.status_code}"
        )

    # ========================================================
    # 7. GET jobId
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
    # 8. BUILD GET STATUS URL
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
    # 9. POLL STATUS
    # ========================================================

    polling_start = time.perf_counter()

    completed_attempt = None

    for attempt in range(
        1,
        max_attempts + 1
    ):

        print(
            f"\nChecking status..."
            f" Attempt {attempt}"
        )

        # ====================================================
        # START TIMER FOR STATUS REQUEST
        # ====================================================

        status_start = time.perf_counter()

        try:

            status_response = requests.get(
                get_url,
                headers=headers,
                timeout=60
            )

        except requests.exceptions.Timeout as e:

            status_time = (
                time.perf_counter()
                - status_start
            )

            total_time = (
                time.perf_counter()
                - total_start
            )

            print(
                f"[TIMING] {agent_name} "
                f"| STATUS GET Attempt {attempt} "
                f"TIMEOUT: "
                f"{status_time:.2f} seconds"
            )

            print(
                f"[TIMING] {agent_name} "
                f"| TOTAL TIME: "
                f"{total_time:.2f} seconds"
            )

            print(
                "\nStatus API request timed out:"
            )

            print(
                str(e)
            )

            raise RuntimeError(
                f"Status API request timed out: {e}"
            )

        except requests.exceptions.RequestException as e:

            status_time = (
                time.perf_counter()
                - status_start
            )

            total_time = (
                time.perf_counter()
                - total_start
            )

            print(
                f"[TIMING] {agent_name} "
                f"| STATUS GET Attempt {attempt} "
                f"REQUEST ERROR: "
                f"{status_time:.2f} seconds"
            )

            print(
                f"[TIMING] {agent_name} "
                f"| TOTAL TIME: "
                f"{total_time:.2f} seconds"
            )

            print(
                "\nStatus Request Exception:"
            )

            print(
                str(e)
            )

            raise

        status_time = (
            time.perf_counter()
            - status_start
        )

        print(
            f"[TIMING] {agent_name} "
            f"| STATUS GET Attempt {attempt}: "
            f"{status_time:.2f} seconds"
        )

        # ====================================================
        # CHECK GET RESPONSE
        # ====================================================

        if status_response.status_code != 200:

            total_time = (
                time.perf_counter()
                - total_start
            )

            print(
                "\n========================================"
            )

            print(
                "STATUS API FAILED"
            )

            print(
                "========================================"
            )

            print(
                "Agent:",
                agent_name
            )

            print(
                "Attempt:",
                attempt
            )

            print(
                "Status Code:",
                status_response.status_code
            )

            print(
                f"[TIMING] {agent_name} "
                f"| FAILED TOTAL: "
                f"{total_time:.2f} seconds"
            )

            print(
                "\nStatus Response Headers:"
            )

            try:

                print(
                    json.dumps(
                        dict(
                            status_response.headers
                        ),
                        indent=4,
                        default=str
                    )
                )

            except Exception:

                print(
                    status_response.headers
                )

            print(
                "\nStatus Response Body:"
            )

            print(
                status_response.text
            )

            raise RuntimeError(
                "Status API failed."
            )

        # ====================================================
        # CONVERT RESPONSE TO JSON
        # ====================================================

        status_result = (
            status_response.json()
        )

        # ====================================================
        # GET CURRENT STATUS
        # ====================================================

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

            completed_attempt = attempt

            polling_time = (
                time.perf_counter()
                - polling_start
            )

            total_time = (
                time.perf_counter()
                - total_start
            )

            print(
                "\n========================================"
            )

            print(
                "AGENT COMPLETED"
            )

            print(
                "========================================"
            )

            print(
                f"[TIMING] {agent_name} "
                f"| POLLING TIME: "
                f"{polling_time:.2f} seconds"
            )

            print(
                f"[TIMING] {agent_name} "
                f"| TOTAL CALL TIME: "
                f"{total_time:.2f} seconds"
            )

            print(
                f"[TIMING] {agent_name} "
                f"| TOTAL ATTEMPTS: "
                f"{completed_attempt}"
            )

            # ------------------------------------------------
            # OUTPUT
            # ------------------------------------------------

            agent_output = (
                status_result.get(
                    "output"
                )
            )

            # ------------------------------------------------
            # OUTPUT IS NULL
            # ------------------------------------------------

            if agent_output is None:

                print(
                    "Agent output is null."
                )

                return status_result

            # ------------------------------------------------
            # OUTPUT MAY BE JSON STRING
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

                    # Normal text
                    pass

            # ------------------------------------------------
            # PRINT AGENT OUTPUT
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
            # RETURN FULL ORACLE RESPONSE
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

            total_time = (
                time.perf_counter()
                - total_start
            )

            polling_time = (
                time.perf_counter()
                - polling_start
            )

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
                f"[TIMING] {agent_name} "
                f"| POLLING TIME: "
                f"{polling_time:.2f} seconds"
            )

            print(
                f"[TIMING] {agent_name} "
                f"| TOTAL TIME: "
                f"{total_time:.2f} seconds"
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

        # ====================================================
        # POLLING SLEEP
        # ====================================================

        sleep_start = time.perf_counter()

        # Keep polling interval at 1 second
        time.sleep(1)

        sleep_time = (
            time.perf_counter()
            - sleep_start
        )

        print(
            f"[TIMING] {agent_name} "
            f"| POLLING SLEEP: "
            f"{sleep_time:.2f} seconds"
        )

    # ========================================================
    # 10. TIMEOUT
    # ========================================================

    total_time = (
        time.perf_counter()
        - total_start
    )

    polling_time = (
        time.perf_counter()
        - polling_start
    )

    print(
        "\n========================================"
    )

    print(
        "AGENT TIMEOUT"
    )

    print(
        "========================================"
    )

    print(
        f"[TIMING] {agent_name} "
        f"| POLLING TIME: "
        f"{polling_time:.2f} seconds"
    )

    print(
        f"[TIMING] {agent_name} "
        f"| TOTAL TIME: "
        f"{total_time:.2f} seconds"
    )

    print(
        f"[TIMING] {agent_name} "
        f"| MAX ATTEMPTS: "
        f"{max_attempts}"
    )

    raise TimeoutError(
        f"Agent did not complete within "
        f"{max_attempts} attempts."
    )
