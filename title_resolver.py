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
    title = re.sub(
        r"\s+",
        " ",
        title
    )

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

    normalized = normalize_title(
        title
    )

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

    Examples:

        "site engine"
        vs
        "site engineer"

        "site enginner"
        vs
        "site engineer"

        "site engineer"
        vs
        "senior site engineer"
    """

    title1 = normalize_title(
        title1
    )

    title2 = normalize_title(
        title2
    )

    if not title1 or not title2:
        return 0.0

    words1 = title1.split()
    words2 = title2.split()

    n1 = len(words1)
    n2 = len(words2)

    # Always make words1 the longer list
    if n1 < n2:

        words1, words2 = (
            words2,
            words1
        )

        n1, n2 = (
            n2,
            n1
        )

    normalized_title2 = " ".join(
        words2
    )

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

        scores.append(
            score
        )

    return (
        max(scores)
        if scores
        else 0.0
    )


# ============================================================
# TOKEN FUZZY SIMILARITY
# ============================================================

def token_fuzzy_similarity(
    requested_title: str,
    actual_title: str
) -> float:
    """
    Compare titles token by token.

    This helps with cases such as:

        Site Engine
        Site Engineer

    where one token is a shortened/partial version.
    """

    requested_tokens = get_title_tokens(
        requested_title
    )

    actual_tokens = get_title_tokens(
        actual_title
    )

    if (
        not requested_tokens
        or not actual_tokens
    ):
        return 0.0

    best_scores = []

    for requested_token in requested_tokens:

        best_score = 0.0

        for actual_token in actual_tokens:

            score = SequenceMatcher(
                None,
                requested_token,
                actual_token
            ).ratio()

            if score > best_score:
                best_score = score

        best_scores.append(
            best_score
        )

    if not best_scores:
        return 0.0

    return sum(
        best_scores
    ) / len(
        best_scores
    )


# ============================================================
# PREFIX TOKEN SIMILARITY
# ============================================================

def prefix_token_similarity(
    requested_title: str,
    actual_title: str
) -> float:
    """
    Compare tokens using prefix-style matching.

    Examples:

        engine
        engineer

    produce a strong match because one starts with
    the other.
    """

    requested_tokens = get_title_tokens(
        requested_title
    )

    actual_tokens = get_title_tokens(
        actual_title
    )

    if (
        not requested_tokens
        or not actual_tokens
    ):
        return 0.0

    scores = []

    for requested_token in requested_tokens:

        best_score = 0.0

        for actual_token in actual_tokens:

            # Exact token
            if requested_token == actual_token:
                score = 1.0

            # Requested token is prefix of actual token
            elif actual_token.startswith(
                requested_token
            ):
                score = 0.95

            # Actual token is prefix of requested token
            elif requested_token.startswith(
                actual_token
            ):
                score = 0.95

            else:
                score = SequenceMatcher(
                    None,
                    requested_token,
                    actual_token
                ).ratio()

            if score > best_score:
                best_score = score

        scores.append(
            best_score
        )

    if not scores:
        return 0.0

    return sum(
        scores
    ) / len(
        scores
    )


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
            site engineer

        actual:
            senior site engineer

        -> True


        requested:
            oracle hcm

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

    if (
        not requested_tokens
        or not actual_tokens
    ):
        return False

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

        if (
            current_tokens
            ==
            requested_tokens
        ):
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
    """

    requested_tokens = get_title_tokens(
        requested_title
    )

    actual_tokens = get_title_tokens(
        actual_title
    )

    if (
        not requested_tokens
        or not actual_tokens
    ):
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
        /
        len(requested_tokens)
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
            ==
            requested_tokens
        ):

            prefix_bonus = 0.2

    score = min(
        1.0,
        token_score + prefix_bonus
    )

    return score


# ============================================================
# GET TITLE LIST FROM JOB_REQUISITIONS RESULT
# ============================================================

def get_title_list(
    title_result
):
    """
    Extract the requisition list from JOB_REQUISITIONS.

    Supports:

        {
            "output": {
                "result": [...]
            }
        }

    Also supports output/result being JSON strings.
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

    if isinstance(
        output,
        str
    ):

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

    # --------------------------------------------------------
    # RESULT DIRECTLY CONTAINS LIST
    # --------------------------------------------------------

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
            str
        ):

            try:

                nested_result = json.loads(
                    nested_result
                )

            except (
                json.JSONDecodeError,
                TypeError
            ):

                nested_result = None

        if isinstance(
            nested_result,
            list
        ):

            return nested_result

        requisitions = result.get(
            "requisitions"
        )

        if isinstance(
            requisitions,
            str
        ):

            try:

                requisitions = json.loads(
                    requisitions
                )

            except (
                json.JSONDecodeError,
                TypeError
            ):

                requisitions = None

        if isinstance(
            requisitions,
            list
        ):

            return requisitions

    return []


# ============================================================
# BUILD TITLE MATCH
# ============================================================

def build_title_match(
    title: dict,
    requested_title: str,
    score: float,
    match_type: str
):
    """
    Build a consistent match object.
    """

    return {

        "requested_title":
            requested_title,

        "title":
            title.get(
                "Title"
            ),

        "requisition_number":
            title.get(
                "RequisitionNumber"
            ),

        "score":
            round(
                score,
                4
            ),

        "match_type":
            match_type,

        "requisition":
            title
    }


# ============================================================
# REMOVE DUPLICATE MATCHES
# ============================================================

def remove_duplicate_matches(
    matches
):
    """
    Remove duplicate records based on:

        title + requisition_number
    """

    unique_matches = []

    seen = set()

    for match in matches:

        if not isinstance(
            match,
            dict
        ):
            continue

        title = match.get(
            "title"
        )

        requisition_number = match.get(
            "requisition_number"
        )

        key = (
            normalize_title(
                title
            ),
            str(
                requisition_number
            )
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
# SORT TITLE MATCHES
# ============================================================

def sort_title_matches(
    matches
):
    """
    Sort strongest matches first.

    Exact matches appear before partial/fuzzy matches
    when scores are equal.
    """

    return sorted(

        matches,

        key=lambda item: (

            item.get(
                "score",
                0.0
            ),

            1
            if item.get(
                "match_type"
            ) == "EXACT"
            else 0

        ),

        reverse=True
    )


# ============================================================
# FIND ALL EXACT TITLE MATCHES
# ============================================================

def find_exact_title_matches(
    title_list,
    requested_title: str
):
    """
    Find ALL exact matches.

    Example:

        Site Engineer -> requisition 21
        Site Engineer -> requisition 102

    Both are returned.
    """

    requested_normalized = normalize_title(
        requested_title
    )

    matches = []

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
            ==
            requested_normalized
        ):

            matches.append(
                build_title_match(
                    title,
                    requested_title,
                    1.0,
                    "EXACT"
                )
            )

    return remove_duplicate_matches(
        matches
    )


# ============================================================
# FIND RELATED TITLE MATCHES
# ============================================================

def find_related_title_matches(
    title_list,
    requested_title: str,
    threshold: float = 0.70
):
    """
    Find related partial/fuzzy titles.

    Handles cases such as:

        Site Engine
        -> Site Engineer

        Site Enginner
        -> Site Engineer

        Site Engineer
        -> Site Engineer (Trainee)

        Site Engineer
        -> Senior Site Engineer
    """

    requested_normalized = normalize_title(
        requested_title
    )

    matches = []

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

        # ----------------------------------------------------
        # Skip exact titles
        # ----------------------------------------------------

        if (
            actual_normalized
            ==
            requested_normalized
        ):
            continue

        # ----------------------------------------------------
        # GENERAL FUZZY SCORE
        # ----------------------------------------------------

        fuzzy_score = title_similarity(
            requested_title,
            actual_title
        )

        # ----------------------------------------------------
        # PARTIAL TOKEN SCORE
        # ----------------------------------------------------

        partial_score = partial_title_score(
            requested_title,
            actual_title
        )

        # ----------------------------------------------------
        # TOKEN FUZZY SCORE
        # ----------------------------------------------------

        token_fuzzy_score = token_fuzzy_similarity(
            requested_title,
            actual_title
        )

        # ----------------------------------------------------
        # PREFIX TOKEN SCORE
        # ----------------------------------------------------

        prefix_score = prefix_token_similarity(
            requested_title,
            actual_title
        )

        # ----------------------------------------------------
        # STRONGEST SCORE
        # ----------------------------------------------------

        score = max(
            fuzzy_score,
            partial_score,
            token_fuzzy_score,
            prefix_score
        )

        # ----------------------------------------------------
        # PARTIAL MATCH
        # ----------------------------------------------------

        is_partial_match = partial_title_match(
            requested_title,
            actual_title
        )

        # ----------------------------------------------------
        # SHORT TITLE PREFIX CHECK
        # ----------------------------------------------------

        requested_tokens = get_title_tokens(
            requested_title
        )

        actual_tokens = get_title_tokens(
            actual_title
        )

        prefix_token_match = False

        if requested_tokens and actual_tokens:

            if len(requested_tokens) <= len(actual_tokens):

                prefix_token_match = True

                for index, requested_token in enumerate(
                    requested_tokens
                ):

                    actual_token = actual_tokens[index]

                    if not (
                        actual_token.startswith(
                            requested_token
                        )
                        or
                        requested_token.startswith(
                            actual_token
                        )
                    ):

                        prefix_token_match = False
                        break

        # ----------------------------------------------------
        # QUALIFIED MATCH
        # ----------------------------------------------------

        if (
            score >= threshold
            or is_partial_match
            or prefix_token_match
        ):

            if (
                is_partial_match
                or prefix_token_match
            ):

                match_type = "PARTIAL"

            else:

                match_type = "FUZZY"

            matches.append(
                build_title_match(
                    title,
                    requested_title,
                    score,
                    match_type
                )
            )

    return remove_duplicate_matches(
        matches
    )


# ============================================================
# FIND BEST TITLE
# ============================================================

def find_best_title(
    title_result,
    requested_title: str,
    threshold: float = 0.70
):
    """
    Resolve one requested title.

    Rules:

    1. If exactly one exact title exists:
           return EXACT

    2. If multiple exact titles exist:
           return MULTIPLE
           and include related matches as options

    3. If no exact title exists:
           use fuzzy/partial matching

    Possible results:

        EXACT
        SUGGEST
        MULTIPLE
        NOT_FOUND
    """

    # ========================================================
    # VALIDATE REQUEST
    # ========================================================

    if not requested_title:

        return {
            "status":
                "NOT_FOUND",

            "requested_title":
                requested_title
        }

    requested_title = str(
        requested_title
    ).strip()

    if not requested_title:

        return {
            "status":
                "NOT_FOUND",

            "requested_title":
                requested_title
        }

    # ========================================================
    # GET TITLE LIST
    # ========================================================

    title_list = get_title_list(
        title_result
    )

    if not title_list:

        return {
            "status":
                "NOT_FOUND",

            "requested_title":
                requested_title
        }

    # ========================================================
    # FIND EXACT MATCHES FIRST
    # ========================================================

    exact_matches = find_exact_title_matches(
        title_list,
        requested_title
    )

    # ========================================================
    # IMPORTANT RULE
    #
    # ONE EXACT MATCH = EXACT
    #
    # Do NOT allow fuzzy matches to override it.
    #
    # Example:
    #
    # Site Engineer (Trainee)
    #
    # Exact:
    #   Site Engineer (Trainee) -> 44
    #
    # Fuzzy:
    #   Site Engineer -> 21
    #   Site Engineer -> 102
    #
    # We ignore the fuzzy matches because an exact unique
    # match already exists.
    # ========================================================

    if len(
        exact_matches
    ) == 1:

        single_exact = exact_matches[0]

        return {
            "status":
                "EXACT",

            "requested_title":
                requested_title,

            "matched_title":
                single_exact.get(
                    "title"
                ),

            "requisition_number":
                single_exact.get(
                    "requisition_number"
                ),

            "requisition":
                single_exact.get(
                    "requisition"
                ),

            "score":
                single_exact.get(
                    "score",
                    1.0
                )
        }

    # ========================================================
    # MULTIPLE EXACT MATCHES
    #
    # Example:
    #
    # Site Engineer -> 21
    # Site Engineer -> 102
    #
    # In this situation we should NOT automatically select
    # one of them.
    #
    # We can also include related titles such as:
    #
    # Site Engineer (Trainee)
    # Senior Site Engineer
    # ========================================================

    if len(
        exact_matches
    ) > 1:

        related_matches = find_related_title_matches(
            title_list,
            requested_title,
            threshold
        )

        all_matches = []

        all_matches.extend(
            exact_matches
        )

        all_matches.extend(
            related_matches
        )

        all_matches = remove_duplicate_matches(
            all_matches
        )

        all_matches = sort_title_matches(
            all_matches
        )

        return {
            "status":
                "MULTIPLE",

            "requested_title":
                requested_title,

            "matches":
                all_matches
        }

    # ========================================================
    # NO EXACT MATCH
    #
    # Now fuzzy / partial matching is allowed.
    # ========================================================

    related_matches = find_related_title_matches(
        title_list,
        requested_title,
        threshold
    )

    related_matches = remove_duplicate_matches(
        related_matches
    )

    related_matches = sort_title_matches(
        related_matches
    )

    # ========================================================
    # NOTHING FOUND
    # ========================================================

    if not related_matches:

        return {
            "status":
                "NOT_FOUND",

            "requested_title":
                requested_title
        }

    # ========================================================
    # ONE RELATED MATCH
    # ========================================================

    if len(
        related_matches
    ) == 1:

        single_match = related_matches[0]

        return {
            "status":
                "SUGGEST",

            "requested_title":
                requested_title,

            "suggested_title":
                single_match.get(
                    "title"
                ),

            "requisition_number":
                single_match.get(
                    "requisition_number"
                ),

            "requisition":
                single_match.get(
                    "requisition"
                ),

            "score":
                single_match.get(
                    "score",
                    0.0
                )
        }

    # ========================================================
    # MULTIPLE RELATED MATCHES
    # ========================================================

    return {
        "status":
            "MULTIPLE",

        "requested_title":
            requested_title,

        "matches":
            related_matches
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

    Possible statuses:

        EXACT
        SUGGEST
        MULTIPLE
        NOT_FOUND
    """

    # ========================================================
    # VALIDATE REQUEST
    # ========================================================

    if not requested_title:

        return {
            "status":
                "NOT_FOUND",

            "requested_title":
                requested_title
        }

    requested_title = str(
        requested_title
    ).strip()

    if not requested_title:

        return {
            "status":
                "NOT_FOUND",

            "requested_title":
                requested_title
        }

    # ========================================================
    # FIND TITLE
    # ========================================================

    match = find_best_title(
        title_result,
        requested_title
    )

    # ========================================================
    # NO MATCH
    # ========================================================

    if not match:

        return {
            "status":
                "NOT_FOUND",

            "requested_title":
                requested_title
        }

    # ========================================================
    # EXACT
    # ========================================================

    if (
        match.get(
            "status"
        )
        ==
        "EXACT"
    ):

        return {
            "status":
                "EXACT",

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

    # ========================================================
    # SUGGEST
    # ========================================================

    if (
        match.get(
            "status"
        )
        ==
        "SUGGEST"
    ):

        return {
            "status":
                "SUGGEST",

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

    # ========================================================
    # MULTIPLE
    # ========================================================

    if (
        match.get(
            "status"
        )
        ==
        "MULTIPLE"
    ):

        return {
            "status":
                "MULTIPLE",

            "requested_title":
                requested_title,

            "matches":
                match.get(
                    "matches",
                    []
                )
        }

    # ========================================================
    # NOT FOUND
    # ========================================================

    return {
        "status":
            "NOT_FOUND",

        "requested_title":
            requested_title
    }
