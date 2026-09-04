
# ============================================================
# title_resolver.py
# ============================================================

import json
import re
from difflib import SequenceMatcher


# ============================================================
# NORMALIZE TITLE
# ============================================================

def normalize_title(title: str) -> str:
    """
    Normalize a job title for comparison.

    Example:
        "Site   Engineer"
        -> "site engineer"
    """

    if not title:
        return ""

    title = str(title).strip().lower()

    # Remove extra spaces
    title = re.sub(r"\s+", " ", title)

    return title


# ============================================================
# GET TITLE TOKENS
# ============================================================

def get_title_tokens(title: str):
    """
    Convert a title into normalized tokens.

    Example:
        "site engineer"
        -> ["site", "engineer"]
    """

    normalized = normalize_title(title)

    if not normalized:
        return []

    return normalized.split()


# ============================================================
# TITLE SIMILARITY
# ============================================================

def title_similarity(
    title1: str,
    title2: str
) -> float:
    """
    Calculate fuzzy similarity between two titles.

    For titles with different lengths, compare the shorter
    title against every equally-sized consecutive section
    of the longer title.

    Example:

        "site enginner"

        vs

        "senior site engineer"

    This allows the requested title to match a portion
    of a longer title.
    """

    title1 = normalize_title(title1)
    title2 = normalize_title(title2)

    if not title1 or not title2:
        return 0.0

    words1 = title1.split()
    words2 = title2.split()

    n1 = len(words1)
    n2 = len(words2)

    # Always make words1 the longer list
    if n1 < n2:
        words1, words2 = words2, words1
        n1, n2 = n2, n1

    normalized_title2 = " ".join(words2)

    scores = []

    for index in range(
        n1 - n2 + 1
    ):

        current_words = words1[
            index:index + n2
        ]

        normalized_title1 = " ".join(
            current_words
        )

        score = SequenceMatcher(
            None,
            normalized_title1,
            normalized_title2
        ).ratio()

        scores.append(score)

    return max(scores) if scores else 0.0


# ============================================================
# PARTIAL TITLE MATCH
# ============================================================

def partial_title_match(
    requested_title: str,
    actual_title: str
) -> bool:
    """
    Check whether the requested title appears as a
    meaningful consecutive part of the actual title.

    Examples:

        requested:
            site engineer

        actual:
            site engineer trainee

        -> True

        requested:
            oracle hcm

        actual:
            oracle hcm consultant

        -> True

        requested:
            oracle

        actual:
            oracle hcm consultant

        -> True
    """

    requested_tokens = get_title_tokens(
        requested_title
    )

    actual_tokens = get_title_tokens(
        actual_title
    )

    if not requested_tokens or not actual_tokens:
        return False

    # --------------------------------------------------------
    # SINGLE TOKEN
    # --------------------------------------------------------

    if len(requested_tokens) == 1:

        return (
            requested_tokens[0]
            in actual_tokens
        )

    # --------------------------------------------------------
    # MULTIPLE TOKENS
    # --------------------------------------------------------

    requested_length = len(
        requested_tokens
    )

    actual_length = len(
        actual_tokens
    )

    if requested_length > actual_length:
        return False

    for index in range(
        actual_length - requested_length + 1
    ):

        current_tokens = actual_tokens[
            index:index + requested_length
        ]

        if current_tokens == requested_tokens:
            return True

    return False


# ============================================================
# PARTIAL TITLE SCORE
# ============================================================

def partial_title_score(
    requested_title: str,
    actual_title: str
) -> float:
    """
    Calculate a token-based partial score.

    Example:

        requested:
            oracle hcm

        actual:
            oracle hcm consultant

        token score = 1.0
        prefix bonus = 0.2
        final score = 1.0
    """

    requested_tokens = get_title_tokens(
        requested_title
    )

    actual_tokens = get_title_tokens(
        actual_title
    )

    if not requested_tokens or not actual_tokens:
        return 0.0

    # --------------------------------------------------------
    # COUNT MATCHING TOKENS
    # --------------------------------------------------------

    matched_tokens = 0

    for token in requested_tokens:

        if token in actual_tokens:
            matched_tokens += 1

    token_score = (
        matched_tokens
        / len(requested_tokens)
    )

    # --------------------------------------------------------
    # PREFIX BONUS
    # --------------------------------------------------------

    prefix_bonus = 0.0

    if len(actual_tokens) >= len(
        requested_tokens
    ):

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
# GET TITLE LIST FROM JOBREQUISITIONHR RESULT
# ============================================================

def get_title_list(title_result):
    """
    Extract the requisition list from JOBREQUISITIONHR.

    Expected structure:

    {
        "output": "{\"result\":[
            {
                "RequisitionNumber": "44",
                "Title": "Site Engineer"
            }
        ]}"
    }

    Also supports:

    {
        "output": {
            "result": [...]
        }
    }

    and nested result structures.
    """

    # --------------------------------------------------------
    # VALIDATE INPUT
    # --------------------------------------------------------

    if not isinstance(
        title_result,
        dict
    ):
        return []

    # --------------------------------------------------------
    # GET OUTPUT
    # --------------------------------------------------------

    output = title_result.get(
        "output"
    )

    if output is None:
        return []

    # --------------------------------------------------------
    # OUTPUT MAY BE JSON STRING
    # --------------------------------------------------------

    if isinstance(output, str):

        output = output.strip()

        if not output:
            return []

        try:

            output = json.loads(
                output
            )

        except (
            json.JSONDecodeError,
            TypeError
        ):

            return []

    # --------------------------------------------------------
    # OUTPUT MUST BE DICT
    # --------------------------------------------------------

    if not isinstance(
        output,
        dict
    ):
        return []

    # --------------------------------------------------------
    # GET RESULT
    # --------------------------------------------------------

    result = output.get(
        "result"
    )

    if result is None:
        return []

    # --------------------------------------------------------
    # RESULT DIRECTLY CONTAINS LIST
    # --------------------------------------------------------

    if isinstance(
        result,
        list
    ):
        return result

    # --------------------------------------------------------
    # RESULT MAY BE JSON STRING
    # --------------------------------------------------------

    if isinstance(
        result,
        str
    ):

        result = result.strip()

        if not result:
            return []

        try:

            result = json.loads(
                result
            )

        except (
            json.JSONDecodeError,
            TypeError
        ):

            return []

        if isinstance(
            result,
            list
        ):
            return result

    # --------------------------------------------------------
    # RESULT MAY BE NESTED
    # --------------------------------------------------------

    if isinstance(
        result,
        dict
    ):

        nested_result = result.get(
            "result"
        )

        if isinstance(
            nested_result,
            list
        ):
            return nested_result

        # Sometimes data may be inside
        # "requisitions"
        requisitions = result.get(
            "requisitions"
        )

        if isinstance(
            requisitions,
            list
        ):
            return requisitions

    return []


# ============================================================
# FIND BEST TITLE
# ============================================================

def find_best_title(
    title_result,
    requested_title: str,
    threshold: float = 0.75
):
    """
    Find the best SINGLE job-title match.

    IMPORTANT:
        Exact match   -> EXACT
        Fuzzy match   -> SUGGEST
        Partial match -> SUGGEST
        No match      -> NOT_FOUND

    A fuzzy or partial match is NEVER automatically
    accepted.
    """

    # --------------------------------------------------------
    # VALIDATE REQUEST
    # --------------------------------------------------------

    if not requested_title:
        return None

    requested_title = str(
        requested_title
    ).strip()

    if not requested_title:
        return None

    requested_normalized = normalize_title(
        requested_title
    )

    # --------------------------------------------------------
    # GET TITLE LIST
    # --------------------------------------------------------

    title_list = get_title_list(
        title_result
    )

    if not title_list:
        return None

    # ========================================================
    # 1. EXACT MATCH
    # ========================================================

    for title in title_list:

        if not isinstance(
            title,
            dict
        ):
            continue

        actual_title = title.get(
            "Title"
        )

        if not actual_title:
            continue

        actual_normalized = normalize_title(
            actual_title
        )

        if (
            actual_normalized
            == requested_normalized
        ):

            return {
                "status": "EXACT",
                "requested_title":
                    requested_title,
                "matched_title":
                    actual_title,
                "requisition_number":
                    title.get(
                        "RequisitionNumber"
                    ),
                "requisition":
                    title,
                "score": 1.0
            }

    # ========================================================
    # 2. SEARCH PARTIAL / FUZZY MATCHES
    # ========================================================

    best_title = None
    best_score = 0.0

    for title in title_list:

        if not isinstance(
            title,
            dict
        ):
            continue

        actual_title = title.get(
            "Title"
        )

        if not actual_title:
            continue

        # ----------------------------------------------------
        # FUZZY SCORE
        # ----------------------------------------------------

        fuzzy_score = title_similarity(
            requested_title,
            actual_title
        )

        # ----------------------------------------------------
        # PARTIAL SCORE
        # ----------------------------------------------------

        partial_score = partial_title_score(
            requested_title,
            actual_title
        )

        # ----------------------------------------------------
        # STRONGEST SCORE
        # ----------------------------------------------------

        score = max(
            fuzzy_score,
            partial_score
        )

        # ----------------------------------------------------
        # PARTIAL MATCH
        # ----------------------------------------------------

        is_partial_match = (
            partial_title_match(
                requested_title,
                actual_title
            )
        )

        # ----------------------------------------------------
        # SELECT BEST MATCH
        # ----------------------------------------------------

        if (
            score > best_score
            and (
                score >= threshold
                or is_partial_match
            )
        ):

            best_score = score

            best_title = title

    # ========================================================
    # 3. SUGGESTION
    # ========================================================

    if best_title:

        return {
            "status": "SUGGEST",
            "requested_title":
                requested_title,
            "suggested_title":
                best_title.get(
                    "Title"
                ),
            "requisition_number":
                best_title.get(
                    "RequisitionNumber"
                ),
            "requisition":
                best_title,
            "score":
                round(
                    best_score,
                    4
                )
        }

    # ========================================================
    # 4. NOT FOUND
    # ========================================================

    return {
        "status": "NOT_FOUND",
        "requested_title":
            requested_title
    }


# ============================================================
# RESOLVE SINGLE TITLE
# ============================================================

def resolve_title(
    title_result,
    requested_title: str
):
    """
    Public function used by scheduling_flow().

    This resolver handles ONLY ONE title.

    Examples:

        "Site Engineer"
            -> EXACT

        "sit enginner"
            -> SUGGEST

        "xyz manager"
            -> NOT_FOUND
    """

    # --------------------------------------------------------
    # VALIDATE REQUEST
    # --------------------------------------------------------

    if not requested_title:

        return {
            "status": "NOT_FOUND",
            "requested_title":
                requested_title
        }

    requested_title = str(
        requested_title
    ).strip()

    if not requested_title:

        return {
            "status": "NOT_FOUND",
            "requested_title":
                requested_title
        }

    # --------------------------------------------------------
    # FIND BEST MATCH
    # --------------------------------------------------------

    match = find_best_title(
        title_result,
        requested_title
    )

    # --------------------------------------------------------
    # NO MATCH OBJECT
    # --------------------------------------------------------

    if not match:

        return {
            "status": "NOT_FOUND",
            "requested_title":
                requested_title
        }

    # --------------------------------------------------------
    # EXACT
    # --------------------------------------------------------

    if match["status"] == "EXACT":

        return {
            "status": "EXACT",

            "requested_title":
                requested_title,

            "matched_title":
                match.get(
                    "matched_title"
                ),

            "requisition_number":
                match.get(
                    "requisition_number"
                ),

            "requisition":
                match.get(
                    "requisition"
                ),

            "score":
                match.get(
                    "score",
                    1.0
                )
        }

    # --------------------------------------------------------
    # SUGGESTION
    # --------------------------------------------------------

    if match["status"] == "SUGGEST":

        return {
            "status": "SUGGEST",

            "requested_title":
                requested_title,

            "suggested_title":
                match.get(
                    "suggested_title"
                ),

            "requisition_number":
                match.get(
                    "requisition_number"
                ),

            "requisition":
                match.get(
                    "requisition"
                ),

            "score":
                match.get(
                    "score",
                    0.0
                )
        }

    # --------------------------------------------------------
    # NOT FOUND
    # --------------------------------------------------------

    return {
        "status": "NOT_FOUND",

        "requested_title":
            requested_title
    }

