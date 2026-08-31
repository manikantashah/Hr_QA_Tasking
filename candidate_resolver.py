# ============================================================
# candidate_resolver.py
# ============================================================

import json
import re

from difflib import SequenceMatcher

# ============================================================
# PARSE JSON SAFELY
# ============================================================

def parse_json_safely(value):
    """
    Safely parse Oracle Agent JSON output.

    Handles:
    1. Dictionary
    2. Normal JSON string
    3. JSON string containing extra text
    """

    if isinstance(value, dict):
        return value

    if not isinstance(value, str):
        return None

    value = value.strip()

    if not value:
        return None

    # --------------------------------------------------------
    # Try normal JSON parsing first
    # --------------------------------------------------------

    try:
        return json.loads(value)

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------------
    # Try extracting the first JSON object
    # --------------------------------------------------------

    start = value.find("{")
    end = value.rfind("}")

    if start == -1 or end == -1:
        return None

    json_text = value[start:end + 1]

    try:
        return json.loads(json_text)

    except json.JSONDecodeError:
        return None

# ============================================================
# NORMALIZE NAME
# ============================================================

def normalize_name(
    name: str
) -> str:

    if not name:
        return ""

    name = str(
        name
    ).strip().lower()

    # Remove extra spaces
    name = re.sub(
        r"\s+",
        " ",
        name
    )

    return name


# ============================================================
# NAME SIMILARITY
# ============================================================

def name_similarity(
    name1: str,
    name2: str
) -> float:

    return SequenceMatcher(
        None,
        normalize_name(name1),
        normalize_name(name2)
    ).ratio()


# ============================================================
# FIND BEST CANDIDATE FROM ORACLE AGENT RESULT
# ============================================================

def find_best_candidate(
    candidate_result,
    requested_name: str
):

    # ========================================================
    # VALIDATE INPUT
    # ========================================================

    if not isinstance(
        candidate_result,
        dict
    ):
        return None

    if not requested_name:
        return None

    # ========================================================
    # GET OUTPUT
    # ========================================================

    output = candidate_result.get(
        "output"
    )

    # --------------------------------------------------------
    # No output
    # --------------------------------------------------------

    if output is None:

        return None

    # ========================================================
    # ORACLE OUTPUT MAY BE JSON STRING
    # ========================================================

    if isinstance(
        output,
        str
    ):

        output = output.strip()

        if not output:

            return None

        # ----------------------------------------------------
        # First try normal JSON parsing
        # ----------------------------------------------------

        try:

            output = json.loads(
                output
            )

        except json.JSONDecodeError:

            # ------------------------------------------------
            # JSON may contain extra text
            # ------------------------------------------------

            start = output.find(
                "{"
            )

            end = output.rfind(
                "}"
            )

            if (
                start == -1
                or
                end == -1
            ):

                return None

            json_text = output[
                start:end + 1
            ]

            try:

                output = json.loads(
                    json_text
                )

            except json.JSONDecodeError:

                return None

    # ========================================================
    # VALIDATE PARSED OUTPUT
    # ========================================================

    if not isinstance(
        output,
        dict
    ):

        return None

    # ========================================================
    # GET RESULT
    # ========================================================

    result = output.get(
        "result",
        {}
    )

    if not isinstance(
        result,
        dict
    ):

        return None

    # ========================================================
    # GET CANDIDATE LIST
    # ========================================================

    candidates = result.get(
        "requisitions",
        []
    )

    if not isinstance(
        candidates,
        list
    ):

        return None

    if not candidates:

        return None

    # ========================================================
    # NORMALIZE REQUESTED NAME
    # ========================================================

    requested_name = str(
        requested_name
    ).strip()

    if not requested_name:

        return None

    requested_normalized = (
        normalize_name(
            requested_name
        )
    )

    # ========================================================
    # 1. EXACT CASE-INSENSITIVE MATCH
    # ========================================================

    for candidate in candidates:

        if not isinstance(
            candidate,
            dict
        ):

            continue

        actual_name = candidate.get(
            "CandidateName"
        )

        if not actual_name:

            continue

        if (
            normalize_name(
                actual_name
            )
            ==
            requested_normalized
        ):

            return {

                "status":
                    "EXACT",

                "candidate":
                    candidate,

                "score":
                    1.0
            }

    # ========================================================
    # 2. FUZZY MATCH
    # ========================================================

    best_candidate = None

    best_score = 0.0

    for candidate in candidates:

        if not isinstance(
            candidate,
            dict
        ):

            continue

        actual_name = candidate.get(
            "CandidateName"
        )

        if not actual_name:

            continue

        score = name_similarity(
            requested_name,
            actual_name
        )

        if score > best_score:

            best_score = score

            best_candidate = candidate

    # ========================================================
    # 3. SUGGESTION
    # ========================================================

    if (
        best_candidate
        and
        best_score >= 0.75
    ):

        return {

            "status":
                "SUGGEST",

            "candidate":
                best_candidate,

            "score":
                round(
                    best_score,
                    4
                )
        }

    # ========================================================
    # 4. NOT FOUND
    # ========================================================

    return None


# ============================================================
# RESOLVE CANDIDATE FROM ORACLE AGENT RESULT
# ============================================================

def resolve_candidate(
    candidate_result,
    requested_name: str
):

    match = find_best_candidate(
        candidate_result,
        requested_name
    )

    # --------------------------------------------------------
    # Candidate does not exist
    # --------------------------------------------------------

    if not match:

        return {

            "status":
                "NOT_FOUND",

            "candidate":
                None,

            "candidate_name":
                None,

            "email":
                None,

            "jobApplicationId":
                None,

            "score":
                0.0
        }

    # --------------------------------------------------------
    # Candidate found / suggested
    # --------------------------------------------------------

    candidate = match[
        "candidate"
    ]

    return {

        "status":
            match[
                "status"
            ],

        "candidate":
            candidate,

        "candidate_name":
            candidate.get(
                "CandidateName"
            ),

        "email":
            candidate.get(
                "Email"
            ),

        "jobApplicationId":
            candidate.get(
                "JobApplicationId"
            ),

        "score":
            match.get(
                "score",
                0.0
            )
    }


# ============================================================
# FIND BEST CANDIDATE FROM HR MASTER DATAFRAME
# ============================================================

def resolve_candidate_from_dataframe(
    master_df,
    requested_name: str
):

    # ========================================================
    # VALIDATE DATAFRAME
    # ========================================================

    if master_df is None:

        return None

    if master_df.empty:

        return None

    if "candidate_name" not in master_df.columns:

        return None

    requested_name = str(
        requested_name
    ).strip()

    if not requested_name:

        return None

    requested_normalized = (
        normalize_name(
            requested_name
        )
    )

    # ========================================================
    # GET UNIQUE CANDIDATE NAMES
    # ========================================================

    candidate_names = (

        master_df[
            "candidate_name"
        ]

        .dropna()

        .astype(str)

        .str.strip()

        .unique()

        .tolist()
    )

    # ========================================================
    # 1. EXACT CASE-INSENSITIVE MATCH
    # ========================================================

    for candidate_name in candidate_names:

        if (
            normalize_name(
                candidate_name
            )
            ==
            requested_normalized
        ):

            return {

                "status":
                    "EXACT",

                "requested_name":
                    requested_name,

                "actual_name":
                    candidate_name,

                "score":
                    1.0
            }

    # ========================================================
    # 2. FUZZY MATCH
    # ========================================================

    best_name = None

    best_score = 0.0

    for candidate_name in candidate_names:

        score = name_similarity(
            requested_name,
            candidate_name
        )

        if score > best_score:

            best_score = score

            best_name = candidate_name

    # ========================================================
    # 3. SUGGESTION
    # ========================================================

    if (
        best_name
        and
        best_score >= 0.75
    ):

        return {

            "status":
                "SUGGEST",

            "requested_name":
                requested_name,

            "actual_name":
                best_name,

            "score":
                best_score
        }

    # ========================================================
    # 4. NOT FOUND
    # ========================================================

    return {

        "status":
            "NOT_FOUND",

        "requested_name":
            requested_name,

        "actual_name":
            None,

        "score":
            best_score
    }


# ============================================================
# OPTIONAL: GET CANONICAL CANDIDATE DATA FROM DATAFRAME
# ============================================================

def get_candidate_from_dataframe(
    master_df,
    candidate_name: str
):

    if master_df is None:

        return None

    if master_df.empty:

        return None

    if "candidate_name" not in master_df.columns:

        return None

    normalized_requested = (
        normalize_name(
            candidate_name
        )
    )

    for _, row in master_df.iterrows():

        actual_name = row.get(
            "candidate_name"
        )

        if not actual_name:

            continue

        if (
            normalize_name(
                str(actual_name)
            )
            ==
            normalized_requested
        ):

            return row.to_dict()

    return None