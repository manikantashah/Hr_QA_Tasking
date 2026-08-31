from main import (
    executeSql,
    get_hr_data,
    extract_candidate_name
)

from candidate_resolver import (
    resolve_candidate_from_dataframe
)


def getOutput(
    question: str
):

    print("GET HR OUTPUT START")

    # ========================================================
    # 1. GET HR DATA
    # ========================================================

    master_df, work_experience_df = get_hr_data()

    print("Master rows:", len(master_df))
    print("Work experience rows:", len(work_experience_df))

    # ========================================================
    # 2. EXTRACT CANDIDATE NAME
    # ========================================================

    requested_candidate = extract_candidate_name(question)

    print("\nREQUESTED CANDIDATE:")
    print(requested_candidate)

    # ========================================================
    # 3. RESOLVE CANDIDATE NAME
    # ========================================================

    if requested_candidate:

        candidate_match = resolve_candidate_from_dataframe(
            master_df,
            requested_candidate
        )

        print("\nCANDIDATE MATCH RESULT:")
        print(candidate_match)

        # ====================================================
        # 3A. FUZZY MATCH / SUGGESTION
        # ====================================================

        if (
            candidate_match
            and candidate_match.get("status") == "SUGGEST"
        ):

            suggested_name = candidate_match.get("actual_name")

            return {
                "status": "WAITING_FOR_USER",
                "candidate_match": "SUGGEST",
                "requested_candidate": requested_candidate,
                "suggested_candidate": suggested_name,
                "original_question": question,
                "message": (
                    f"I couldn't find an exact match for "
                    f"'{requested_candidate}'. Did you mean "
                    f"'{suggested_name}'?"
                )
            }

        # ====================================================
        # 3B. CANDIDATE NOT FOUND
        # ====================================================

        if (
            candidate_match
            and candidate_match.get("status") == "NOT_FOUND"
        ):

            return {
                "status": "NOT_FOUND",
                "candidate_match": "NOT_FOUND",
                "requested_candidate": requested_candidate,
                "original_question": question,
                "message": (
                    f"I couldn't find a candidate matching "
                    f"'{requested_candidate}'."
                )
            }

        # ====================================================
        # 3C. EXACT MATCH
        # ====================================================

        if (
            candidate_match
            and candidate_match.get("status") == "EXACT"
        ):

            canonical_name = candidate_match.get("actual_name")

            print("\nCANDIDATE EXACT MATCH:")
            print(canonical_name)

            if canonical_name and requested_candidate != canonical_name:
                question = question.replace(
                    requested_candidate,
                    canonical_name
                )

    # ========================================================
    # 4. NORMAL HR Q&A
    # ========================================================

    response = executeSql(
        question,
        master_df,
        work_experience_df
    )

    print("GET HR OUTPUT END")

    return response
