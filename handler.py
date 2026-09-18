# ============================================================
# handler.py
# Chat With HR / HR Q&A
# ============================================================

import re
import json
from main import (
    executeSql,
    get_hr_data,
    extract_candidate_name,
    extract_title_name
)

from candidate_resolver import (
    resolve_candidate_from_dataframe
)

from title_resolver import (
    resolve_title
)


# ============================================================
# BUILD TITLE RESOLVER INPUT
# ============================================================

def _build_title_result(
    master_df
):
    """
    Convert master_df requisition information into the
    structure expected by title_resolver.py.
    """

    required_columns = [
        "requisition_title",
        "requisition_number"
    ]

    for column in required_columns:

        if column not in master_df.columns:

            return {
                "output": {
                    "result": []
                }
            }

    title_df = (
        master_df[
            [
                "requisition_title",
                "requisition_number"
            ]
        ]
        .copy()
    )

    title_df = title_df.dropna(
        subset=[
            "requisition_title"
        ]
    )

    title_df = title_df.drop_duplicates(
        subset=[
            "requisition_title",
            "requisition_number"
        ]
    )

    records = []

    for _, row in title_df.iterrows():

        title = row.get(
            "requisition_title"
        )

        requisition_number = row.get(
            "requisition_number"
        )

        if not title:
            continue

        records.append(
            {
                "Title":
                    str(
                        title
                    ).strip(),

                "RequisitionNumber":
                    (
                        str(
                            requisition_number
                        ).strip()
                        if requisition_number is not None
                        else None
                    )
            }
        )

    return {
        "output": {
            "result": records
        }
    }


# ============================================================
# FORMAT TITLE SUGGESTION
# ============================================================

def _format_title_with_requisition(
    title,
    requisition_number
):
    """
    Example:

        Site Engineer (Requisition 21)
    """

    if (
        title
        and
        requisition_number
    ):

        return (
            f"{title} "
            f"(Requisition {requisition_number})"
        )

    if title:

        return str(
            title
        ).strip()

    if requisition_number:

        return (
            f"Requisition "
            f"{requisition_number}"
        )

    return ""


# ============================================================
# EXTRACT EXPLICIT REQUISITION NUMBER
# ============================================================

def _extract_explicit_requisition_number(
    question
):
    """
    Extract the internal requisition instruction that is added
    after a user selects a title.

    Example:

        Use Requisition Number 121 for the resolved job title.

    Returns:

        "121"

    Otherwise:

        None
    """

    if not question:

        return None

    match = re.search(
        r"Use\s+Requisition\s+Number\s+(\d+)"
        r"\s+for\s+the\s+resolved\s+job\s+title",
        str(question),
        flags=re.IGNORECASE
    )

    if not match:

        return None

    return (
        match.group(
            1
        ).strip()
    )


# ============================================================
# REMOVE EXPLICIT REQUISITION INSTRUCTION
# ============================================================

def _remove_requisition_instruction(
    question
):
    """
    Remove the internal continuation instruction before
    extracting candidate/title information.

    Example:

        how many candidates are in Procurement Engineer

        Use Requisition Number 121 for the resolved job title.

    becomes:

        how many candidates are in Procurement Engineer
    """

    if not question:

        return ""

    cleaned_question = re.sub(
        r"Use\s+Requisition\s+Number\s+\d+"
        r"\s+for\s+the\s+resolved\s+job\s+title\.?",
        " ",
        str(question),
        flags=re.IGNORECASE
    )

    cleaned_question = re.sub(
        r"[ \t]+",
        " ",
        cleaned_question
    )

    cleaned_question = re.sub(
        r"\n\s*\n+",
        "\n\n",
        cleaned_question
    )

    return cleaned_question.strip()

# ============================================================
# DETECT REQUISITION COUNT QUERY
# ============================================================

def _is_requisition_count_query(
    question
):
    """
    Detect whether the user is asking for the total/count
    of requisitions for a job title.

    Examples:

        How many requisitions of Site Engineer?

        How many requisitions are there for Site Engineer?

        What is the total number of requisitions for Site Engineer?

        Give me the count of requisitions for Site Engineer.

        Total requisitions of Site Engineer?

        How many reqs are there for Site Engineer?
    """

    if not question:

        return False

    text = re.sub(
        r"\s+",
        " ",
        str(
            question
        ).strip().lower()
    )

    patterns = [
        r"\bhow many requisitions\b",
        r"\btotal number of requisitions\b",
        r"\btotal requisitions\b",
        r"\bnumber of requisitions\b",
        r"\bcount of requisitions\b",
        r"\bcount requisitions\b",
        r"\bhow many reqs\b",
        r"\btotal reqs\b",
        r"\bcount of reqs\b",
        r"\bcount reqs\b"
    ]

    for pattern in patterns:

        if re.search(
            pattern,
            text
        ):

            return True

    return False

# ============================================================
# DETECT WORK EXPERIENCE ROLE QUERY
# ============================================================

def _is_work_experience_role_query(
    question
):
    """
    Detect whether the user's title refers to a person's
    work-experience job title rather than a requisition title.

    Examples:

        How many years did Akhil Kotha work as Oracle HCM Consultant?

        How long did Akhil Kotha work as an Oracle HCM Consultant?

        What experience does Akhil Kotha have as Oracle HCM Consultant?

        How many months did Akhil Kotha work as HCM Consultant?

    These questions should use:

        work_experience_df.job_title

    and should NOT go through the requisition title resolver.
    """

    if not question:

        return False

    text = re.sub(
        r"\s+",
        " ",
        str(
            question
        ).strip().lower()
    )

    patterns = [
        r"\bworked\s+as\b",
        r"\bwork\s+as\b",
        r"\bworking\s+as\b",
        r"\bexperience\s+as\b",
        r"\bexperience\s+in\s+the\s+role\s+of\b",
        r"\bworked\s+in\s+the\s+role\s+of\b",
        r"\bwork\s+in\s+the\s+role\s+of\b",
        r"\bhow\s+many\s+years\b.*\bworked\s+as\b",
        r"\bhow\s+many\s+months\b.*\bworked\s+as\b",
        r"\bhow\s+long\b.*\bworked\s+as\b"
    ]

    for pattern in patterns:

        if re.search(
            pattern,
            text
        ):

            return True

    return False

# ============================================================
# RESOLVE TITLE USING EXPLICIT REQUISITION
# ============================================================

def _resolve_title_for_requisition(
    master_df,
    requested_title,
    requisition_number
):
    """
    Resolve the title inside an explicitly selected
    requisition.

    This is used when the user has already selected a
    specific requisition.

    Example:

        requested_title = "Procurement Engineer"
        requisition_number = "121"

    Result:

        {
            "status": "EXACT",
            "requested_title": "Procurement Engineer",
            "matched_title": "Procurement Engineer",
            "requisition_number": "121"
        }
    """

    if (
        master_df is None
        or
        not requested_title
        or
        not requisition_number
    ):

        return None

    required_columns = [
        "requisition_title",
        "requisition_number"
    ]

    for column in required_columns:

        if column not in master_df.columns:

            return None

    requested_title_normalized = (
        re.sub(
            r"\s+",
            " ",
            str(
                requested_title
            ).strip()
        ).lower()
    )

    requisition_normalized = (
        str(
            requisition_number
        ).strip()
    )

    # ========================================================
    # FIND SELECTED REQUISITION
    # ========================================================

    selected_rows = master_df[
        master_df[
            "requisition_number"
        ]
        .astype(str)
        .str.strip()
        ==
        requisition_normalized
    ].copy()

    if selected_rows.empty:

        print(
            "\nEXPLICIT REQUISITION NOT FOUND:"
        )

        print(
            requisition_normalized
        )

        return {
            "status":
                "NOT_FOUND",

            "requested_title":
                requested_title,

            "requisition_number":
                requisition_normalized
        }

    # ========================================================
    # EXACT TITLE INSIDE SELECTED REQUISITION
    # ========================================================

    selected_rows[
        "_normalized_title"
    ] = (
        selected_rows[
            "requisition_title"
        ]
        .astype(str)
        .str.replace(
            r"\s+",
            " ",
            regex=True
        )
        .str.strip()
        .str.lower()
    )

    exact_rows = selected_rows[
        selected_rows[
            "_normalized_title"
        ]
        ==
        requested_title_normalized
    ]

    if not exact_rows.empty:

        matched_title = (
            exact_rows.iloc[0][
                "requisition_title"
            ]
        )

        result = {
            "status":
                "EXACT",

            "requested_title":
                requested_title,

            "matched_title":
                str(
                    matched_title
                ).strip(),

            "requisition_number":
                requisition_normalized
        }

        print(
            "\nEXPLICIT REQUISITION RESOLUTION:"
        )

        print(
            result
        )

        return result

    # ========================================================
    # FALLBACK
    #
    # The requisition was explicitly selected, so use the
    # stored title for that requisition.
    # ========================================================

    first_row = (
        selected_rows.iloc[0]
    )

    matched_title = first_row.get(
        "requisition_title"
    )

    if matched_title:

        result = {
            "status":
                "EXACT",

            "requested_title":
                requested_title,

            "matched_title":
                str(
                    matched_title
                ).strip(),

            "requisition_number":
                requisition_normalized
        }

        print(
            "\nEXPLICIT REQUISITION RESOLUTION "
            "USING STORED TITLE:"
        )

        print(
            result
        )

        return result

    return {
        "status":
            "NOT_FOUND",

        "requested_title":
            requested_title,

        "requisition_number":
            requisition_normalized
    }


# ============================================================
# GET OUTPUT
# ============================================================

def getOutput(
    question: str
):

    print(
        "\n========================================"
    )

    print(
        "GET HR OUTPUT START"
    )

    print(
        "========================================"
    )

    # ========================================================
    # 1. LOAD HR DATA
    # ========================================================

    master_df, work_experience_df = (
        get_hr_data()
    )

    print(
        "Master rows:",
        len(master_df)
    )

    print(
        "Work experience rows:",
        len(work_experience_df)
    )

    # ========================================================
    # 2. EXTRACT INTERNAL EXPLICIT REQUISITION
    #
    # This is used when a previous title-selection step added:
    #
    # Use Requisition Number 121 for the resolved job title.
    # ========================================================

    explicit_requisition_number = (
        _extract_explicit_requisition_number(
            question
        )
    )

    if explicit_requisition_number:

        print(
            "\nEXPLICIT REQUISITION FOUND:"
        )

        print(
            explicit_requisition_number
        )

    # ========================================================
    # 3. REMOVE INTERNAL INSTRUCTION
    # ========================================================

    question_for_extraction = (
        _remove_requisition_instruction(
            question
        )
    )

    print(
        "\nQUESTION USED FOR EXTRACTION:"
    )

    print(
        question_for_extraction
    )

    # ========================================================
    # 4. EXTRACT CANDIDATE
    # ========================================================

    requested_candidate = (
        extract_candidate_name(
            question_for_extraction
        )
    )

    print(
        "\nREQUESTED CANDIDATE:"
    )

    print(
        requested_candidate
    )

    # ========================================================
    # 5. EXTRACT TITLE + REQUISITION NUMBER
    #
    # extract_title_name() now returns:
    #
    # {
    #     "title_name": "...",
    #     "requisition_number": "..."
    # }
    #
    # Example:
    #
    # {
    #     "title_name": "Site Engineer",
    #     "requisition_number": "44"
    # }
    # ========================================================

    title_info = extract_title_name(
        question_for_extraction
    )

    # --------------------------------------------------------
    # Safety check
    #
    # In case extract_title_name() returns None for any reason.
    # --------------------------------------------------------

    if not isinstance(
        title_info,
        dict
    ):

        title_info = {
            "title_name":
                None,

            "requisition_number":
                None
        }

    requested_title = (
        title_info.get(
            "title_name"
        )
    )

    requested_requisition_number = (
        title_info.get(
            "requisition_number"
        )
    )

    # ========================================================
    # DETERMINE WHETHER TITLE IS A WORK-EXPERIENCE ROLE
    # ========================================================

    is_work_experience_role_query = (
        _is_work_experience_role_query(
            question_for_extraction
        )
    )

    print(
        "\nWORK EXPERIENCE ROLE QUERY:"
    )

    print(
        is_work_experience_role_query
    )

    print(
            "\nTITLE / REQUISITION INFORMATION:")

    print(
            title_info)

    print(
        "\nREQUESTED TITLE:"
    )

    print(
        requested_title
    )

    print(
        "\nREQUESTED REQUISITION NUMBER:"
    )

    print(
        requested_requisition_number
    )

    # ========================================================
    # 6. RESOLVE CANDIDATE
    # ========================================================

    if requested_candidate:

        candidate_match = (
            resolve_candidate_from_dataframe(
                master_df,
                requested_candidate
            )
        )

        print(
            "\nCANDIDATE MATCH RESULT:"
        )

        print(
            candidate_match
        )

        # ====================================================
        # 6A. CANDIDATE SUGGESTION
        # ====================================================

        if (
            candidate_match
            and
            candidate_match.get(
                "status"
            )
            ==
            "SUGGEST"
        ):

            suggested_name = (
                candidate_match.get(
                    "actual_name"
                )
            )

            return {
                "status":
                    "WAITING_FOR_USER",

                "candidate_match":
                    "SUGGEST",

                "requested_candidate":
                    requested_candidate,

                "suggested_candidate":
                    suggested_name,

                "original_question":
                    question,

                "message":
                    (
                        f"I couldn't find an exact match for "
                        f"'{requested_candidate}'. "
                        f"Did you mean '{suggested_name}'?"
                    )
            }

        # ====================================================
        # 6B. CANDIDATE NOT FOUND
        # ====================================================

        if (
            candidate_match
            and
            candidate_match.get(
                "status"
            )
            ==
            "NOT_FOUND"
        ):

            return {
                "status":
                    "NOT_FOUND",

                "candidate_match":
                    "NOT_FOUND",

                "requested_candidate":
                    requested_candidate,

                "original_question":
                    question,

                "message":
                    (
                        f"I couldn't find a candidate matching "
                        f"'{requested_candidate}'."
                    )
            }

        # ====================================================
        # 6C. MULTIPLE CANDIDATES
        # ====================================================

        if (
            candidate_match
            and
            candidate_match.get(
                "status"
            )
            ==
            "MULTIPLE"
        ):

            matches = candidate_match.get(
                "matches",
                []
            )

            valid_matches = []

            for match in matches:

                if not isinstance(
                    match,
                    dict
                ):

                    continue

                candidate_data = (
                    match.get(
                        "candidate"
                    )
                )

                if not isinstance(
                    candidate_data,
                    dict
                ):

                    continue

                actual_name = (
                    match.get(
                        "actual_name"
                    )
                    or
                    match.get(
                        "candidate_name"
                    )
                    or
                    candidate_data.get(
                        "CandidateName"
                    )
                )

                email = (
                    match.get(
                        "email"
                    )
                    or
                    candidate_data.get(
                        "Email"
                    )
                )

                application_id = (
                    match.get(
                        "jobApplicationId"
                    )
                    or
                    match.get(
                        "job_application_id"
                    )
                    or
                    candidate_data.get(
                        "JobApplicationId"
                    )
                )

                if not actual_name:

                    continue

                valid_matches.append(
                    {
                        "candidate_name":
                            str(
                                actual_name
                            ).strip(),

                        "email":
                            email,

                        "jobApplicationId":
                            application_id,

                        "score":
                            match.get(
                                "score",
                                0.0
                            ),

                        "candidate":
                            candidate_data
                    }
                )

            if not valid_matches:

                return {
                    "status":
                        "NOT_FOUND",

                    "candidate_match":
                        "NOT_FOUND",

                    "requested_candidate":
                        requested_candidate,

                    "original_question":
                        question,

                    "message":
                        (
                            f"I could not find a usable candidate "
                            f"match for '{requested_candidate}'."
                        )
                }

            options = []

            for index, match in enumerate(
                valid_matches,
                start=1
            ):

                option = (
                    f"{index}. "
                    f"{match['candidate_name']}"
                )

                if match.get(
                    "email"
                ):

                    option += (
                        f" ({match['email']})"
                    )

                if match.get(
                    "jobApplicationId"
                ):

                    option += (
                        f" - Application "
                        f"{match['jobApplicationId']}"
                    )

                options.append(
                    option
                )

            return {
                "status":
                    "WAITING_FOR_USER",

                "candidate_match":
                    "MULTIPLE",

                "requested_candidate":
                    requested_candidate,

                "candidate_matches":
                    valid_matches,

                "original_question":
                    question,

                "message":
                    (
                        f"I found multiple candidates matching "
                        f"'{requested_candidate}'.\n\n"
                        +
                        "\n".join(
                            options
                        )
                        +
                        "\n\n"
                        "Please select one by option number."
                    )
            }

        # ====================================================
        # 6D. EXACT CANDIDATE
        # ====================================================

        if (
            candidate_match
            and
            candidate_match.get(
                "status"
            )
            ==
            "EXACT"
        ):

            canonical_name = (
                candidate_match.get(
                    "actual_name"
                )
            )

            print(
                "\nCANDIDATE EXACT MATCH:"
            )

            print(
                canonical_name
            )

            if (
                canonical_name
                and
                requested_candidate
                !=
                canonical_name
            ):

                question = (
                    question.replace(
                        requested_candidate,
                        canonical_name
                    )
                )

    # ========================================================
    # 7. TITLE RESOLUTION
    #
    # IMPORTANT:
    #
    # This must happen BEFORE executeSql().
    #
    # ALL title similarity/fuzzy logic remains inside
    # title_resolver.py.
    # ========================================================

    if (
    requested_title
    and
    not is_work_experience_role_query
):

        print(
            "\nBUILDING TITLE RESOLVER DATA..."
        )

        title_result = _build_title_result(
            master_df
        )

        print(
            "\nTITLE RESOLVER INPUT:"
        )

        print(
            title_result
        )

        # ====================================================
        # DETERMINE WHICH REQUISITION NUMBER TO USE
        #
        # There can be two sources:
        #
        # 1. User explicitly provided:
        #
        #    "Site Engineer requisition 44"
        #
        # 2. Previous multi-title selection added:
        #
        #    "Use Requisition Number 121 for the resolved
        #     job title."
        #
        # The internal continuation instruction has priority
        # because it represents a previously confirmed selection.
        # ====================================================

        requisition_to_use = (
            explicit_requisition_number
            or
            requested_requisition_number
        )

        print(
            "\nREQUISITION TO USE:"
        )

        print(
            requisition_to_use
        )

        # ====================================================
        # EXPLICIT REQUISITION
        # ====================================================

        if requisition_to_use:

            title_match = (
                _resolve_title_for_requisition(
                    master_df,
                    requested_title,
                    requisition_to_use
                )
            )

        # ====================================================
        # NO EXPLICIT REQUISITION
        #
        # Let title_resolver.py do the matching.
        # ====================================================

        else:

            title_match = resolve_title(
                title_result,
                requested_title
            )

        print(
            "\nTITLE MATCH RESULT:"
        )

        print(
            title_match
        )

        # ====================================================
        # 7A. TITLE NOT FOUND
        # ====================================================

        if (
            not title_match
            or
            title_match.get(
                "status"
            )
            ==
            "NOT_FOUND"
        ):

            return {
                "status":
                    "WAITING_FOR_USER",

                "title_match":
                    "NOT_FOUND",

                "requested_title":
                    requested_title,

                "requested_requisition_number":
                    requisition_to_use,

                "original_question":
                    question,

                "message":
                    (
                        f"I couldn't find a job title matching "
                        f"'{requested_title}'. "
                        "Please provide another job title."
                    )
            }

        title_status = (
            title_match.get(
                "status"
            )
        )
        # ========================================================
        # 7B. AGGREGATE REQUISITION COUNT
        #
        # Example:
        #
        # "How many requisitions of Site Engineer?"
        #
        # Do NOT select one requisition.
        #
        # If title resolver returns:
        #
        #   Site Engineer       -> 102
        #   Site Engineer       -> 21
        #   Senior Site Engineer -> 94
        #   Site Engineer (Trainee) -> 44
        #
        # only the EXACT title "Site Engineer" is used.
        #
        # SQL should count all matching requisitions.
        # ========================================================

        is_requisition_count_query = (
            _is_requisition_count_query(
                question_for_extraction
            )
        )

        if (
            is_requisition_count_query
            and
            not requisition_to_use
        ):

            print(
                "\nREQUISITION COUNT QUERY DETECTED:"
            )

            print(
                question_for_extraction
            )

            # ====================================================
            # CASE 1: MULTIPLE TITLE MATCHES
            # ====================================================

            if title_status == "MULTIPLE":

                matches = title_match.get(
                    "matches",
                    []
                )

                exact_title_matches = []

                requested_title_normalized = re.sub(
                    r"\s+",
                    " ",
                    str(
                        requested_title
                    ).strip()
                ).lower()

                if isinstance(
                    matches,
                    list
                ):

                    for match in matches:

                        if not isinstance(
                            match,
                            dict
                        ):

                            continue

                        matched_title = (
                            match.get(
                                "title"
                            )
                            or
                            match.get(
                                "matched_title"
                            )
                            or
                            match.get(
                                "Title"
                            )
                        )

                        if not matched_title:

                            continue

                        matched_title_normalized = re.sub(
                            r"\s+",
                            " ",
                            str(
                                matched_title
                            ).strip()
                        ).lower()

                        # ------------------------------------------------
                        # EXACT TITLE ONLY
                        # ------------------------------------------------

                        if (
                            matched_title_normalized
                            ==
                            requested_title_normalized
                        ):

                            exact_title_matches.append(
                                match
                            )

                # ====================================================
                # EXACT TITLE FOUND
                # ====================================================

                if exact_title_matches:

                    canonical_title = (
                        exact_title_matches[0].get(
                            "title"
                        )
                        or
                        exact_title_matches[0].get(
                            "matched_title"
                        )
                        or
                        exact_title_matches[0].get(
                            "Title"
                        )
                    )

                    canonical_title = str(
                        canonical_title
                    ).strip()

                    print(
                        "\nEXACT TITLE MATCHES FOR "
                        "REQUISITION COUNT:"
                    )

                    for match in exact_title_matches:

                        print(
                            json.dumps(
                                match,
                                indent=4,
                                default=str
                            )
                        )

                    print(
                        "\nCANONICAL TITLE:"
                    )

                    print(
                        canonical_title
                    )

                    # ------------------------------------------------
                    # Replace only the title in the original question.
                    #
                    # IMPORTANT:
                    # Do NOT add:
                    #
                    # Use Requisition Number 102...
                    #
                    # because this query must count ALL requisitions.
                    # ------------------------------------------------

                    if (
                        requested_title
                        and
                        canonical_title
                        and
                        requested_title.lower()
                        !=
                        canonical_title.lower()
                    ):

                        question = re.sub(
                            re.escape(
                                requested_title
                            ),
                            canonical_title,
                            question,
                            count=1,
                            flags=re.IGNORECASE
                        )

                    print(
                        "\nFINAL AGGREGATE QUESTION SENT TO executeSql:"
                    )

                    print(
                        question
                    )

                    response = executeSql(
                        question,
                        master_df,
                        work_experience_df
                    )

                    print(
                        "\nGET HR OUTPUT END"
                    )

                    return response

            # ====================================================
            # CASE 2: EXACT TITLE MATCH
            #
            # There is only one title/requisition in the data.
            #
            # Still do NOT append a requisition filter because
            # the user asked for a COUNT of requisitions.
            # ====================================================

            if title_status == "EXACT":

                matched_title = (
                    title_match.get(
                        "matched_title"
                    )
                )

                if matched_title:

                    matched_title = str(
                        matched_title
                    ).strip()

                    if (
                        requested_title
                        and
                        requested_title.lower()
                        !=
                        matched_title.lower()
                    ):

                        question = re.sub(
                            re.escape(
                                requested_title
                            ),
                            matched_title,
                            question,
                            count=1,
                            flags=re.IGNORECASE
                        )

                    print(
                        "\nEXACT TITLE COUNT QUERY:"
                    )

                    print(
                        "Title:",
                        matched_title
                    )

                    print(
                        "\nFINAL AGGREGATE QUESTION SENT TO executeSql:"
                    )

                    print(
                        question
                    )

                    response = executeSql(
                        question,
                        master_df,
                        work_experience_df
                    )

                    print(
                        "\nGET HR OUTPUT END"
                    )

                    return response

        # ====================================================
        # 7B. SINGLE TITLE SUGGESTION
        # ====================================================

        if title_status == "SUGGEST":

            suggested_title = (
                title_match.get(
                    "suggested_title"
                )
            )

            suggested_requisition = (
                title_match.get(
                    "requisition_number"
                )
            )

            display_title = (
                _format_title_with_requisition(
                    suggested_title,
                    suggested_requisition
                )
            )

            message = (
                f"I couldn't find an exact match for "
                f"'{requested_title}'. "
                f"Did you mean '{display_title}'?"
            )

            return {
                "status":
                    "WAITING_FOR_USER",

                "title_match":
                    "SUGGEST",

                "requested_title":
                    requested_title,

                "requested_requisition_number":
                    requisition_to_use,

                "suggested_title":
                    suggested_title,

                "suggested_requisition_number":
                    suggested_requisition,

                "suggested_title_display":
                    display_title,

                "original_question":
                    question,

                "message":
                    message
            }

        # ====================================================
        # 7C. MULTIPLE TITLE MATCHES
        # ====================================================

        if title_status == "MULTIPLE":

            matches = title_match.get(
                "matches",
                []
            )

            valid_matches = []

            if isinstance(
                matches,
                list
            ):

                for match in matches:

                    if not isinstance(
                        match,
                        dict
                    ):

                        continue

                    matched_title = (
                        match.get(
                            "title"
                        )
                        or
                        match.get(
                            "matched_title"
                        )
                        or
                        match.get(
                            "Title"
                        )
                    )

                    requisition_number = (
                        match.get(
                            "requisition_number"
                        )
                        or
                        match.get(
                            "RequisitionNumber"
                        )
                    )

                    if not matched_title:

                        continue

                    display_title = (
                        _format_title_with_requisition(
                            matched_title,
                            requisition_number
                        )
                    )

                    valid_matches.append(
                        {
                            "title":
                                str(
                                    matched_title
                                ).strip(),

                            "requisition_number":
                                (
                                    str(
                                        requisition_number
                                    ).strip()
                                    if requisition_number is not None
                                    else None
                                ),

                            "display":
                                display_title,

                            "score":
                                match.get(
                                    "score",
                                    0.0
                                ),

                            "match_type":
                                match.get(
                                    "match_type"
                                ),

                            "requisition":
                                match.get(
                                    "requisition"
                                )
                        }
                    )

            if not valid_matches:

                return {
                    "status":
                        "WAITING_FOR_USER",

                    "title_match":
                        "NOT_FOUND",

                    "requested_title":
                        requested_title,

                    "original_question":
                        question,

                    "message":
                        (
                            f"I could not resolve the job title "
                            f"'{requested_title}'. "
                            "Please provide another job title."
                        )
                }

            options = []

            for index, match in enumerate(
                valid_matches,
                start=1
            ):

                options.append(
                    f"{index}. "
                    f"{match['display']}"
                )

            options_text = "\n".join(
                options
            )

            message = (
                f"I found multiple job titles "
                f"matching '{requested_title}'. "
                f"Please select one:\n\n"
                f"{options_text}\n\n"
                "You can reply with the option number "
                "or the requisition number."
            )

            return {
                "status":
                    "WAITING_FOR_USER",

                "title_match":
                    "MULTIPLE",

                "requested_title":
                    requested_title,

                "title_matches":
                    valid_matches,

                "original_question":
                    question,

                "message":
                    message
            }

        # ====================================================
        # 7D. EXACT TITLE MATCH
        # ====================================================

        if title_status == "EXACT":

            matched_title = (
                title_match.get(
                    "matched_title"
                )
            )

            matched_requisition = (
                title_match.get(
                    "requisition_number"
                )
            )

            print(
                "\nTITLE EXACT MATCH:"
            )

            print(
                "Title:",
                matched_title
            )

            print(
                "Requisition:",
                matched_requisition
            )

            # ------------------------------------------------
            # Replace requested title with canonical title
            # ------------------------------------------------

            if (
                matched_title
                and
                requested_title
                and
                requested_title.lower()
                !=
                str(
                    matched_title
                ).lower()
            ):

                question = re.sub(
                    re.escape(
                        requested_title
                    ),
                    str(
                        matched_title
                    ),
                    question,
                    count=1,
                    flags=re.IGNORECASE
                )

            # ------------------------------------------------
            # Restrict SQL to selected requisition
            # ------------------------------------------------

            if matched_requisition:

                requisition_instruction = (
                    f"Use Requisition Number "
                    f"{matched_requisition} "
                    f"for the resolved job title."
                )

                if (
                    requisition_instruction.lower()
                    not in
                    question.lower()
                ):

                    question = (
                        f"{question}\n\n"
                        f"{requisition_instruction}"
                    )

    # ========================================================
    # 8. ONLY NOW CALL SQL
    # ========================================================

    print(
        "\nFINAL QUESTION SENT TO executeSql:"
    )

    print(
        question
    )

    response = executeSql(
        question,
        master_df,
        work_experience_df
    )

    print(
        "\nGET HR OUTPUT END"
    )

    return response
