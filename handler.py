# ============================================================
# handler.py
# Chat With HR / HR Q&A
# ============================================================

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
    Convert master_df requisition information into the structure
    expected by title_resolver.py.

    title_resolver expects:

        {
            "output": {
                "result": [
                    {
                        "Title": "...",
                        "RequisitionNumber": "..."
                    }
                ]
            }
        }
    """

    required_columns = [
        "requisition_title",
        "requisition_number"
    ]

    # --------------------------------------------------------
    # Check required columns
    # --------------------------------------------------------

    for column in required_columns:

        if column not in master_df.columns:

            return {
                "output": {
                    "result": []
                }
            }

    # --------------------------------------------------------
    # Extract title + requisition
    # --------------------------------------------------------

    title_df = (
        master_df[
            [
                "requisition_title",
                "requisition_number"
            ]
        ]
        .copy()
    )

    # --------------------------------------------------------
    # Remove records without a title
    # --------------------------------------------------------

    title_df = title_df.dropna(
        subset=[
            "requisition_title"
        ]
    )

    # --------------------------------------------------------
    # Remove duplicate title/requisition combinations
    # --------------------------------------------------------

    title_df = title_df.drop_duplicates(
        subset=[
            "requisition_title",
            "requisition_number"
        ]
    )

    # --------------------------------------------------------
    # Convert to title_resolver format
    # --------------------------------------------------------

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
    Format title suggestion as:

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
    # 1. GET HR DATA
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
    # 2. EXTRACT CANDIDATE NAME
    # ========================================================

    requested_candidate = (
        extract_candidate_name(
            question
        )
    )

    print(
        "\nREQUESTED CANDIDATE:"
    )

    print(
        requested_candidate
    )

    # ========================================================
    # 3. EXTRACT TITLE
    # ========================================================

    requested_title = (
        extract_title_name(
            question
        )
    )

    print(
        "\nREQUESTED TITLE:"
    )

    print(
        requested_title
    )

    # ========================================================
    # 4. RESOLVE CANDIDATE NAME
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
        # 4A. FUZZY MATCH / SUGGESTION
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
        # 4B. CANDIDATE NOT FOUND
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
        # 4C. MULTIPLE CANDIDATES
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

            message = (
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
                    message
            }

        # ====================================================
        # 4D. EXACT MATCH
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
    # 5. RESOLVE TITLE
    # ========================================================

    if requested_title:

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
        # 5A. TITLE NOT FOUND
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
                    "NOT_FOUND",

                "title_match":
                    "NOT_FOUND",

                "requested_title":
                    requested_title,

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

        # ====================================================
        # 5B. SINGLE TITLE SUGGESTION
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
        # 5C. MULTIPLE TITLE MATCHES
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
        # 5D. EXACT TITLE MATCH
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
            # Replace title in question with canonical title
            # ------------------------------------------------

            if (
                matched_title
                and
                requested_title != matched_title
            ):

                question = (
                    question.replace(
                        requested_title,
                        matched_title
                    )
                )

            # ------------------------------------------------
            # Restrict SQL to the resolved requisition.
            #
            # This is important because a title can belong to
            # multiple requisitions.
            # ------------------------------------------------

            if matched_requisition:

                # We append a clarification to the question
                # so SQL generation uses this requisition.
                question = (
                    f"{question}\n\n"
                    f"Use Requisition Number "
                    f"{matched_requisition} for the resolved "
                    f"job title."
                )

    # ========================================================
    # 6. NORMAL HR Q&A
    # ========================================================

    response = executeSql(
        question,
        master_df,
        work_experience_df
    )

    print(
        "\nGET HR OUTPUT END"
    )

    return response
