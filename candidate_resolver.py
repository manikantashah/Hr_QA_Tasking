
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
        4. JSON string with extra data after first JSON object
    """

    # --------------------------------------------------------
    # Already dictionary
    # --------------------------------------------------------

    if isinstance(
        value,
        dict
    ):

        return value

    # --------------------------------------------------------
    # Must be string
    # --------------------------------------------------------

    if not isinstance(
        value,
        str
    ):

        return None

    value = value.strip()

    if not value:

        return None

    # --------------------------------------------------------
    # Normal JSON parsing
    # --------------------------------------------------------

    try:

        return json.loads(
            value
        )

    except json.JSONDecodeError:

        pass

    # --------------------------------------------------------
    # JSON decoder
    # --------------------------------------------------------

    try:

        decoder = json.JSONDecoder()

        parsed, _ = decoder.raw_decode(
            value
        )

        return parsed

    except (
        json.JSONDecodeError,
        TypeError
    ):

        pass

    # --------------------------------------------------------
    # Extract JSON object
    # --------------------------------------------------------

    start = value.find(
        "{"
    )

    end = value.rfind(
        "}"
    )

    if (
        start == -1
        or
        end == -1
    ):

        return None

    json_text = value[
        start:end + 1
    ]

    try:

        return json.loads(
            json_text
        )

    except json.JSONDecodeError:

        return None


# ============================================================
# NORMALIZE NAME
# ============================================================

def normalize_name(
    name: str
) -> str:
    """
    Normalize candidate name.

    Example:

        " Jithu   Danel "
        ->
        "jithu danel"
    """

    if not name:

        return ""

    name = str(
        name
    ).strip().lower()

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
    """
    Calculate fuzzy similarity between names.

    Word order is ignored.

    Examples:

        Jithu Danel
        Jithu Daniel

        Wood Charles
        Charles Wood
    """

    name1 = normalize_name(
        name1
    )

    name2 = normalize_name(
        name2
    )

    if (
        not name1
        or
        not name2
    ):

        return 0.0

    words1 = name1.split()
    words2 = name2.split()

    n1 = len(
        words1
    )

    n2 = len(
        words2
    )

    # --------------------------------------------------------
    # Make words1 the longer list
    # --------------------------------------------------------

    if n1 < n2:

        words1, words2 = (
            words2,
            words1
        )

        n1, n2 = (
            n2,
            n1
        )

    # --------------------------------------------------------
    # Sort shorter name
    # --------------------------------------------------------

    words2 = sorted(
        words2
    )

    normalized_name2 = " ".join(
        words2
    )

    scores = []

    # --------------------------------------------------------
    # Compare shorter name against windows
    # --------------------------------------------------------

    for i in range(
        n1 - n2 + 1
    ):

        current_words = words1[
            i:i + n2
        ]

        current_words = sorted(
            current_words
        )

        normalized_name1 = " ".join(
            current_words
        )

        score = SequenceMatcher(
            None,
            normalized_name1,
            normalized_name2
        ).ratio()

        scores.append(
            score
        )

    return (
        max(scores)
        if scores
        else 0.0
    )


# ============================================================
# BUILD CANDIDATE MATCH
# ============================================================

def build_candidate_match(
    candidate,
    requested_name,
    score,
    match_type
):
    """
    Build a consistent candidate match object.
    """

    return {

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

        "requisition_number":
            candidate.get(
                "RequisitionNumber"
            ),

        "requested_name":
            requested_name,

        "score":
            round(
                score,
                4
            ),

        "match_type":
            match_type
    }


# ============================================================
# REMOVE DUPLICATE CANDIDATE MATCHES
# ============================================================

def remove_duplicate_candidate_matches(
    matches
):
    """
    Remove duplicate candidates.

    Primary key:
        JobApplicationId

    Fallback:
        CandidateName + Email
    """

    unique_matches = []

    seen = set()

    for match in matches:

        if not isinstance(
            match,
            dict
        ):

            continue

        candidate = match.get(
            "candidate",
            {}
        )

        if not isinstance(
            candidate,
            dict
        ):

            continue

        application_id = candidate.get(
            "JobApplicationId"
        )

        candidate_name = normalize_name(
            candidate.get(
                "CandidateName"
            )
        )

        email = normalize_name(
            candidate.get(
                "Email"
            )
        )

        if application_id:

            key = (
                "APPLICATION",
                str(
                    application_id
                )
            )

        else:

            key = (
                "NAME_EMAIL",
                candidate_name,
                email
            )

        if key in seen:

            continue

        seen.add(
            key
        )

        unique_matches.append(
            match
        )

    return unique_matches


# ============================================================
# SORT CANDIDATE MATCHES
# ============================================================

def sort_candidate_matches(
    matches
):
    """
    Sort strongest candidate matches first.
    """

    return sorted(

        matches,

        key=lambda item:
            item.get(
                "score",
                0.0
            ),

        reverse=True
    )


# ============================================================
# FIND BEST CANDIDATE FROM ORACLE AGENT RESULT
# ============================================================

def find_best_candidate(
    candidate_result,
    requested_name: str,
    threshold: float = 0.75,
    multiple_margin: float = 0.08
):
    """
    Resolve a candidate from CANDIDATEREQUISTION.

    Possible statuses:

        EXACT
        SUGGEST
        MULTIPLE
        NOT_FOUND

    Rules:

        1. One exact candidate
           -> EXACT

        2. Multiple exact candidates
           -> MULTIPLE

        3. One strong fuzzy candidate
           -> SUGGEST

        4. Multiple close fuzzy candidates
           -> MULTIPLE

        5. No sufficiently close candidate
           -> NOT_FOUND

    multiple_margin:

        Only fuzzy candidates close to the best score
        are returned.

        Example:

            Best score = 0.91
            Margin     = 0.08

            Candidates >= 0.83
            are considered relevant.
    """

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

    requested_name = str(
        requested_name
    ).strip()

    if not requested_name:

        return None

    # ========================================================
    # GET OUTPUT
    # ========================================================

    output = candidate_result.get(
        "output"
    )

    if output is None:

        return None

    # ========================================================
    # PARSE OUTPUT
    # ========================================================

    if isinstance(
        output,
        str
    ):

        output = parse_json_safely(
            output
        )

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

    if isinstance(
        result,
        str
    ):

        result = parse_json_safely(
            result
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

    requested_normalized = normalize_name(
        requested_name
    )

    # ========================================================
    # 1. FIND ALL EXACT MATCHES
    # ========================================================

    exact_matches = []

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

            exact_matches.append(
                build_candidate_match(
                    candidate,
                    requested_name,
                    1.0,
                    "EXACT"
                )
            )

    exact_matches = (
        remove_duplicate_candidate_matches(
            exact_matches
        )
    )

    # ========================================================
    # ONE EXACT MATCH
    # ========================================================

    if len(
        exact_matches
    ) == 1:

        return {

            "status":
                "EXACT",

            "requested_name":
                requested_name,

            "candidate":
                exact_matches[0].get(
                    "candidate"
                ),

            "candidate_name":
                exact_matches[0].get(
                    "candidate_name"
                ),

            "email":
                exact_matches[0].get(
                    "email"
                ),

            "jobApplicationId":
                exact_matches[0].get(
                    "jobApplicationId"
                ),

            "score":
                1.0,

            "matches":
                []
        }

    # ========================================================
    # MULTIPLE EXACT MATCHES
    # ========================================================

    if len(
        exact_matches
    ) > 1:

        return {

            "status":
                "MULTIPLE",

            "requested_name":
                requested_name,

            "candidate":
                None,

            "candidate_name":
                None,

            "email":
                None,

            "jobApplicationId":
                None,

            "score":
                1.0,

            "matches":
                exact_matches
        }

    # ========================================================
    # 2. CALCULATE ALL FUZZY SCORES
    # ========================================================

    fuzzy_matches = []

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

        if score >= threshold:

            fuzzy_matches.append(
                build_candidate_match(
                    candidate,
                    requested_name,
                    score,
                    "FUZZY"
                )
            )

    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    fuzzy_matches = (
        remove_duplicate_candidate_matches(
            fuzzy_matches
        )
    )

    # ========================================================
    # SORT
    # ========================================================

    fuzzy_matches = sort_candidate_matches(
        fuzzy_matches
    )

    # ========================================================
    # NOTHING FOUND
    # ========================================================

    if not fuzzy_matches:

        return {

            "status":
                "NOT_FOUND",

            "requested_name":
                requested_name,

            "candidate":
                None,

            "candidate_name":
                None,

            "email":
                None,

            "jobApplicationId":
                None,

            "score":
                0.0,

            "matches":
                []
        }

    # ========================================================
    # BEST FUZZY SCORE
    # ========================================================

    best_score = fuzzy_matches[0].get(
        "score",
        0.0
    )

    # ========================================================
    # KEEP ONLY CLOSE CANDIDATES
    # ========================================================

    relevant_matches = []

    minimum_relevant_score = max(
        threshold,
        best_score - multiple_margin
    )

    for match in fuzzy_matches:

        score = match.get(
            "score",
            0.0
        )

        if score >= minimum_relevant_score:

            relevant_matches.append(
                match
            )

    # ========================================================
    # ONE RELEVANT FUZZY CANDIDATE
    # ========================================================

    if len(
        relevant_matches
    ) == 1:

        single_match = (
            relevant_matches[0]
        )

        return {

            "status":
                "SUGGEST",

            "requested_name":
                requested_name,

            "candidate":
                single_match.get(
                    "candidate"
                ),

            "candidate_name":
                single_match.get(
                    "candidate_name"
                ),

            "email":
                single_match.get(
                    "email"
                ),

            "jobApplicationId":
                single_match.get(
                    "jobApplicationId"
                ),

            "score":
                single_match.get(
                    "score",
                    0.0
                ),

            "matches":
                []
        }

    # ========================================================
    # MULTIPLE RELEVANT FUZZY CANDIDATES
    # ========================================================

    return {

        "status":
            "MULTIPLE",

        "requested_name":
            requested_name,

        "candidate":
            None,

        "candidate_name":
            None,

        "email":
            None,

        "jobApplicationId":
            None,

        "score":
            best_score,

        "matches":
            relevant_matches
    }


# ============================================================
# RESOLVE CANDIDATE
# ============================================================

def resolve_candidate(
    candidate_result,
    requested_name: str
):
    """
    Public candidate resolver.

    Possible statuses:

        EXACT
        SUGGEST
        MULTIPLE
        NOT_FOUND
    """

    match = find_best_candidate(
        candidate_result,
        requested_name
    )

    # ========================================================
    # NOT FOUND
    # ========================================================

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
                0.0,

            "matches":
                []
        }

    status = match.get(
        "status"
    )

    # ========================================================
    # MULTIPLE
    # ========================================================

    if status == "MULTIPLE":

        return {

            "status":
                "MULTIPLE",

            "requested_name":
                requested_name,

            "candidate":
                None,

            "candidate_name":
                None,

            "email":
                None,

            "jobApplicationId":
                None,

            "score":
                match.get(
                    "score",
                    0.0
                ),

            "matches":
                match.get(
                    "matches",
                    []
                )
        }

    # ========================================================
    # EXACT / SUGGEST
    # ========================================================

    candidate = match.get(
        "candidate"
    )

    if not isinstance(
        candidate,
        dict
    ):

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
                0.0,

            "matches":
                []
        }

    return {

        "status":
            status,

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
            ),

        "matches":
            []
    }


# ============================================================
# FIND BEST CANDIDATE FROM HR MASTER DATAFRAME
# ============================================================

def resolve_candidate_from_dataframe(
    master_df,
    requested_name: str,
    threshold: float = 0.75,
    multiple_margin: float = 0.08
):
    """
    Resolve candidate names from a DataFrame.

    Possible statuses:

        EXACT
        SUGGEST
        MULTIPLE
        NOT_FOUND
    """

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

    requested_normalized = normalize_name(
        requested_name
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
    # EXACT MATCHES
    # ========================================================

    exact_names = []

    for candidate_name in candidate_names:

        if (
            normalize_name(
                candidate_name
            )
            ==
            requested_normalized
        ):

            exact_names.append(
                candidate_name
            )

    # ========================================================
    # ONE EXACT MATCH
    # ========================================================

    if len(
        exact_names
    ) == 1:

        return {

            "status":
                "EXACT",

            "requested_name":
                requested_name,

            "actual_name":
                exact_names[0],

            "score":
                1.0
        }

    # ========================================================
    # MULTIPLE EXACT MATCHES
    # ========================================================

    if len(
        exact_names
    ) > 1:

        return {

            "status":
                "MULTIPLE",

            "requested_name":
                requested_name,

            "matches":
                exact_names
        }

    # ========================================================
    # FUZZY MATCHES
    # ========================================================

    fuzzy_names = []

    for candidate_name in candidate_names:

        score = name_similarity(
            requested_name,
            candidate_name
        )

        if score >= threshold:

            fuzzy_names.append(
                {
                    "actual_name":
                        candidate_name,

                    "score":
                        round(
                            score,
                            4
                        )
                }
            )

    # ========================================================
    # SORT
    # ========================================================

    fuzzy_names = sorted(

        fuzzy_names,

        key=lambda item:
            item.get(
                "score",
                0.0
            ),

        reverse=True
    )

    # ========================================================
    # NO FUZZY MATCH
    # ========================================================

    if not fuzzy_names:

        return {

            "status":
                "NOT_FOUND",

            "requested_name":
                requested_name,

            "actual_name":
                None,

            "score":
                0.0
        }

    # ========================================================
    # BEST SCORE
    # ========================================================

    best_score = fuzzy_names[0].get(
        "score",
        0.0
    )

    minimum_relevant_score = max(
        threshold,
        best_score - multiple_margin
    )

    relevant_names = [

        item

        for item in fuzzy_names

        if item.get(
            "score",
            0.0
        ) >= minimum_relevant_score

    ]

    # ========================================================
    # ONE FUZZY MATCH
    # ========================================================

    if len(
        relevant_names
    ) == 1:

        return {

            "status":
                "SUGGEST",

            "requested_name":
                requested_name,

            "actual_name":
                relevant_names[0].get(
                    "actual_name"
                ),

            "score":
                relevant_names[0].get(
                    "score",
                    0.0
                )
        }

    # ========================================================
    # MULTIPLE FUZZY MATCHES
    # ========================================================

    return {

        "status":
            "MULTIPLE",

        "requested_name":
            requested_name,

        "matches":
            relevant_names
    }


# ============================================================
# GET CANONICAL CANDIDATE DATA FROM DATAFRAME
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

    normalized_requested = normalize_name(
        candidate_name
    )

    for _, row in master_df.iterrows():

        actual_name = row.get(
            "candidate_name"
        )

        if not actual_name:

            continue

        if (
            normalize_name(
                str(
                    actual_name
                )
            )
            ==
            normalized_requested
        ):

            return row.to_dict()

    return None

