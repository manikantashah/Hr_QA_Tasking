# ============================================================
# interviewer_resolver.py
# ============================================================

import json
import re
from difflib import SequenceMatcher


# ============================================================
# NORMALIZE NAME
# ============================================================

def normalize_name(name: str) -> str:

    if not name:
        return ""

    name = str(name).strip().lower()

    # Remove extra spaces
    name = re.sub(r"\s+", " ", name)

    return name


# ============================================================
# NAME TOKENS
# ============================================================

def get_name_tokens(name: str):
    """
    Convert a name into normalized individual tokens.

    Example:
        "Charles Wood Devadoss Wood Fread"

    becomes:
        ["charles", "wood", "devadoss", "wood", "fread"]
    """

    normalized = normalize_name(name)

    if not normalized:
        return []

    return normalized.split()


# ============================================================
# NAME SIMILARITY
# ============================================================

def normalize_name(name: str) -> str:

    if not name:
        return ""

    name = str(name).strip().lower()

    name = re.sub(r"\s+", " ", name)

    return name


def name_similarity(name1: str, name2: str) -> float:

    name1 = normalize_name(name1)
    name2 = normalize_name(name2)

    words1 = name1.split()
    words2 = name2.split()

    n1 = len(words1)
    n2 = len(words2)

    if n1 < n2:
        words1, words2 = words2, words1
        n1, n2 = n2, n1

    # Sort requested name
    words2.sort()

    normalized_name2 = " ".join(words2)

    scores = []

    for i in range(n1 - n2 + 1):

        current_words = words1[i:i + n2]

        # Sort current window
        current_words.sort()

        normalized_name1 = " ".join(current_words)

        score = SequenceMatcher(
            None,
            normalized_name1,
            normalized_name2
        ).ratio()

        scores.append(score)

    return max(scores) if scores else 0.0



# ============================================================
# PARTIAL NAME MATCH
# ============================================================

def partial_name_match(
    requested_name: str,
    actual_name: str
) -> bool:
    """
    Check whether the requested name represents a meaningful
    partial version of the actual interviewer name.

    Examples:

        requested:
            Charles Wood

        actual:
            Charles Wood Devadoss Wood Fread

        -> True

        requested:
            Charles Wood Devadoss

        actual:
            Charles Wood Devadoss Wood Fread

        -> True

        requested:
            Charles

        actual:
            Charles Wood Devadoss Wood Fread

        -> True
    """

    requested_tokens = get_name_tokens(requested_name)
    actual_tokens = get_name_tokens(actual_name)

    if not requested_tokens or not actual_tokens:
        return False

    # --------------------------------------------------------
    # Single token
    # --------------------------------------------------------

    if len(requested_tokens) == 1:
        return requested_tokens[0] in actual_tokens

    # --------------------------------------------------------
    # Multiple tokens
    #
    # Check whether requested sequence occurs consecutively
    # inside the actual name.
    #
    # Example:
    #
    # Charles Wood
    #
    # exists inside:
    #
    # Charles Wood Devadoss Wood Fread
    # --------------------------------------------------------

    requested_length = len(requested_tokens)
    actual_length = len(actual_tokens)

    for index in range(
        actual_length - requested_length + 1
    ):
        if (
            actual_tokens[
                index:index + requested_length
            ]
            == requested_tokens
        ):
            return True

    return False


# ============================================================
# PARTIAL NAME SCORE
# ============================================================

def partial_name_score(
    requested_name: str,
    actual_name: str
) -> float:
    """
    Calculate a score for partial token-based matching.

    Example:

        Charles Wood

        vs

        Charles Wood Devadoss Wood Fread

    gets a strong partial-match score.
    """

    requested_tokens = get_name_tokens(requested_name)
    actual_tokens = get_name_tokens(actual_name)

    if not requested_tokens or not actual_tokens:
        return 0.0

    # --------------------------------------------------------
    # Count matching tokens
    # --------------------------------------------------------

    matched_tokens = 0

    for token in requested_tokens:
        if token in actual_tokens:
            matched_tokens += 1

    token_score = (
        matched_tokens / len(requested_tokens)
    )

    # --------------------------------------------------------
    # Prefix bonus
    #
    # "Charles Wood" is especially strong when it appears
    # at the beginning of the full name.
    # --------------------------------------------------------

    prefix_bonus = 0.0

    if len(actual_tokens) >= len(requested_tokens):

        if (
            actual_tokens[
                :len(requested_tokens)
            ]
            == requested_tokens
        ):
            prefix_bonus = 0.2

    score = min(
        1.0,
        token_score + prefix_bonus
    )

    return score


# ============================================================
# GET INTERVIEWER LIST FROM AGENT RESULT
# ============================================================

def get_interviewer_list(interviewer_result):
    """
    Extract interviewer list from INTERVIEWERDATA agent response.

    Supported structures:

    1.
    {
        "output": {
            "result": [
                {
                    "DisplayName": "...",
                    "WorkEmail": "..."
                }
            ]
        }
    }

    2. output can be a JSON string.

    3. result may itself be wrapped inside another object.
    """

    # ========================================================
    # VALIDATE INPUT
    # ========================================================

    if not isinstance(interviewer_result, dict):
        return []

    # ========================================================
    # GET OUTPUT
    # ========================================================

    output = interviewer_result.get("output")

    if output is None:
        return []

    # ========================================================
    # OUTPUT MAY BE JSON STRING
    # ========================================================

    if isinstance(output, str):

        output = output.strip()

        if not output:
            return []

        try:
            output = json.loads(output)

        except (
            json.JSONDecodeError,
            TypeError
        ):
            return []

    # ========================================================
    # OUTPUT MUST BE DICT
    # ========================================================

    if not isinstance(output, dict):
        return []

    # ========================================================
    # GET RESULT
    # ========================================================

    result = output.get("result")

    if result is None:
        return []

    # ========================================================
    # RESULT DIRECTLY CONTAINS LIST
    # ========================================================

    if isinstance(result, list):
        return result

    # ========================================================
    # RESULT MAY BE NESTED
    #
    # Example:
    #
    # {
    #     "result": {
    #         "result": [...]
    #     }
    # }
    # ========================================================

    if isinstance(result, dict):

        nested_result = result.get("result")

        if isinstance(nested_result, list):
            return nested_result

        # ----------------------------------------------------
        # Some responses may use "interviewers"
        # ----------------------------------------------------

        interviewers = result.get("interviewers")

        if isinstance(interviewers, list):
            return interviewers

    # ========================================================
    # NOTHING USABLE FOUND
    # ========================================================

    return []


# ============================================================
# FIND BEST / EXACT INTERVIEWER
# ============================================================

def find_best_interviewer(
    interviewer_result,
    requested_name: str
):
    """
    Find an interviewer for one requested name.

    IMPORTANT:
    A fuzzy or partial match is NEVER automatically selected.

    Returns:

        Exact match:
        {
            "status": "EXACT",
            "interviewer": {...},
            "score": 1.0
        }

        Partial/Fuzzy match:
        {
            "status": "SUGGEST",
            "interviewer": {...},
            "score": ...
        }

        No match:
        None
    """

    # ========================================================
    # VALIDATE REQUEST
    # ========================================================

    if not requested_name:
        return None

    requested_name = str(requested_name).strip()

    if not requested_name:
        return None

    requested_normalized = normalize_name(
        requested_name
    )

    # ========================================================
    # GET INTERVIEWER LIST
    # ========================================================

    interviewer_list = get_interviewer_list(
        interviewer_result
    )

    if not interviewer_list:
        return None

    # ========================================================
    # 1. EXACT MATCH
    # ========================================================

    for interviewer in interviewer_list:

        if not isinstance(interviewer, dict):
            continue

        actual_name = interviewer.get("DisplayName")

        if not actual_name:
            continue

        if (
            normalize_name(actual_name)
            == requested_normalized
        ):
            return {
                "status": "EXACT",
                "interviewer": interviewer,
                "score": 1.0
            }

    # ========================================================
    # 2. PARTIAL TOKEN MATCH
    # ========================================================

    partial_candidates = []

    for interviewer in interviewer_list:

        if not isinstance(interviewer, dict):
            continue

        actual_name = interviewer.get("DisplayName")

        if not actual_name:
            continue

        if partial_name_match(
            requested_name,
            actual_name
        ):

            score = partial_name_score(
                requested_name,
                actual_name
            )

            partial_candidates.append(
                (
                    score,
                    interviewer
                )
            )

    # ========================================================
    # SELECT BEST PARTIAL MATCH
    # ========================================================

    if partial_candidates:

        partial_candidates.sort(
            key=lambda item: item[0],
            reverse=True
        )

        best_score, best_interviewer = (
            partial_candidates[0]
        )

        return {
            "status": "SUGGEST",
            "interviewer": best_interviewer,
            "score": round(best_score, 4)
        }

    # ========================================================
    # 3. FIND BEST FUZZY MATCH
    # ========================================================

    best_interviewer = None
    best_score = 0.0

    for interviewer in interviewer_list:

        if not isinstance(interviewer, dict):
            continue

        actual_name = interviewer.get("DisplayName")

        if not actual_name:
            continue

        score = name_similarity(
            requested_name,
            actual_name
        )

        if score > best_score:
            best_score = score
            best_interviewer = interviewer

    # ========================================================
    # 4. SUGGESTION
    # ========================================================

    if (
        best_interviewer
        and best_score >= 0.75
    ):
        return {
            "status": "SUGGEST",
            "interviewer": best_interviewer,
            "score": round(best_score, 4)
        }

    # ========================================================
    # 5. NOT FOUND
    # ========================================================

    return None


# ============================================================
# FIND ALL INTERVIEWER SUGGESTIONS
# ============================================================

def find_interviewer_suggestions(
    interviewer_result,
    requested_name: str,
    threshold: float = 0.75
):
    """
    Find ALL interviewers that are sufficiently similar
    to the requested interviewer name.

    IMPORTANT:
    This function does NOT select any interviewer.

    It only produces suggestions.

    Matching methods:

    1. Exact token sequence / partial name
    2. Fuzzy SequenceMatcher similarity
    """

    # ========================================================
    # VALIDATE REQUEST
    # ========================================================

    if not requested_name:
        return []

    requested_name = str(requested_name).strip()

    if not requested_name:
        return []

    # ========================================================
    # GET INTERVIEWER LIST
    # ========================================================

    interviewer_list = get_interviewer_list(
        interviewer_result
    )

    if not interviewer_list:
        return []

    # ========================================================
    # CALCULATE SCORES
    # ========================================================

    suggestions = []

    for interviewer in interviewer_list:

        if not isinstance(interviewer, dict):
            continue

        actual_name = interviewer.get("DisplayName")

        if not actual_name:
            continue

        # ----------------------------------------------------
        # Normal fuzzy similarity
        # ----------------------------------------------------

        fuzzy_score = name_similarity(
            requested_name,
            actual_name
        )

        # ----------------------------------------------------
        # Partial token score
        # ----------------------------------------------------

        partial_score = partial_name_score(
            requested_name,
            actual_name
        )

        # ----------------------------------------------------
        # Choose strongest score
        # ----------------------------------------------------

        score = max(
            fuzzy_score,
            partial_score
        )

        # ----------------------------------------------------
        # Partial name match should always qualify
        # ----------------------------------------------------

        is_partial_match = partial_name_match(
            requested_name,
            actual_name
        )

        if (
            score >= threshold
            or is_partial_match
        ):
            suggestions.append(
                {
                    "requested_name": requested_name,
                    "actual_name": actual_name,
                    "email": interviewer.get("WorkEmail"),
                    "score": round(score, 4)
                }
            )

    # ========================================================
    # SORT BY SCORE
    # ========================================================

    suggestions.sort(
        key=lambda item: item.get("score", 0.0),
        reverse=True
    )

    return suggestions


# ============================================================
# RESOLVE MULTIPLE INTERVIEWERS
# ============================================================

def resolve_interviewers(
    interviewer_result,
    requested_names
):
    """
    Resolve one or more interviewer names.

    Behavior:

    1. Exact match
       -> FOUND

    2. Partial match
       -> SUGGEST

    3. Fuzzy match
       -> SUGGEST

    4. No match
       -> NOT_FOUND

    IMPORTANT:
    A fuzzy or partial match is NEVER automatically selected.

    Example:

        User:
            Charles Wood

        API:
            Charles Wood Devadoss Wood Fread

        Result:
            {
                "status": "SUGGEST",
                "suggestions": [...]
            }

    The orchestrator can then ask the user for confirmation.
    """

    # ========================================================
    # NORMALIZE REQUESTED NAMES
    # ========================================================

    if isinstance(requested_names, str):
        requested_names = [requested_names]

    if not isinstance(requested_names, list):
        return {
            "status": "NOT_FOUND",
            "matches": [],
            "suggestions": [],
            "not_found": []
        }

    requested_names = [
        str(name).strip()
        for name in requested_names
        if str(name).strip()
    ]

    if not requested_names:
        return {
            "status": "NOT_FOUND",
            "matches": [],
            "suggestions": [],
            "not_found": []
        }

    # ========================================================
    # GET INTERVIEWER LIST
    # ========================================================

    interviewer_list = get_interviewer_list(
        interviewer_result
    )

    if not interviewer_list:
        return {
            "status": "NOT_FOUND",
            "matches": [],
            "suggestions": [],
            "not_found": requested_names
        }

    # ========================================================
    # RESULT ARRAYS
    # ========================================================

    matches = []
    suggestions = []
    not_found = []

    # ========================================================
    # RESOLVE EACH REQUESTED INTERVIEWER
    # ========================================================

    for requested_name in requested_names:

        # ====================================================
        # 1. EXACT MATCH
        # ====================================================

        exact_match = None

        requested_normalized = normalize_name(
            requested_name
        )

        for interviewer in interviewer_list:

            if not isinstance(interviewer, dict):
                continue

            actual_name = interviewer.get("DisplayName")

            if not actual_name:
                continue

            if (
                normalize_name(actual_name)
                == requested_normalized
            ):
                exact_match = interviewer
                break

        # ====================================================
        # EXACT MATCH FOUND
        # ====================================================

        if exact_match:

            matches.append(
                {
                    "requested_name": requested_name,
                    "actual_name": exact_match.get(
                        "DisplayName"
                    ),
                    "email": exact_match.get(
                        "WorkEmail"
                    ),
                    "score": 1.0
                }
            )

            continue

        # ====================================================
        # 2. NO EXACT MATCH
        #
        # FIND PARTIAL / FUZZY SUGGESTIONS
        # ====================================================

        name_suggestions = find_interviewer_suggestions(
            interviewer_result,
            requested_name,
            threshold=0.75
        )

        # ====================================================
        # NO MATCH
        # ====================================================

        if not name_suggestions:

            not_found.append(
                requested_name
            )

            continue

        # ====================================================
        # ADD SUGGESTIONS
        # ====================================================

        suggestions.extend(
            name_suggestions
        )

    # ========================================================
    # REMOVE DUPLICATE SUGGESTIONS
    # ========================================================

    unique_suggestions = []
    seen = set()

    for suggestion in suggestions:

        key = (
            suggestion.get("requested_name"),
            suggestion.get("actual_name")
        )

        if key in seen:
            continue

        seen.add(key)

        unique_suggestions.append(
            suggestion
        )

    suggestions = unique_suggestions

    # ========================================================
    # SORT SUGGESTIONS
    # ========================================================

    suggestions.sort(
        key=lambda item: item.get("score", 0.0),
        reverse=True
    )

    # ========================================================
    # FUZZY / PARTIAL SUGGESTION FOUND
    #
    # IMPORTANT:
    # DO NOT AUTOMATICALLY SELECT.
    # ========================================================

    if suggestions:

        return {
            "status": "SUGGEST",
            "matches": matches,
            "suggestions": suggestions,
            "not_found": not_found
        }

    # ========================================================
    # NOTHING FOUND
    # ========================================================

    if not matches:

        return {
            "status": "NOT_FOUND",
            "matches": [],
            "suggestions": [],
            "not_found": not_found
        }

    # ========================================================
    # SOME INTERVIEWERS NOT FOUND
    # ========================================================

    if not_found:

        return {
            "status": "NOT_FOUND",
            "matches": matches,
            "suggestions": [],
            "not_found": not_found
        }

    # ========================================================
    # ALL INTERVIEWERS FOUND EXACTLY
    # ========================================================

    return {
        "status": "FOUND",
        "matches": matches,
        "suggestions": [],
        "not_found": []
    }
