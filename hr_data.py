import requests
import pandas as pd


MASTER_API_URL = (
    "http://139.185.51.13:8080/ords/"
    "xxcust/XXSH_AAR_APP/HrChatMaster"
)

WORK_EXPERIENCE_API_URL = (
    "http://139.185.51.13:8080/ords/"
    "xxcust/XXSH_AAR_APP/HrChatWorkExperience"
)


def get_api_data(url):

    response = requests.get(url)
    response.raise_for_status()

    data = response.json()

    return data["items"]


def create_hr_tables():

    # ========================================================
    # MASTER API
    # ========================================================

    master_records = get_api_data(
        MASTER_API_URL
    )

    master_df = pd.DataFrame(
        master_records
    )


    # ========================================================
    # WORK EXPERIENCE API
    # ========================================================

    work_experience_records = get_api_data(
        WORK_EXPERIENCE_API_URL
    )

    work_experience_df = pd.DataFrame(
        work_experience_records
    )


    # ========================================================
    # NORMALIZE JOIN KEYS
    # ========================================================

    join_keys = [
        "screening_header_id",
        "requisition_header_id",
        "candidate_line_id"
    ]

    for key in join_keys:

        master_df[key] = (
            master_df[key]
            .astype(str)
            .str.replace(
                ".0",
                "",
                regex=False
            )
            .str.strip()
        )

        work_experience_df[key] = (
            work_experience_df[key]
            .astype(str)
            .str.replace(
                ".0",
                "",
                regex=False
            )
            .str.strip()
        )


    return (
        master_df,
        work_experience_df
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    master_df, work_experience_df = (
        create_hr_tables()
    )

    print("\n================ MASTER TABLE ================\n")

    print(
        master_df.to_string(
            index=False
        )
    )

    print("\n================ WORK EXPERIENCE TABLE ================\n")

    print(
        work_experience_df.to_string(
            index=False
        )
    )