
# ============================================================
# generate_token.py
# ============================================================

import time
import jwt
import requests
import os

from requests.auth import HTTPBasicAuth


# ============================================================
# GET ACCESS TOKEN
# ============================================================

def get_access_token():

    print("\nGenerating fresh access token...")

    # --------------------------------------------------------
    # Environment variables
    # --------------------------------------------------------

    IDCS_TOKEN_URL = os.getenv("IDCS_TOKEN_URL")
    CLIENT_ID = os.getenv("CLIENT_ID")
    SCOPE = os.getenv("SCOPE")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    FUSION_USERNAME = os.getenv("FUSION_USERNAME")
    PRIVATE_KEY_FILE = os.getenv("PRIVATE_KEY_FILE")

    # --------------------------------------------------------
    # Validate environment variables
    # --------------------------------------------------------

    required_variables = {
        "IDCS_TOKEN_URL": IDCS_TOKEN_URL,
        "CLIENT_ID": CLIENT_ID,
        "SCOPE": SCOPE,
        "CLIENT_SECRET": CLIENT_SECRET,
        "FUSION_USERNAME": FUSION_USERNAME,
        "PRIVATE_KEY_FILE": PRIVATE_KEY_FILE,
    }

    missing_variables = [
        name
        for name, value in required_variables.items()
        if not value
    ]

    if missing_variables:
        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(missing_variables)
        )

    # --------------------------------------------------------
    # Read private key
    # --------------------------------------------------------

    if not os.path.isfile(PRIVATE_KEY_FILE):
        raise FileNotFoundError(
            f"Private key file not found: {PRIVATE_KEY_FILE}"
        )

    with open(PRIVATE_KEY_FILE, "r") as f:
        private_key = f.read()

    # --------------------------------------------------------
    # Create JWT payload
    # --------------------------------------------------------

    now = int(time.time())

    payload = {
        "iss": CLIENT_ID,
        "sub": FUSION_USERNAME,
        "aud": "https://identity.oraclecloud.com/",
        "iat": now,
        "exp": now + 86400
    }

    # --------------------------------------------------------
    # Generate JWT assertion
    # --------------------------------------------------------

    assertion = jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={
            "kid": "agent_api_cert"
        }
    )

    # --------------------------------------------------------
    # Request access token
    # --------------------------------------------------------

    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
        "scope": SCOPE
    }

    response = requests.post(
        IDCS_TOKEN_URL,
        data=data,
        auth=HTTPBasicAuth(
            CLIENT_ID,
            CLIENT_SECRET
        ),
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
        timeout=30
    )

    print("Token API Status:", response.status_code)

    # --------------------------------------------------------
    # Validate response
    # --------------------------------------------------------

    if response.status_code != 200:
        raise RuntimeError(
            f"Token generation failed.\n"
            f"Status: {response.status_code}\n"
            f"Response: {response.text}"
        )

    token_response = response.json()

    token = token_response.get("access_token")

    if not token:
        raise RuntimeError(
            "access_token not found in token response."
        )

    print("Access token generated successfully.")
    print("Token length:", len(token))

    return token
