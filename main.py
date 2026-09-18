import json
import os
import operator
import re
import pandas as pd
from pandasql import sqldf
from typing import Literal, Annotated
from typing_extensions import TypedDict
from hr_data import create_hr_tables
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_core.prompts import PromptTemplate
from langchain_oci import ChatOCIGenAI

from langgraph.graph import StateGraph, START, END

from hr_data import create_hr_tables

# ============================================================
# 1. Load environment variables
# ============================================================

load_dotenv()

CONFIG = os.getenv("ConfigPath")


# ============================================================
# 2. Create Intent LLM
# ============================================================

llm_intent = ChatOCIGenAI(

    

    model_id="cohere.command-a-03-2025",
    service_endpoint="https://inference.generativeai.eu-frankfurt-1.oci.oraclecloud.com",
    compartment_id="ocid1.compartment.oc1..aaaaaaaa2jjkoqmd23eccvazv4u6dx746sx7ltkytcxb7swfjibcqdvw6blq",
    auth_profile="DEFAULT",
    auth_file_location= CONFIG, 
    model_kwargs={"max_tokens": 4000}
)



# ============================================================
# 3. Create Query Generator LLM
# ============================================================

query_generator = ChatOCIGenAI(
    model_id="cohere.command-a-03-2025",
        service_endpoint="https://inference.generativeai.eu-frankfurt-1.oci.oraclecloud.com",
        compartment_id="ocid1.compartment.oc1..aaaaaaaa2jjkoqmd23eccvazv4u6dx746sx7ltkytcxb7swfjibcqdvw6blq",
        auth_profile="DEFAULT",
        auth_file_location= CONFIG, 
        model_kwargs={"max_tokens": 4000}
    
)


# ============================================================
# 4. Create Query Evaluator LLM
# ============================================================

query_evaluator = ChatOCIGenAI(
    model_id="cohere.command-a-03-2025",
    service_endpoint="https://inference.generativeai.eu-frankfurt-1.oci.oraclecloud.com",
    compartment_id="ocid1.compartment.oc1..aaaaaaaa2jjkoqmd23eccvazv4u6dx746sx7ltkytcxb7swfjibcqdvw6blq",
    auth_profile="DEFAULT",
    auth_file_location= CONFIG, 
    model_kwargs={"max_tokens": 4000}
)


# ============================================================
# 5. Create Query Optimizer LLM
# ============================================================

query_optimizer = ChatOCIGenAI(
    model_id="cohere.command-a-03-2025",
    service_endpoint="https://inference.generativeai.eu-frankfurt-1.oci.oraclecloud.com",
    compartment_id="ocid1.compartment.oc1..aaaaaaaa2jjkoqmd23eccvazv4u6dx746sx7ltkytcxb7swfjibcqdvw6blq",
    auth_profile="DEFAULT",
    auth_file_location= CONFIG, 
    model_kwargs={"max_tokens": 4000}
)

#6.Result_summarizer_llm

result_summarizer_llm = ChatOCIGenAI(
    model_id="cohere.command-a-03-2025",
    service_endpoint="https://inference.generativeai.eu-frankfurt-1.oci.oraclecloud.com",
    compartment_id="ocid1.compartment.oc1..aaaaaaaa2jjkoqmd23eccvazv4u6dx746sx7ltkytcxb7swfjibcqdvw6blq",
    auth_profile="DEFAULT",
    auth_file_location= CONFIG, 
    model_kwargs={"max_tokens": 4000}
)

# ============================================================
# ROUTE DECISION
# ============================================================

class RouteDecision(BaseModel):

    route: Literal[
        "HYBRID_ROUTE",
        "UNKNOWN_ROUTE"
    ] = Field(
        description=(
            "The data source route selected based on the user's "
            "HR recruitment question."
        )
    )

    reason: str = Field(
        description=(
            "Explanation for why this route was selected."
        )
    )


# ============================================================
# QUERY STATE
# ============================================================

class QueryState(TypedDict):

    question: str

    master_df: pd.DataFrame

    work_experience_df: pd.DataFrame

    route_reason: str

    route: Literal[
        "UNKNOWN_ROUTE",
        "HYBRID_ROUTE"
    ]

    query: str

    evaluation: Literal[
        "approved",
        "needs_improvement"
    ]

    feedback: str

    iteration: int

    max_iteration: int

    sql_result: str

    result_summary: str

    query_history: Annotated[
        list[str],
        operator.add
    ]

    feedback_history: Annotated[
        list[str],
        operator.add
    ]


# ============================================================
# EXTRACT CANDIDATE NAME
# ============================================================

def extract_candidate_name(
    question: str
):
    """
    Extract a specific candidate name from the question.

    Returns:
        candidate name
        or None
    """

    prompt = f"""

You are an HR Recruitment Question Analyzer.

Determine whether the user's question refers to one specific
candidate.

USER QUESTION:

{question}

Rules:

1. Extract the candidate name if a specific candidate is mentioned.

2. Preserve the candidate name exactly as the user typed it.

3. Do not correct spelling.

4. Do not invent a candidate name.

5. If no specific candidate is mentioned, return null.

Examples:

Question:
"can u give me the skills of the Mamdou Salem?"

Return:
{{"candidate_name": "Mamdou Salem"}}

Question:
"what is the email of Jithu Daniel?"

Return:
{{"candidate_name": "Jithu Daniel"}}

Question:
"show me all candidates in requisition 44"

Return:
{{"candidate_name": null}}

Return ONLY valid JSON.
"""

    try:

        response = llm_intent.invoke(
            prompt
        )

        content = response.content.strip()

        if content.startswith(
            "```"
        ):

            content = content.replace(
                "```json",
                ""
            )

            content = content.replace(
                "```",
                ""
            )

            content = content.strip()

        result = json.loads(
            content
        )

        return result.get(
            "candidate_name"
        )

    except Exception:

        return None


# ============================================================
# EXTRACT TITLE NAME
# ============================================================

# ============================================================
# EXTRACT TITLE + REQUISITION NUMBER
# ============================================================

def extract_title_name(
    question: str
):
    """
    Extract a job/requisition title and requisition number
    from the user's question.

    IMPORTANT:

    This function ONLY extracts what the user mentioned.

    It does NOT:
        - correct the title
        - fuzzy match the title
        - resolve the title
        - select a requisition
        - compare against database titles

    All title matching/resolution must be handled by
    title_resolver.py.

    Returns:

        {
            "title_name": "...",
            "requisition_number": "..."
        }

    Example:

        "What is the status of the Site Engineer?"

        ->
        {
            "title_name": "Site Engineer",
            "requisition_number": None
        }

    Example:

        "What is the status of Site Engineer requisition 44?"

        ->
        {
            "title_name": "Site Engineer",
            "requisition_number": "44"
        }

    Example:

        "What is the status of requisition 44?"

        ->
        {
            "title_name": None,
            "requisition_number": "44"
        }
    """

    prompt = f"""

You are an HR Recruitment Question Analyzer.

Read the ENTIRE user question and extract TWO independent
pieces of information:

1. The job title / position / requisition title, if the user
   refers to one.

2. The requisition number, if the user explicitly provides one.

USER QUESTION:

{question}


============================================================
JOB TITLE EXTRACTION RULES
============================================================

1. Read the entire question before extracting the title.

2. Extract the job title if the user appears to be referring
   to a specific job title / position / requisition title.

3. The job title may appear ANYWHERE in the sentence.

4. The title may be:

   - an exact title
   - a partial title
   - an abbreviated title
   - a misspelled title
   - an informal title reference

5. Preserve the title EXACTLY as the user typed it.

6. Do NOT correct spelling.

7. Do NOT fuzzy match the title.

8. Do NOT resolve the title.

9. Do NOT invent a title.

10. Do NOT require the title to exactly match a database title.

11. If the user clearly appears to refer to a title, extract it
    even when the title is abbreviated or incomplete.

12. Do NOT extract a requisition number as the title.

13. Do NOT return a candidate name as the title.

14. A title may contain:

    - spaces
    - hyphens
    - numbers
    - parentheses
    - abbreviations


============================================================
REQUISITION NUMBER RULES
============================================================

1. Extract the requisition number whenever the user explicitly
   provides one.

2. A requisition number is numeric.

3. Examples:

   44
   121
   130
   1024

4. The requisition number can appear anywhere in the question.

5. Do NOT treat the requisition number as part of the job title.

6. Preserve the requisition number exactly as provided.

7. If no requisition number is provided, return null.


============================================================
EXAMPLES
============================================================


Question:

"What is the state of the Site Engineer?"

Return:

{{"title_name": "Site Engineer", "requisition_number": null}}


Question:

"What is the status of Site Enginner?"

Return:

{{"title_name": "Site Enginner", "requisition_number": null}}


Question:

"What is the status of the hcm?"

Return:

{{"title_name": "hcm", "requisition_number": null}}


Question:

"How many candidates are in oracle hcm?"

Return:

{{"title_name": "oracle hcm", "requisition_number": null}}


Question:

"Tell me about Python SDE-1."

Return:

{{"title_name": "Python SDE-1", "requisition_number": null}}


Question:

"What is the status of requisition 44?"

Return:

{{"title_name": null, "requisition_number": "44"}}


Question:

"Show all candidates in requisition 44."

Return:

{{"title_name": null, "requisition_number": "44"}}


Question:

"What is the status of Site Engineer requisition 44?"

Return:

{{"title_name": "Site Engineer", "requisition_number": "44"}}


Question:

"How many candidates are in Oracle HCM requisition 130?"

Return:

{{"title_name": "Oracle HCM", "requisition_number": "130"}}


Question:

"What is the status of the HCM Consultant for requisition 139?"

Return:

{{"title_name": "HCM Consultant", "requisition_number": "139"}}


Question:

"Give me the AI score of Jithu Daniel."

Return:

{{"title_name": null, "requisition_number": null}}


Question:

"What is the education of Mamdou Salem?"

Return:

{{"title_name": null, "requisition_number": null}}


Question:

"Who is the highest scoring candidate?"

Return:

{{"title_name": null, "requisition_number": null}}


Question:

"How many candidates are there?"

Return:

{{"title_name": null, "requisition_number": null}}


============================================================
IMPORTANT
============================================================

The title and requisition number are independent.

For example:

"status of Site Engineer requisition 44"

means:

title_name = "Site Engineer"

requisition_number = "44"

Do NOT return:

"Site Engineer requisition 44"

as the title.

Return ONLY valid JSON.

Do not return markdown.

Do not return code fences.

Do not return any text outside the JSON object.
"""

    try:

        response = llm_intent.invoke(
            prompt
        )

        content = response.content.strip()

        # ----------------------------------------------------
        # Remove markdown code fences if the model returns them
        # ----------------------------------------------------

        if content.startswith(
            "```"
        ):

            content = content.replace(
                "```json",
                ""
            )

            content = content.replace(
                "```",
                ""
            )

            content = content.strip()

        

        # ----------------------------------------------------
        # Parse JSON
        # ----------------------------------------------------

        try:

            result = json.loads(
                content
            )

        except json.JSONDecodeError:

            print(
                "\nNORMAL JSON PARSING FAILED."
            )

            print(
                "Trying JSON parsing with strict=False..."
            )

            result = json.loads(
                content,
                strict=False
            )

        # ----------------------------------------------------
        # Extract title
        # ----------------------------------------------------

        title = result.get(
            "title_name"
        )

        if title is not None:

            title = str(
                title
            ).strip()

            if not title:

                title = None

        # ----------------------------------------------------
        # Extract requisition number
        # ----------------------------------------------------

        requisition_number = result.get(
            "requisition_number"
        )

        if requisition_number is not None:

            requisition_number = str(
                requisition_number
            ).strip()

            if not requisition_number:

                requisition_number = None

        # ----------------------------------------------------
        # Return both values
        # ----------------------------------------------------

        return {
            "title_name":
                title,

            "requisition_number":
                requisition_number
        }

    except Exception as exc:

        print(
            "\nTITLE / REQUISITION EXTRACTION ERROR:"
        )

        print(
            exc
        )

        return {
            "title_name":
                None,

            "requisition_number":
                None
        }

# ============================================================
# GET HR DATA
# ============================================================

def get_hr_data():

    master_df, work_experience_df = (
        create_hr_tables()
    )

    return (
        master_df,
        work_experience_df
    )


# ============================================================
# HR RECRUITMENT DATABASE SCHEMA
# ============================================================

HR_DATABASE_SCHEMA = """

============================================================
HR RECRUITMENT DATABASE
============================================================

This HR Question Answering system uses TWO SQLite-compatible
Pandas DataFrame tables.

TABLE 1:
master_df

TABLE 2:
work_experience_df


============================================================
TABLE 1: master_df
============================================================

PURPOSE:
Contains recruitment, requisition, candidate, and screening
information.

GRANULARITY:
One row represents one candidate application for one job
requisition.

IMPORTANT:
One requisition can have multiple candidate applications.

Therefore:

RequisitionNumber is NOT unique.

JobApplicationId identifies a candidate application.


------------------------------------------------------------
MASTER TABLE COLUMNS
------------------------------------------------------------

requisition_header_id
- Requisition header identifier.
- Data type: TEXT.

requisition_number
- Business requisition number.
- Data type: TEXT.

requisition_id
- System requisition identifier.
- Data type: TEXT.

requisition_title
- Job requisition title.
- Data type: TEXT.

requisition_state_name
- Current state of the requisition.
- Data type: TEXT.

requisition_phase_name
- Current phase of the requisition.
- Data type: TEXT.

requisition_applications
- Number of applications associated with the requisition.
- Data type: NUMBER.
- This value may be repeated for every candidate belonging
  to the same requisition.
- NEVER SUM this column across candidate rows.

requisition_jd_title
- Job description title.
- Data type: TEXT.

requisition_jd_about
- Job description overview.
- Data type: TEXT.

requisition_jd_responsibilities
- Job description responsibilities.
- Data type: TEXT.

requisition_creation_date
- Requisition creation date.
- Data type: TEXT.

candidate_line_id
- Candidate line identifier.
- Data type: TEXT.

candidate_job_application_id
- Candidate application identifier.
- Data type: TEXT.

candidate_person_id
- Candidate/person identifier.
- Data type: TEXT.

candidate_name
- Candidate name.
- Data type: TEXT.

candidate_requisition_id
- Requisition identifier associated with the candidate.
- Data type: TEXT.

candidate_requisition_number
- Requisition number associated with the candidate.
- Data type: TEXT.

candidate_public_state_name
- Current candidate application status.
- Data type: TEXT.

candidate_recruiter_id
- Recruiter identifier.
- Data type: TEXT.

candidate_phase_id
- Candidate phase identifier.
- Data type: TEXT.

candidate_state_id
- Candidate state identifier.
- Data type: TEXT.

candidate_email
- Candidate email.
- Data type: TEXT.

screening_header_id
- Screening header identifier.
- Data type: TEXT.

screening_candidate_line_id
- Screening candidate line identifier.
- Data type: TEXT.

screening_requisition_header_id
- Screening requisition header identifier.
- Data type: TEXT.

screening_current_role
- Candidate current or recent role.
- Data type: TEXT.

screening_education
- Candidate education.
- Data type: TEXT.

screening_certifications
- Candidate certifications.
- Data type: TEXT.

screening_ai_summary
- AI-generated screening summary.
- Data type: TEXT.

screening_ai_score
- AI-generated screening score.
- Data type: NUMBER/TEXT.

screening_person_id
- Screening person identifier.
- Data type: TEXT.

screening_person_number
- Screening person number.
- Data type: TEXT.

screening_recruiter
- Recruiter name.
- Data type: TEXT.

screening_work_email
- Recruiter/work email.
- Data type: TEXT.

screening_skills
- Candidate skills.
- Data type: TEXT.


============================================================
TABLE 2: work_experience_df
============================================================

PURPOSE:
Contains individual work-experience records.

GRANULARITY:
ONE ROW represents ONE work-experience record.

A single candidate can therefore have MULTIPLE rows.

COLUMNS:

line_id
screening_header_id
requisition_header_id
candidate_line_id
job_application_id
candidate_person_id
company_name
job_title
duration


============================================================
RELATIONSHIP
============================================================

The two tables are related through:

screening_header_id
requisition_header_id
candidate_line_id

Preferred JOIN:

m.screening_header_id = w.screening_header_id

AND

m.requisition_header_id = w.requisition_header_id

AND

m.candidate_line_id = w.candidate_line_id


============================================================
MASTER DATA QUESTIONS
============================================================

Use master_df for:

- requisition information
- requisition number
- requisition title
- requisition state
- requisition phase
- requisition applications
- candidate information
- candidate name
- candidate application
- candidate application status
- education
- certifications
- current role
- candidate recruiter
- candidate email
- AI score
- AI summary
- skills
- screening information
- job description


============================================================
WORK EXPERIENCE QUESTIONS
============================================================

Use work_experience_df for:

- previous companies
- previous employers
- work history
- previous jobs
- previous job titles
- experience duration
- employment history


============================================================
WHEN BOTH TABLES ARE REQUIRED
============================================================

Use BOTH tables when the question requires:

master_df information

AND

work_experience_df information.

JOIN using:

m.screening_header_id = w.screening_header_id

AND

m.requisition_header_id = w.requisition_header_id

AND

m.candidate_line_id = w.candidate_line_id


============================================================
SKILLS
============================================================

Skills questions MUST use:

master_df.screening_skills

Do not use certifications for skills questions.


============================================================
COUNTING RULES
============================================================

For unique candidate applications use:

COUNT(DISTINCT candidate_job_application_id)

Do not SUM requisition_applications.

For work experience records:

COUNT(*)


============================================================
SQL SAFETY
============================================================

Only these tables are allowed:

master_df
work_experience_df

Only SELECT statements are allowed.

Do not use:

INSERT
UPDATE
DELETE
DROP
ALTER
CREATE

Do not use:

SELECT *

Never invent columns.


============================================================
TEXT SEARCH
============================================================

Case-insensitive flexible search:

LOWER(column) LIKE LOWER('%value%')

Exact search:

LOWER(column) = LOWER('value')


============================================================
JOB TITLE QUESTIONS
============================================================

For a question about a job/requisition title, include:

requisition_number
requisition_title
requisition_state_name

when appropriate.

Example:

SELECT
    m.requisition_number,
    m.requisition_title,
    m.requisition_state_name
FROM master_df m
WHERE LOWER(m.requisition_title)
      = LOWER('Site Engineer')
LIMIT 50;


============================================================
REQUISITION STATE
============================================================

Use:

m.requisition_state_name

when the question asks about requisition state/status.


============================================================
REQUISITION PHASE
============================================================

Use:

m.requisition_phase_name


============================================================
CANDIDATE APPLICATION STATE
============================================================

Use:

m.candidate_public_state_name


============================================================
AI SCORE
============================================================

Use:

m.screening_ai_score


============================================================
WORK EXPERIENCE
============================================================

Use:

w.company_name
w.job_title
w.duration


============================================================
FINAL SQL RULE
============================================================

Return SQL ONLY.

Do not return:

- explanations
- markdown
- code fences
- JSON
- comments
- natural-language answers

"""


# ============================================================
# CLEAN SQL
# ============================================================

def clean_sql(
    text: str
):

    text = text.strip()

    if "```sql" in text:

        return (
            text
            .split("```sql")[1]
            .split("```")[0]
            .strip()
        )

    if "```" in text:

        return (
            text
            .split("```")[1]
            .split("```")[0]
            .strip()
        )

    return text.strip()


# ============================================================
# EXTRACT JSON
# ============================================================

def extract_json(
    text: str
) -> dict:

    text = text.strip()

    try:

        return json.loads(
            text
        )

    except Exception:

        pass

    match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL
    )

    if match:

        json_text = match.group()

        return json.loads(
            json_text
        )

    raise ValueError(
        "Could not parse JSON from evaluator response"
    )


# ============================================================
# INTENT ROUTER
# ============================================================

# ============================================================
# INTENT ROUTER
# ============================================================

def intent_router(
    state: QueryState
):

    print(
        "ENTER Intent Router"
    )

    question = str(
        state.get(
            "question",
            ""
        )
    ).strip()

    question_lower = question.lower()

    # ========================================================
    # DETERMINISTIC HR ROUTING
    # ========================================================
    #
    # Some HR questions contain a job title that may NOT
    # exactly match the database title.
    #
    # Example:
    #
    # "total how many candidates are in the oracle hcm"
    #
    # User title:
    #     oracle hcm
    #
    # Actual database title:
    #     Oracle HCM Functional Specialist
    #
    # The title resolver will handle this later.
    #
    # Therefore, do not let the intent LLM reject the request
    # simply because the exact title is not present in the
    # schema text.
    # ========================================================

    candidate_words = [
        "candidate",
        "candidates",
        "applicant",
        "applicants",
        "people applied",
        "person applied"
    ]

    candidate_count_words = [
        "how many",
        "how much",
        "total",
        "count",
        "number of",
        "candidate count",
        "total number"
    ]

    candidate_list_words = [
        "show candidates",
        "show me candidates",
        "give me candidates",
        "give me the candidates",
        "list candidates",
        "list the candidates",
        "who are the candidates",
        "all candidates",
        "candidates in",
        "candidates for",
        "candidates under",
        "candidates of"
    ]

    hr_context_words = [
        "requisition",
        "job",
        "job title",
        "position",
        "role",
        "candidate",
        "candidates",
        "applicant",
        "applicants",
        "screening",
        "interview",
        "recruitment",
        "recruiter",
        "hiring",
        "skills",
        "education",
        "experience",
        "certification",
        "ai score",
        "application"
    ]

    # ========================================================
    # CHECK CANDIDATE QUESTION
    # ========================================================

    has_candidate_word = any(
        word in question_lower
        for word in candidate_words
    )

    has_candidate_count_word = any(
        word in question_lower
        for word in candidate_count_words
    )

    has_candidate_list_word = any(
        phrase in question_lower
        for phrase in candidate_list_words
    )

    has_hr_context = any(
        word in question_lower
        for word in hr_context_words
    )

    # ========================================================
    # CANDIDATE COUNT
    # ========================================================
    #
    # Examples:
    #
    # total how many candidates are in the oracle hcm
    # how many candidates are in requisition 44
    # what is the candidate count for Site Engineer
    # ========================================================

    if (
        has_candidate_word
        and
        has_candidate_count_word
        and
        has_hr_context
    ):

        reason = (
            "The question is a candidate-count request "
            "that can be answered using HR recruitment data."
        )

        print(
            "Deterministic HR Route: HYBRID_ROUTE"
        )

        print(
            "Reason:",
            reason
        )

        print(
            "EXIT Intent Router"
        )

        return {
            "route":
                "HYBRID_ROUTE",
            "route_reason":
                reason
        }

    # ========================================================
    # CANDIDATE LIST
    # ========================================================
    #
    # Examples:
    #
    # give me the candidates in oracle hcm
    # show candidates for requisition 44
    # list the candidates under Site Engineer
    # ========================================================

    if (
        has_candidate_list_word
        and
        has_hr_context
    ):

        reason = (
            "The question is a candidate information request "
            "that can be answered using HR recruitment data."
        )

        print(
            "Deterministic HR Route: HYBRID_ROUTE"
        )

        print(
            "Reason:",
            reason
        )

        print(
            "EXIT Intent Router"
        )

        return {
            "route":
                "HYBRID_ROUTE",
            "route_reason":
                reason
        }

    # ========================================================
    # GENERAL HR DATA QUESTIONS
    # ========================================================
    #
    # This protects questions such as:
    #
    # what are Jithu's skills?
    # what is the status of Site Engineer?
    # who is the recruiter?
    # what is the education of Jithu?
    # ========================================================

    strong_hr_question_patterns = [
        r"\bwhat\s+are\b.*\bskills\b",
        r"\bwhat\s+is\b.*\bskill\b",
        r"\bwhat\s+is\b.*\beducation\b",
        r"\bwhat\s+is\b.*\bexperience\b",
        r"\bwhat\s+is\b.*\bstatus\b",
        r"\bwhat\s+is\b.*\bstate\b",
        r"\bwhat\s+is\b.*\bphase\b",
        r"\bwhat\s+is\b.*\brecruiter\b",
        r"\bwho\s+is\b.*\brecruiter\b",
        r"\bai\s+score\b",
        r"\bscreening\s+score\b",
        r"\bapplication\s+status\b",
        r"\brequisition\s+\d+\b",
        r"\bjob\s+title\b",
        r"\brequisition\s+title\b"
    ]

    for pattern in strong_hr_question_patterns:

        if re.search(
            pattern,
            question_lower
        ):

            reason = (
                "The question matches an HR recruitment "
                "data query."
            )

            print(
                "Deterministic HR Route: HYBRID_ROUTE"
            )

            print(
                "Reason:",
                reason
            )

            print(
                "EXIT Intent Router"
            )

            return {
                "route":
                    "HYBRID_ROUTE",
                "route_reason":
                    reason
            }

    # ========================================================
    # LLM ROUTING
    # ========================================================

    prompt = f"""
You are an intelligent routing agent for an HR Recruitment
Natural Language to SQL system.

Your task is to determine whether the user's question can
be answered using the available HR recruitment data.

IMPORTANT:

A user may provide a shortened, abbreviated, misspelled,
or informal job title.

Examples:

"Oracle HCM"

may refer to:

"Oracle HCM Functional Specialist"

"Site Enginner"

may refer to:

"Site Engineer"

Do NOT classify a question as UNKNOWN_ROUTE merely because
the exact user-provided job title does not literally appear
in the schema.

The job title will be resolved by a separate title resolver
after routing.

AVAILABLE DATABASE SCHEMA:

{HR_DATABASE_SCHEMA}

============================================================
ROUTING RULES
============================================================

1. HYBRID_ROUTE

Choose HYBRID_ROUTE if the user's question can be answered,
calculated, filtered, sorted, compared, or derived using
the available HR recruitment data.

This includes questions about:

- requisitions
- job titles
- candidates
- candidate counts
- candidate names
- applicants
- screening
- AI scores
- skills
- education
- certifications
- recruiters
- candidate status
- requisition status
- requisition phase
- work experience

============================================================
CANDIDATE COUNT
============================================================

These MUST be HYBRID_ROUTE:

"How many candidates are there?"

"How many candidates are in requisition 42?"

"How many candidates are in Oracle HCM?"

"Total how many candidates are in the Oracle HCM?"

"What is the candidate count for Site Engineer?"

"How many applicants are under Oracle HCM?"

The job title does NOT need to exactly match the database
title.

The title resolver may resolve:

"Oracle HCM"

to:

"Oracle HCM Functional Specialist"

============================================================
CANDIDATE LIST
============================================================

These MUST be HYBRID_ROUTE:

"Show candidates for requisition 42."

"Give me all candidates in Oracle HCM."

"Who are the candidates for Site Engineer?"

"List the candidates under Oracle HCM."

============================================================
JOB TITLE
============================================================

Questions containing a job title are valid HR questions.

Examples:

"What is the status of Oracle HCM?"

"How many candidates are in Oracle HCM?"

"Show candidates in Oracle HCM."

"What is the state of Site Engineer?"

Do NOT require the exact title to appear in the schema.

============================================================
UNKNOWN_ROUTE
============================================================

Choose UNKNOWN_ROUTE only when the question clearly cannot
be answered using HR recruitment data.

Examples:

"What is the weather today?"

"What is the company's annual revenue?"

"What is the current stock price?"

"Tell me a joke."

"Who won the cricket match?"

Do NOT classify an HR recruitment question as UNKNOWN_ROUTE
just because a job title is abbreviated or not an exact
database value.

============================================================
BUSINESS TERMINOLOGY
============================================================

job opening -> requisition

position -> requisition/job

applicant -> candidate

candidate -> candidate_name

application -> candidate application

screening score -> screening_ai_score

AI score -> screening_ai_score

application status -> candidate_public_state_name

job title -> requisition_title

current job -> screening_current_role

education -> screening_education

experience -> work experience

skills -> screening_skills

certifications -> screening_certifications

AI summary -> screening_ai_summary

requisition status -> requisition_state_name

requisition phase -> requisition_phase_name

============================================================
USER QUESTION
============================================================

{question}

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

HYBRID example:

{{
    "route": "HYBRID_ROUTE",
    "reason": "The question can be answered using available HR recruitment data."
}}

UNKNOWN example:

{{
    "route": "UNKNOWN_ROUTE",
    "reason": "The question cannot be answered using available HR recruitment data."
}}

Do not return markdown.
Do not return code fences.
Do not return text outside the JSON.
"""

    # ========================================================
    # CALL LLM
    # ========================================================

    try:

        response = llm_intent.invoke(
            prompt
        )

        print(
            "RAW INTENT RESPONSE:"
        )

        print(
            response.content
        )

        data = extract_json(
            response.content
        )

        route = data.get(
            "route",
            "UNKNOWN_ROUTE"
        )

        reason = data.get(
            "reason",
            "No routing reason provided."
        )

        # ====================================================
        # VALIDATE ROUTE
        # ====================================================

        if route not in [
            "HYBRID_ROUTE",
            "UNKNOWN_ROUTE"
        ]:

            route = "UNKNOWN_ROUTE"

        print(
            "Route:",
            route
        )

        print(
            "Reason:",
            reason
        )

        print(
            "EXIT Intent Router"
        )

        return {
            "route":
                route,
            "route_reason":
                reason
        }

    except Exception as e:

        import traceback

        traceback.print_exc()

        return {
            "route":
                "UNKNOWN_ROUTE",

            "route_reason":
                f"Intent routing failed: {str(e)}"
        }

# ============================================================
# GENERATE SQL
# ============================================================

def generate_query_hybrid(
    state: QueryState
):

    print(
        "ENTER generate_query_hybrid"
    )

    template = """

You are an expert SQLite SQL Generator for an HR Recruitment
Question Answering system.

Your job is to convert the user's natural-language HR question
into ONE valid SQLite SQL query.

The SQL will be executed against Pandas DataFrames using pandasql.

============================================================
USER QUESTION
============================================================

{question}

============================================================
HR DATABASE SCHEMA
============================================================

{hr_database_schema}

============================================================
AVAILABLE TABLES
============================================================

Only these tables are available:

master_df
work_experience_df

Never invent another table.

============================================================
IMPORTANT BUSINESS RULES
============================================================

Determine first whether the question is about:

1. Requisition
2. Candidate
3. Work experience
4. Screening
5. Both candidate and work experience

============================================================
REQUISITION QUESTIONS
============================================================

For questions about:

- requisition
- job
- job title
- requisition title
- requisition state
- requisition status
- requisition phase

use master_df.

Use:

m.requisition_number
m.requisition_title
m.requisition_state_name
m.requisition_phase_name

============================================================
REQUISITION COUNT / REQUISITION NUMBER LIST
============================================================

This rule has PRIORITY over the normal job-title rule.

If the user asks for:

- total requisitions
- how many requisitions
- number of requisitions
- count of requisitions
- how many reqs
- total reqs

AND the user also asks to:

- give the requisition numbers
- list the requisition numbers
- show the requisition numbers
- give the req numbers
- show the req numbers

then return BOTH:

1. The total number of unique requisitions.
2. The list of unique requisition numbers.

Use:

COUNT(DISTINCT m.requisition_number)

and:

GROUP_CONCAT(DISTINCT m.requisition_number)

Example:

User:

"How many requisitions of Site Engineer and give the requisition numbers?"

Correct SQL:

SELECT
    COUNT(DISTINCT m.requisition_number) AS total_requisitions,
    GROUP_CONCAT(DISTINCT m.requisition_number) AS requisition_numbers
FROM master_df m
WHERE LOWER(m.requisition_title) =
      LOWER('Site Engineer');

IMPORTANT:

Do NOT select only one requisition number.

Do NOT add:

m.requisition_number = '102'

Do NOT choose the first matching requisition.

If multiple requisitions have the same exact job title, include
ALL of their requisition numbers.

Example data:

Requisition 21  -> Site Engineer
Requisition 102 -> Site Engineer
Requisition 94  -> Senior Site Engineer
Requisition 44  -> Site Engineer (Trainee)

For:

"How many requisitions of Site Engineer and give the
requisition numbers?"

the correct result is:

total_requisitions = 2
requisition_numbers = 21,102

Do NOT include:

94
44

because those are different job titles.


============================================================
REQUISITION COUNT ONLY
============================================================

If the user asks only:

- how many requisitions
- total requisitions
- number of requisitions
- count of requisitions

and does NOT ask for requisition numbers, return only the
total count.

Example:

User:

"How many requisitions are there for Site Engineer?"

Correct SQL:

SELECT
    COUNT(DISTINCT m.requisition_number) AS total_requisitions
FROM master_df m
WHERE LOWER(m.requisition_title) =
      LOWER('Site Engineer');

Do NOT restrict the query to one requisition unless the user
explicitly provides a requisition number.


============================================================
REQUISITION NUMBER LIST ONLY
============================================================

If the user asks only for the requisition numbers for a job
title, return the unique requisition numbers.

Example:

User:

"Give me the requisition numbers for Site Engineer."

Correct SQL:

SELECT DISTINCT
    m.requisition_number
FROM master_df m
WHERE LOWER(m.requisition_title) =
      LOWER('Site Engineer')
ORDER BY m.requisition_number;

============================================================
IMPORTANT JOB TITLE RULE
============================================================

IMPORTANT:

The REQUISITION COUNT / REQUISITION NUMBER LIST rules above
take priority over this general job-title rule.

For aggregate requisition questions, DO NOT select a single
requisition number.

For example:

User:

"What is the state of the Site Engineer?"

Do NOT generate only:

SELECT
    m.requisition_state_name
FROM master_df m
WHERE LOWER(m.requisition_title) =
      LOWER('Site Engineer');

Instead prefer:

SELECT
    m.requisition_number,
    m.requisition_title,
    m.requisition_state_name
FROM master_df m
WHERE LOWER(m.requisition_title) =
      LOWER('Site Engineer')
LIMIT 50;

This is important because multiple requisitions can have
the same job title.

For example:

Requisition 21 -> Site Engineer
Requisition 102 -> Site Engineer

The answer must therefore preserve which state belongs
to which requisition.

IMPORTANT EXCEPTION:

If the user asks for an aggregate requisition query such as:

- How many requisitions of Site Engineer?
- What is the total number of requisitions for Site Engineer?
- Give me the requisition numbers for Site Engineer.
- How many requisitions of Site Engineer and give the
  requisition numbers?

then DO NOT apply the single-requisition logic above.

Instead:

- COUNT DISTINCT requisition numbers for count questions.
- Return ALL matching requisition numbers for list questions.
- If both are requested, return BOTH the total count and
  all matching requisition numbers.
- Never choose only the first matching requisition.
- Never add a condition such as:

  m.requisition_number = '102'

  unless the user explicitly provided requisition 102.

============================================================
REQUISITION NUMBER
============================================================

If the user provides a requisition number, use:

m.requisition_number

Example:

SELECT
    m.requisition_number,
    m.requisition_title,
    m.requisition_state_name
FROM master_df m
WHERE LOWER(m.requisition_number) =
      LOWER('24');

============================================================
CANDIDATE LIST / CANDIDATE NAMES
============================================================

This rule is VERY IMPORTANT.

If the user asks for:

- candidates
- all candidates
- candidate names
- list of candidates
- candidates in a job
- candidates in a job title
- candidates under a job title
- candidates for a requisition
- all candidates for a requisition
- who are the candidates
- give me the candidates

and the user does NOT explicitly ask for additional
candidate information such as:

- email
- skills
- education
- certifications
- current role
- AI score
- AI summary
- application status
- work experience

then return ONLY the candidate names.

Use:

SELECT DISTINCT
    m.candidate_name
FROM master_df m

Do NOT select:

m.candidate_email
m.screening_skills
m.screening_education
m.screening_certifications
m.screening_current_role
m.screening_ai_score
m.candidate_public_state_name

Do NOT join work_experience_df unless the user explicitly
asks for work experience.

Example:

User:

"Can you give me the candidates in Oracle HCM Functional Specialist?"

Correct SQL:

SELECT DISTINCT
    m.candidate_name
FROM master_df m
WHERE m.requisition_number = '130'
  AND LOWER(m.requisition_title) =
      LOWER('Oracle HCM Functional Specialist')
LIMIT 50;

Incorrect SQL:

SELECT
    m.candidate_name,
    m.candidate_email,
    m.screening_skills
FROM master_df m
WHERE ...

============================================================
CANDIDATE QUESTIONS
============================================================

Use master_df for:

candidate name
candidate application
candidate application status
education
certifications
current role
AI score
AI summary
skills

============================================================
CANDIDATE NAME
============================================================

Use:

m.candidate_name

For exact full-name matching:

LOWER(m.candidate_name) =
LOWER('Full Name')

For partial matching:

LOWER(m.candidate_name) LIKE
LOWER('%name%')

Do not silently choose one candidate when multiple
candidate names can match.

============================================================
SKILLS
============================================================

Skills MUST use:

m.screening_skills

============================================================
AI SCORE
============================================================

AI score MUST use:

m.screening_ai_score

Highest score:

ORDER BY m.screening_ai_score DESC

Lowest score:

ORDER BY m.screening_ai_score ASC

============================================================
APPLICATION STATUS
============================================================

Use:

m.candidate_public_state_name

============================================================
REQUISITION STATUS
============================================================

Use:

m.requisition_state_name

============================================================
REQUISITION PHASE
============================================================

Use:

m.requisition_phase_name

============================================================
WORK EXPERIENCE
============================================================

Use:

work_experience_df

Columns:

w.company_name
w.job_title
w.duration

============================================================
WORK EXPERIENCE DETAILS / WORK EXPERIENCE LIST
============================================================

IMPORTANT:

When the user asks to:

- give the work experience
- show the work experience
- list the work experience
- provide the work experience
- tell me the work experience
- what is the work experience of the candidate
- what work experience does the candidate have
- show me the candidate's previous work experience
- give the candidate's employment history
- show the candidate's career history

the user is asking for the WORK EXPERIENCE DETAILS.

This is NOT a total-duration calculation question.

Therefore:

DO NOT calculate total years.

DO NOT use:

SUM(...)

DO NOT divide by 12.0.

DO NOT return:

total_years_experience

Instead, return one row for each work-experience record.

============================================================
WORK EXPERIENCE DETAILS COLUMNS
============================================================

For a work-experience details question, return:

w.job_title

w.company_name

w.duration

Use:

SELECT
    w.job_title,
    w.company_name,
    w.duration

FROM master_df m

JOIN work_experience_df w

    ON m.screening_header_id =
       w.screening_header_id

    AND m.requisition_header_id =
        w.requisition_header_id

    AND m.candidate_line_id =
        w.candidate_line_id

Then identify the candidate using:

LOWER(TRIM(m.candidate_name)) =
LOWER(TRIM('Candidate Name'))

============================================================
WORK EXPERIENCE DETAILS EXAMPLE
============================================================

User:

Can you give the work experience of Akhil Kotha?

Correct SQL:

SELECT
    w.job_title,
    w.company_name,
    w.duration
FROM master_df m
JOIN work_experience_df w
    ON m.screening_header_id = w.screening_header_id
    AND m.requisition_header_id = w.requisition_header_id
    AND m.candidate_line_id = w.candidate_line_id
WHERE LOWER(TRIM(m.candidate_name)) =
      LOWER(TRIM('Akhil Kotha'));

============================================================
IMPORTANT PRIORITY RULE
============================================================

The WORK EXPERIENCE DETAILS / WORK EXPERIENCE LIST rule
has PRIORITY over the WORK EXPERIENCE DURATION rules below.

If the user asks to:

"give"
"show"
"list"
"provide"

the work experience, return the individual work-experience
records.

Do NOT calculate total years unless the user explicitly asks
for total duration or total years.

Examples:

"Give the work experience of Akhil Kotha"

=> WORK EXPERIENCE DETAILS

"Show Akhil Kotha's work experience"

=> WORK EXPERIENCE DETAILS

"List Akhil Kotha's previous jobs"

=> WORK EXPERIENCE DETAILS

"Provide Akhil Kotha's employment history"

=> WORK EXPERIENCE DETAILS

"How many years of work experience does Akhil Kotha have?"

=> TOTAL WORK EXPERIENCE

"What is Akhil Kotha's total work experience?"

=> TOTAL WORK EXPERIENCE

"Total how many years of work experience did Akhil Kotha have?"

=> TOTAL WORK EXPERIENCE

"How many years did Akhil Kotha work as Oracle HCM Consultant?"

=> ROLE-SPECIFIC WORK EXPERIENCE DURATION

============================================================
DO NOT MIX DETAILS AND TOTAL DURATION
============================================================

For:

"Can you give the work experience of Akhil Kotha?"

DO NOT generate:

SELECT
    ROUND(
        SUM(...)
        / 12.0,
        2
    ) AS total_years_experience

Instead generate:

SELECT
    w.job_title,
    w.company_name,
    w.duration

FROM master_df m

JOIN work_experience_df w
    ON m.screening_header_id = w.screening_header_id
    AND m.requisition_header_id = w.requisition_header_id
    AND m.candidate_line_id = w.candidate_line_id

WHERE LOWER(TRIM(m.candidate_name)) =
      LOWER(TRIM('Akhil Kotha'));

============================================================
WORK EXPERIENCE DETAILS OUTPUT
============================================================

When the SQL result contains:

job_title
company_name
duration

the result summarizer should format the information as:

**Work Experience:**
1. **<job_title>**
   <company_name>
   <duration>

2. **<job_title>**
   <company_name>
   <duration>

3. **<job_title>**
   <company_name>
   <duration>

Preserve the values returned by SQL.

Do not calculate total years.

Do not replace the individual records with a total-duration
statement.

============================================================
END OF WORK EXPERIENCE DETAILS RULE
============================================================

============================================================
WORK EXPERIENCE DURATION
========================

IMPORTANT:

The column:

w.duration

contains a date range in text format.

Examples:

Jun 2018 – Jan 2020
Jan 2020 – Dec 2024
Jan 2025 – Present

The duration is NOT stored as a numeric number of years.

Therefore:

DO NOT use:

CAST(w.duration AS INTEGER)

DO NOT extract the first word and CAST it to INTEGER.

DO NOT directly use SQLite strftime() on values such as:

Jun 2018
Jan 2020
Jun
Jan

These are text month/year values and are not complete SQLite
date values.

============================================================
SUPPORTED DURATION FORMATS
==========================

The w.duration column may contain either:

1. Completed experience:

<start_month> <start_year> – <end_month> <end_year>

Example:

Jun 2018 – Jan 2020

2. Current experience:

<start_month> <start_year> – Present

Example:

Jan 2025 – Present

The SQL MUST support both formats.

============================================================
HOW TO PARSE START DATE
=======================

For:

Jun 2018 – Jan 2020

the format is:

<start_month> <start_year> – <end_month> <end_year>

Extract the start month using:

LOWER(SUBSTR(TRIM(w.duration), 1, 3))

Extract the start year using:

CAST(SUBSTR(TRIM(w.duration), 5, 4) AS INTEGER)

IMPORTANT:

Month extraction MUST use LOWER().

The source data may contain:

Jan
JAN
jan

Feb
FEB
feb

Jun
JUN
jun

Therefore, month names MUST ALWAYS be normalized using:

LOWER(...)

before comparing them with month names.

============================================================
START MONTH TO MONTH NUMBER
===========================

Use:

CASE LOWER(SUBSTR(TRIM(w.duration), 1, 3))
WHEN 'jan' THEN 1
WHEN 'feb' THEN 2
WHEN 'mar' THEN 3
WHEN 'apr' THEN 4
WHEN 'may' THEN 5
WHEN 'jun' THEN 6
WHEN 'jul' THEN 7
WHEN 'aug' THEN 8
WHEN 'sep' THEN 9
WHEN 'oct' THEN 10
WHEN 'nov' THEN 11
WHEN 'dec' THEN 12
END

DO NOT generate:

CASE SUBSTR(TRIM(w.duration), 1, 3)
WHEN 'jan' THEN 1
WHEN 'jun' THEN 6
END

The SQL MUST use:

CASE LOWER(SUBSTR(...))

============================================================
HOW TO PARSE END DATE
=====================

For a completed duration:

Jun 2018 – Jan 2020

extract the end month using:

LOWER(SUBSTR(TRIM(w.duration), -8, 3))

extract the end year using:

CAST(SUBSTR(TRIM(w.duration), -4) AS INTEGER)

============================================================
END MONTH TO MONTH NUMBER
=========================

Use:

CASE LOWER(SUBSTR(TRIM(w.duration), -8, 3))
WHEN 'jan' THEN 1
WHEN 'feb' THEN 2
WHEN 'mar' THEN 3
WHEN 'apr' THEN 4
WHEN 'may' THEN 5
WHEN 'jun' THEN 6
WHEN 'jul' THEN 7
WHEN 'aug' THEN 8
WHEN 'sep' THEN 9
WHEN 'oct' THEN 10
WHEN 'nov' THEN 11
WHEN 'dec' THEN 12
END

DO NOT generate:

CASE SUBSTR(TRIM(w.duration), -8, 3)
WHEN 'jan' THEN 1
WHEN 'jun' THEN 6
END

The SQL MUST use:

CASE LOWER(SUBSTR(...))

============================================================
HANDLING "PRESENT"
==================

IMPORTANT:

The end of w.duration may be:

Present

Example:

Jan 2025 – Present

"Present" means the candidate is still working in that role.

DO NOT treat "Present" as a missing duration.

DO NOT allow a Present row to become NULL.

When the duration ends with:

Present

use the current month and current year as the end date.

For the current month use:

CAST(STRFTIME('%m', 'now') AS INTEGER)

For the current year use:

CAST(STRFTIME('%Y', 'now') AS INTEGER)

IMPORTANT:

strftime() may be used with:

'now'

because 'now' is a valid SQLite date/time value.

However, DO NOT use strftime() directly on:

Jun 2018
Jan 2020

because these are incomplete SQLite dates.

============================================================
DETERMINE WHETHER THE ROW IS "PRESENT"
======================================

Check the duration using:

LOWER(TRIM(w.duration)) LIKE '%present'

or an equivalent case-insensitive condition.

For example:

CASE
WHEN LOWER(TRIM(w.duration)) LIKE '%present'
THEN ...
ELSE ...
END

The Present condition MUST use the current month/year.

============================================================
CALCULATE COMPLETED EXPERIENCE IN MONTHS
========================================

For a completed duration:

Jun 2018 – Jan 2020

calculate:

(
end_year - start_year
) * 12
+
(
end_month_number - start_month_number
)

Example:

Start month = 6
Start year = 2018

End month = 1
End year = 2020

Therefore:

(2020 - 2018) * 12 + (1 - 6)

= 19 months

============================================================
CALCULATE PRESENT EXPERIENCE IN MONTHS
======================================

For:

Jan 2025 – Present

calculate:

(
current_year - start_year
) * 12
+
(
current_month - start_month_number
)

Example:

If the current date is September 2026:

Start month = 1
Start year = 2025

Current month = 9
Current year = 2026

Therefore:

(2026 - 2025) * 12 + (9 - 1)

= 20 months

============================================================
COMPLETED AND PRESENT ROWS
==========================

The SQL MUST support BOTH:

1. Completed experience:

Jun 2018 – Jan 2020

2. Current experience:

Jan 2025 – Present

For completed rows:

* extract end month from w.duration
* extract end year from w.duration

For Present rows:

* use current month
* use current year

The SQL MUST NOT return NULL for a valid Present row.

============================================================
TOTAL WORK EXPERIENCE
=====================

When the user asks questions such as:

* total work experience
* total years of experience
* how many years of work experience
* total how many years
* overall work experience
* how many years has the candidate worked
* total experience
* overall years of experience

the SQL MUST:

1. Find all matching work-experience rows.
2. Calculate the duration of each row in MONTHS.
3. Support both completed and Present rows.
4. SUM all matching months.
5. Convert the total months to years.

The final calculation MUST be:

ROUND(
SUM(total_months) / 12.0,
2
)

IMPORTANT:

SUM(total_months) is in MONTHS.

Therefore, DO NOT return:

ROUND(
SUM(total_months),
2
)

because that would return months while labeling the result
as years.

The final result MUST be in YEARS.

============================================================
MANDATORY TOTAL EXPERIENCE EXAMPLE
==================================

Given:

Jan 2025 – Present

Jan 2020 – Dec 2024

Jun 2018 – Jan 2020

If the current month/year is September 2026:

Jan 2025 – Present
= 20 months

Jan 2020 – Dec 2024
= 59 months

Jun 2018 – Jan 2020
= 19 months

Total:

20 + 59 + 19

= 98 months

Years:

98 / 12.0

= 8.1667...

Rounded:

8.17 years

Therefore:

The correct total work experience is 8.17 years.

============================================================
MULTIPLE WORK EXPERIENCE ROWS
=============================

If multiple work-experience rows match the candidate:

1. Calculate the duration of each row in MONTHS.
2. SUM all matching months.
3. Convert the total months to years.

Do NOT:

* convert each row to rounded years first
* SUM rounded years
* divide an already rounded value

Correct:

SUM(months) / 12.0

Incorrect:

SUM(rounded_year_values)

============================================================
WORK EXPERIENCE JOB TITLE
=========================

When the user asks about experience worked as a specific
job title, the requested role refers to:

w.job_title

NOT:

m.requisition_title

For example:

User:

How many years did Akhil Kotha work as Oracle HCM Consultant?

The SQL MUST use:

LOWER(TRIM(w.job_title)) =
LOWER(TRIM('Oracle HCM Consultant'))

The candidate MUST be matched using:

LOWER(TRIM(m.candidate_name)) =
LOWER(TRIM('Akhil Kotha'))

IMPORTANT:

For work-experience questions:

w.job_title = previous/current job role

m.requisition_title = recruitment requisition title

Do NOT use m.requisition_title to identify the candidate's
previous work-experience role.

============================================================
WORK EXPERIENCE JOB TITLE FILTER
================================

When the user asks for experience in one specific work-
experience role, prefer filtering w.job_title directly
in the WHERE clause.

Use:

WHERE LOWER(TRIM(m.candidate_name)) =
LOWER(TRIM('Candidate Name'))

AND LOWER(TRIM(w.job_title)) =
LOWER(TRIM('Requested Job Title'))

Example:

WHERE LOWER(TRIM(m.candidate_name)) =
LOWER(TRIM('Akhil Kotha'))

AND LOWER(TRIM(w.job_title)) =
LOWER(TRIM('Oracle HCM Consultant'))

Do NOT use:

m.requisition_title

for this filter.

Do NOT put the role condition inside:

SUM(CASE WHEN ... THEN ... ELSE 0 END)

when the user asks about one specific role.

============================================================
WORK EXPERIENCE COMPANY FILTER
==============================

If the user explicitly asks about a company, use:

w.company_name

For example:

How many years did Akhil Kotha work at Nalsoft Middle East?

Use:

LOWER(TRIM(w.company_name)) =
LOWER(TRIM('Nalsoft Middle East'))

If the user asks for total work experience across all
companies, DO NOT add a company filter unless the user
explicitly requested one.

============================================================
WORK EXPERIENCE CANDIDATE MATCHING
==================================

Join:

master_df m
JOIN work_experience_df w

using:

m.screening_header_id =
w.screening_header_id

AND

m.requisition_header_id =
w.requisition_header_id

AND

m.candidate_line_id =
w.candidate_line_id

Then identify the candidate using:

LOWER(TRIM(m.candidate_name)) =
LOWER(TRIM('Candidate Name'))

============================================================
DO NOT USE STRFTIME DIRECTLY ON TEXT DATES
==========================================

DO NOT use:

strftime('%Y', w.duration)

DO NOT use:

strftime('%m', w.duration)

for values such as:

Jun 2018
Jan 2020

These are incomplete SQLite dates.

strftime() is allowed only with:

'now'

when calculating the current month/year for Present rows.

============================================================
MANDATORY VALIDATION EXAMPLE
============================

Given:

Candidate:

Akhil Kotha

Job Title:

Oracle HCM Consultant

Duration:

Jun 2018 – Jan 2020

The SQL MUST calculate:

Start month = 6
Start year  = 2018

End month   = 1
End year    = 2020

Elapsed months:

(2020 - 2018) * 12 + (1 - 6)

= 19 months

Years:

19 / 12.0

= 1.5833...

Rounded:

1.58 years

============================================================
MANDATORY PRESENT VALIDATION EXAMPLE
====================================

Given:

Duration:

Jan 2025 – Present

If current month/year is September 2026:

Start month = 1
Start year  = 2025

Current month = 9
Current year  = 2026

Elapsed months:

(2026 - 2025) * 12 + (9 - 1)

= 20 months

Years:

20 / 12.0

= 1.6667...

Rounded:

1.67 years

The SQL MUST include this Present row when calculating
total work experience.

============================================================
MANDATORY MONTH PARSING VALIDATION
==================================

For:

Jun 2018 – Jan 2020

the SQL MUST interpret:

LOWER(SUBSTR(TRIM(w.duration), 1, 3))

as:

jun

and:

LOWER(SUBSTR(TRIM(w.duration), -8, 3))

as:

jan

Therefore:

jun = 6
jan = 1

Then:

(2020 - 2018) * 12 + (1 - 6)

= 19 months

============================================================
MANDATORY PRESENT VALIDATION
============================

For:

Jan 2025 – Present

the SQL MUST NOT attempt:

CAST(SUBSTR(TRIM(w.duration), -4) AS INTEGER)

because the last four characters are:

sent

or the end portion of Present, not a year.

Instead, when the end is Present, the SQL MUST use:

CAST(STRFTIME('%m', 'now') AS INTEGER)

and:

CAST(STRFTIME('%Y', 'now') AS INTEGER)

============================================================
MANDATORY SQL STRUCTURE FOR TOTAL EXPERIENCE
============================================

For a question such as:

Total how many years of work experience did Akhil Kotha have?

the SQL should conceptually follow this structure:

SELECT
ROUND(
SUM(
CASE
WHEN LOWER(TRIM(w.duration)) LIKE '%present'
THEN
(
CAST(STRFTIME('%Y', 'now') AS INTEGER)
-
CAST(SUBSTR(TRIM(w.duration), 5, 4) AS INTEGER)
) * 12
+
(
CAST(STRFTIME('%m', 'now') AS INTEGER)
-
CASE LOWER(SUBSTR(TRIM(w.duration), 1, 3))
WHEN 'jan' THEN 1
WHEN 'feb' THEN 2
WHEN 'mar' THEN 3
WHEN 'apr' THEN 4
WHEN 'may' THEN 5
WHEN 'jun' THEN 6
WHEN 'jul' THEN 7
WHEN 'aug' THEN 8
WHEN 'sep' THEN 9
WHEN 'oct' THEN 10
WHEN 'nov' THEN 11
WHEN 'dec' THEN 12
END
)

```
            ELSE
                (
                    CAST(SUBSTR(TRIM(w.duration), -4) AS INTEGER)
                    -
                    CAST(SUBSTR(TRIM(w.duration), 5, 4) AS INTEGER)
                ) * 12
                +
                (
                    CASE LOWER(SUBSTR(TRIM(w.duration), -8, 3))
                        WHEN 'jan' THEN 1
                        WHEN 'feb' THEN 2
                        WHEN 'mar' THEN 3
                        WHEN 'apr' THEN 4
                        WHEN 'may' THEN 5
                        WHEN 'jun' THEN 6
                        WHEN 'jul' THEN 7
                        WHEN 'aug' THEN 8
                        WHEN 'sep' THEN 9
                        WHEN 'oct' THEN 10
                        WHEN 'nov' THEN 11
                        WHEN 'dec' THEN 12
                    END
                    -
                    CASE LOWER(SUBSTR(TRIM(w.duration), 1, 3))
                        WHEN 'jan' THEN 1
                        WHEN 'feb' THEN 2
                        WHEN 'mar' THEN 3
                        WHEN 'apr' THEN 4
                        WHEN 'may' THEN 5
                        WHEN 'jun' THEN 6
                        WHEN 'jul' THEN 7
                        WHEN 'aug' THEN 8
                        WHEN 'sep' THEN 9
                        WHEN 'oct' THEN 10
                        WHEN 'nov' THEN 11
                        WHEN 'dec' THEN 12
                    END
                )
        END
    ) / 12.0,
    2
) AS total_years_experience
```

FROM master_df m

JOIN work_experience_df w
ON m.screening_header_id = w.screening_header_id
AND m.requisition_header_id = w.requisition_header_id
AND m.candidate_line_id = w.candidate_line_id

WHERE LOWER(TRIM(m.candidate_name)) =
LOWER(TRIM('Akhil Kotha'))

============================================================
MANDATORY SQL STRUCTURE FOR ROLE-SPECIFIC EXPERIENCE
====================================================

For a question such as:

How many years did Akhil Kotha work as Oracle HCM Consultant?

the SQL should:

1. Match the candidate.
2. Match w.job_title.
3. Calculate each matching duration in months.
4. Support Present if applicable.
5. SUM the months.
6. Divide by 12.0.
7. ROUND to 2 decimals.

Use:

WHERE LOWER(TRIM(m.candidate_name)) =
LOWER(TRIM('Akhil Kotha'))

AND LOWER(TRIM(w.job_title)) =
LOWER(TRIM('Oracle HCM Consultant'))

============================================================
INCORRECT SQL PATTERNS
======================

INCORRECT:

CASE SUBSTR(TRIM(w.duration), 1, 3)
WHEN 'jan' THEN 1
WHEN 'feb' THEN 2
WHEN 'jun' THEN 6
END

CORRECT:

CASE LOWER(SUBSTR(TRIM(w.duration), 1, 3))
WHEN 'jan' THEN 1
WHEN 'feb' THEN 2
WHEN 'jun' THEN 6
END

---

INCORRECT:

CASE SUBSTR(TRIM(w.duration), -8, 3)
WHEN 'jan' THEN 1
WHEN 'feb' THEN 2
WHEN 'jun' THEN 6
END

CORRECT:

CASE LOWER(SUBSTR(TRIM(w.duration), -8, 3))
WHEN 'jan' THEN 1
WHEN 'feb' THEN 2
WHEN 'jun' THEN 6
END

---

INCORRECT:

LOWER(m.requisition_title) =
LOWER(TRIM('Oracle HCM Consultant'))

CORRECT:

LOWER(TRIM(w.job_title)) =
LOWER(TRIM('Oracle HCM Consultant'))

---

INCORRECT:

CAST(w.duration AS INTEGER)

CORRECT:

Explicitly parse start month, start year, end month,
and end year from w.duration.

---

INCORRECT:

CAST(SUBSTR(TRIM(w.duration), -4) AS INTEGER)

for:

Jan 2025 – Present

CORRECT:

For Present rows use:

CAST(STRFTIME('%Y', 'now') AS INTEGER)

for the end year and:

CAST(STRFTIME('%m', 'now') AS INTEGER)

for the end month.

---

INCORRECT:

strftime('%Y', w.duration)

CORRECT:

Use explicit year extraction from w.duration.

---

INCORRECT:

ROUND(SUM(total_months), 2)

when the requested output is years.

CORRECT:

ROUND(SUM(total_months) / 12.0, 2)

============================================================
FINAL WORK EXPERIENCE RULE
==========================

When answering work-experience duration questions:

1. Use work_experience_df.

2. Join work_experience_df to master_df using:

   screening_header_id
   requisition_header_id
   candidate_line_id

3. Match the candidate using:

   LOWER(TRIM(m.candidate_name))

4. When a specific previous/current role is requested,
   match:

   LOWER(TRIM(w.job_title))

5. When a specific company is requested, match:

   LOWER(TRIM(w.company_name))

6. Parse the start month, start year, end month and end
   year from w.duration.

7. Month extraction MUST use:

   LOWER(SUBSTR(...))

8. Convert month names to month numbers using CASE.

9. If the row ends with Present, use the current month
   and current year.

10. Calculate the duration of every matching row in MONTHS.

11. SUM all matching months.

12. Convert total months to years using:

    total_months / 12.0

13. Use:

    ROUND(..., 2)

    when the requested output is decimal years.

14. NEVER treat w.duration as a numeric value.

15. NEVER directly CAST month names such as Jun or Jan
    to INTEGER.

16. NEVER use strftime() directly on:

    Jun 2018
    Jan 2020

17. strftime() may be used with 'now' for Present rows.

18. NEVER use case-sensitive month matching such as:

    CASE SUBSTR(...)

19. ALWAYS use:

    CASE LOWER(SUBSTR(...))

20. NEVER use m.requisition_title as the candidate's
    previous work-experience role.

21. NEVER drop a Present row from total experience.

22. NEVER return months as years.

23. ALWAYS divide total months by 12.0 before returning
    total years.

24. When multiple experience rows match, SUM MONTHS first,
    then convert to YEARS.

============================================================
FINAL VALIDATION BEFORE RETURNING SQL
=====================================

Before returning SQL, verify that:

* the candidate is matched correctly
* the correct work-experience table is used
* the join keys are correct
* w.job_title is used for previous/current work roles
* w.company_name is used when a company is explicitly requested
* w.duration is parsed correctly
* start month is normalized using LOWER()
* end month is normalized using LOWER()
* start year is extracted correctly
* completed end year is extracted correctly
* Present rows use the current month/year
* Present rows are not ignored
* elapsed months are calculated correctly
* multiple rows are summed in MONTHS
* total months are divided by 12.0
* ROUND(..., 2) is applied to the final years value
* the SQL does not return months while labeling them as years
* the SQL does not use CAST(w.duration AS INTEGER)
* the SQL does not CAST Jun or Jan directly to INTEGER
* the SQL does not use strftime() directly on Jun 2018 or Jan 2020
* the SQL does not use CASE SUBSTR(...) for month matching
* the SQL uses CASE LOWER(SUBSTR(...))
* the SQL does not use m.requisition_title for work-experience roles
* the SQL does not return 0 or NULL because of failed duration parsing
* the SQL does not exclude valid Present experience

For:

Jun 2018 – Jan 2020

the correct duration is:

19 months

or:

1.58 years

For:

Jan 2025 – Present

the duration must be calculated using the current month
and current year.

For total work experience:

SUM(all matching months) / 12.0

# must be used before returning years.

============================================================
WHEN BOTH TABLES ARE REQUIRED
============================================================

Use:

master_df m
JOIN work_experience_df w

with:

m.screening_header_id =
w.screening_header_id

AND

m.requisition_header_id =
w.requisition_header_id

AND

m.candidate_line_id =
w.candidate_line_id

============================================================
SQL RULES
============================================================

1. Return one SELECT query only.

2. Use SQLite-compatible SQL.

3. Never use SELECT *.

4. Never invent tables.

5. Never invent columns.

6. Only use:

   master_df
   work_experience_df

7. Use LIMIT 50 for normal multi-row queries.

8. Do not use LIMIT for scalar aggregates.

9. Use LIMIT 1 only for explicitly single-result questions.

10. Use COUNT(DISTINCT ...) for unique candidate applications.

11. Never SUM requisition_applications.

12. Use LOWER(...) for case-insensitive comparisons.

13. When the user asks only for candidate names,
    SELECT only:

    m.candidate_name

14. Do not return email, skills, education, certifications,
    AI score, current role, or work experience unless the
    user explicitly asks for those fields.

15. Use DISTINCT when listing candidate names to avoid
    duplicate candidate names caused by repeated records.

============================================================
FINAL OUTPUT
============================================================

Return SQL ONLY.

No explanation.

No markdown.

No JSON.

No comments.

"""

    prompt = PromptTemplate(
        input_variables=[
            "question",
            "hr_database_schema"
        ],
        template=template
    )

    final_prompt_string = prompt.format(
        question=state["question"],
        hr_database_schema=HR_DATABASE_SCHEMA
    )

    response = query_generator.invoke(
        final_prompt_string
    )

    sql = clean_sql(
        response.content
    )

    print(
        "Generated SQL:"
    )

    print(
        sql
    )

    print(
        "EXIT generate_query_hybrid"
    )

    return {
        "query":
            sql,

        "query_history":
            [sql]
    }


# ============================================================
# EVALUATE SQL
# ============================================================

def evaluate_query_hybrid(
    state: QueryState
):

    print(
        "ENTER evaluate_query_hybrid"
    )

    template = """

You are an expert SQL Quality Assurance Agent for an HR
Recruitment Question Answering system.

Evaluate the generated SQL using ONLY the supplied schema
and the user's question.

USER QUESTION:

{question}

GENERATED SQL:

{query}

SCHEMA:

{hr_database_schema}

Rules:

1. The SQL may use only master_df and work_experience_df.

2. No invented columns.

3. No invented tables.

4. Only SELECT statements.

5. No SELECT *.

6. Requisition questions normally use master_df.

7. Candidate questions normally use master_df.

8. Work experience questions use work_experience_df.

9. Questions requiring both must use all three relationship keys:

   m.screening_header_id = w.screening_header_id

   AND

   m.requisition_header_id = w.requisition_header_id

   AND

   m.candidate_line_id = w.candidate_line_id

10. Job title questions must use requisition_title.

11. Requisition state questions must use requisition_state_name.

12. Requisition phase questions must use requisition_phase_name.

13. Candidate application status must use
    candidate_public_state_name.

14. AI score must use screening_ai_score.

15. Skills must use screening_skills.

16. Do not approve SQL that changes the business meaning
    of the user's question.

Return ONLY:

{{
    "evaluation": "approved",
    "feedback": "The SQL correctly answers the question and follows the schema."
}}

OR:

{{
    "evaluation": "needs_improvement",
    "feedback": "Explain specifically what is wrong with the SQL."
}}

============================================================
WORK EXPERIENCE DURATION VALIDATION
============================================================

When evaluating SQL for work-experience duration questions:

1. Inspect the actual format of:

   w.duration

2. The duration may contain a month/year date range such as:

   Jun 2018 – Jan 2020

3. For a month/year range, the SQL must explicitly parse:

   - start month
   - start year
   - end month
   - end year

4. Do NOT treat the duration text as a numeric value.

5. Reject SQL that:

   - CASTs "Jun" or "Jan" directly to INTEGER
   - extracts only the year and ignores the month
   - uses strftime() directly on text such as "Jun 2018"
   - uses strftime() directly on text such as "Jan 2020"
   - attempts to calculate the duration from an incomplete
     date string
   - produces NULL for a valid duration value

6. Calculate elapsed months using:

   (
       end_year - start_year
   ) * 12
   +
   (
       end_month_number - start_month_number
   )

7. When the user asks for years, convert total months to
   years using:

   total_months / 12.0

8. Use ROUND(..., 2) when returning decimal years.

9. When multiple work-experience records match the same
   candidate and job/company, calculate the duration of each
   matching record, SUM the total months, and only then
   convert the total months to years.

============================================================
WORK EXPERIENCE MONTH CASE-SENSITIVITY
============================================================

Month extraction MUST be case-insensitive.

For example:

    Jun 2018 – Jan 2020

The extracted values may be:

    Jun
    Jan

Before comparing the month names, normalize them using:

    LOWER(SUBSTR(...))

Correct:

CASE LOWER(SUBSTR(TRIM(w.duration), 1, 3))
    WHEN 'jan' THEN 1
    WHEN 'feb' THEN 2
    WHEN 'mar' THEN 3
    WHEN 'apr' THEN 4
    WHEN 'may' THEN 5
    WHEN 'jun' THEN 6
    WHEN 'jul' THEN 7
    WHEN 'aug' THEN 8
    WHEN 'sep' THEN 9
    WHEN 'oct' THEN 10
    WHEN 'nov' THEN 11
    WHEN 'dec' THEN 12
END

For the end month:

CASE LOWER(SUBSTR(TRIM(w.duration), -8, 3))
    WHEN 'jan' THEN 1
    WHEN 'feb' THEN 2
    WHEN 'mar' THEN 3
    WHEN 'apr' THEN 4
    WHEN 'may' THEN 5
    WHEN 'jun' THEN 6
    WHEN 'jul' THEN 7
    WHEN 'aug' THEN 8
    WHEN 'sep' THEN 9
    WHEN 'oct' THEN 10
    WHEN 'nov' THEN 11
    WHEN 'dec' THEN 12
END

Incorrect:

CASE SUBSTR(TRIM(w.duration), 1, 3)
    WHEN 'jan' THEN 1
    WHEN 'feb' THEN 2
    WHEN 'mar' THEN 3
    ...
END

Reject SQL that compares extracted month names without
normalizing their case.

============================================================
WORK EXPERIENCE JOB TITLE FILTER
============================================================

When the user asks about experience worked as a particular
job title, use:

    w.job_title

Do NOT use:

    m.requisition_title

For example:

User:

"How many years did Akhil Kotha work as Oracle HCM Consultant?"

Correct filtering:

LOWER(TRIM(w.job_title)) =
LOWER(TRIM('Oracle HCM Consultant'))

The candidate should be matched using:

LOWER(TRIM(m.candidate_name)) =
LOWER(TRIM('Akhil Kotha'))

The work-experience records must be joined to master_df using:

m.screening_header_id =
w.screening_header_id

AND

m.requisition_header_id =
w.requisition_header_id

AND

m.candidate_line_id =
w.candidate_line_id

============================================================
WORK EXPERIENCE VALIDATION EXAMPLE
============================================================

Given:

Candidate:
Akhil Kotha

Job Title:
Oracle HCM Consultant

Duration:
Jun 2018 – Jan 2020

The SQL should calculate:

Start month = 6
Start year  = 2018
End month   = 1
End year    = 2020

Elapsed months:

(2020 - 2018) * 12 + (1 - 6)

= 19 months

Years:

19 / 12.0

= 1.5833...

Rounded:

1.58 years

A query that returns:

0
NULL
or another value because the month parsing failed
must NOT be approved.

============================================================
FINAL EVALUATION RULE
============================================================

Do not approve a query merely because:

- the tables are valid
- the columns are valid
- the JOIN keys are valid
- the SQL is syntactically valid

The evaluator must verify that the duration calculation
matches the actual format stored in w.duration and that
month names are parsed case-insensitively.

"""

    prompt = PromptTemplate(

        input_variables=[
            "question",
            "query",
            "hr_database_schema"
        ],

        template=template
    )

    final_prompt_string = prompt.format(

        question=state["question"],

        query=state["query"],

        hr_database_schema=
            HR_DATABASE_SCHEMA
    )

    response = query_evaluator.invoke(
        final_prompt_string
    )

    data = extract_json(
        response.content
    )

    evaluation = data.get(
        "evaluation",
        "needs_improvement"
    )

    feedback = data.get(
        "feedback",
        "No feedback provided."
    )

    if evaluation not in [
        "approved",
        "needs_improvement"
    ]:

        evaluation = (
            "needs_improvement"
        )

    print(
        "Evaluation:",
        evaluation
    )

    print(
        "Feedback:",
        feedback
    )

    print(
        "EXIT evaluate_query_hybrid"
    )

    return {

        "evaluation":
            evaluation,

        "feedback":
            feedback,

        "feedback_history":
            [feedback]
    }


# ============================================================
# OPTIMIZE SQL
# ============================================================

def optimize_query_hybrid(
    state: QueryState
):

    print(
        "ENTER optimize_query_hybrid"
    )

    template = """

You are an expert SQLite SQL Optimization Agent.

Correct the generated SQL using:

1. User question
2. Current SQL
3. Evaluator feedback
4. HR database schema

USER QUESTION:

{question}

CURRENT SQL:

{query}

FEEDBACK:

{feedback}

SCHEMA:

{hr_database_schema}

Rules:

- Only use master_df and work_experience_df.
- Only SELECT statements.
- Never use SELECT *.
- Never invent columns.
- Never invent tables.
- Job title questions use requisition_title.
- Requisition state uses requisition_state_name.
- Requisition phase uses requisition_phase_name.
- Candidate application state uses candidate_public_state_name.
- AI score uses screening_ai_score.
- Skills use screening_skills.
- Work experience uses work_experience_df.
- For JOINs use all three relationship keys.
- For multiple matching job titles, return requisition_number,
  requisition_title and the requested property when useful.
- Return SQL only.

"""

    prompt = PromptTemplate(

        input_variables=[
            "question",
            "query",
            "feedback",
            "hr_database_schema"
        ],

        template=template
    )

    final_prompt_string = prompt.format(

        question=state["question"],

        query=state["query"],

        feedback=state["feedback"],

        hr_database_schema=
            HR_DATABASE_SCHEMA
    )

    response = query_optimizer.invoke(
        final_prompt_string
    )

    optimized_sql = clean_sql(
        response.content
    )

    print(
        "Optimized SQL:"
    )

    print(
        optimized_sql
    )

    print(
        "EXIT optimize_query_hybrid"
    )

    return {

        "query":
            optimized_sql,

        "iteration":
            state["iteration"] + 1,

        "query_history":
            [optimized_sql]
    }


# ============================================================
# RUN SQL
# ============================================================

def run_sql_node(
    state: QueryState
):

    print(
        "ENTER run_sql_node"
    )

    sql_query = state["query"]

    try:

        master_df = (
            state["master_df"].copy()
        )

        work_experience_df = (
            state["work_experience_df"].copy()
        )

        # ====================================================
        # CONVERT JOIN KEYS
        # ====================================================

        master_keys = [
            "screening_header_id",
            "requisition_header_id",
            "candidate_line_id"
        ]

        work_keys = [
            "screening_header_id",
            "requisition_header_id",
            "candidate_line_id"
        ]

        for column in master_keys:

            if column in master_df.columns:

                master_df[column] = pd.to_numeric(
                    master_df[column],
                    errors="coerce"
                )

        for column in work_keys:

            if column in work_experience_df.columns:

                work_experience_df[column] = pd.to_numeric(
                    work_experience_df[column],
                    errors="coerce"
                )

        # ====================================================
        # SQL ENVIRONMENT
        # ====================================================

        env = {

            "master_df":
                master_df,

            "work_experience_df":
                work_experience_df
        }

        # ====================================================
        # CANNOT ANSWER
        # ====================================================

        if (
            sql_query.strip()
            ==
            "CANNOT_ANSWER_FROM_SCHEMA"
        ):

            return {

                "sql_result":
                    "CANNOT_ANSWER_FROM_SCHEMA"
            }

        # ====================================================
        # EXECUTE
        # ====================================================

        print(
            "SQL QUERY:"
        )

        print(
            sql_query
        )

        result = sqldf(
            sql_query,
            env
        )

        print(
            "SQL RESULT:"
        )

        print(
            result
        )

        # ====================================================
        # IMPORTANT EMPTY-RESULT HANDLING
        # ====================================================

        if result.empty:

            return {

                "sql_result":
                    ""
            }

        return {

            "sql_result":
                result.to_string(
                    index=False
                )
        }

    except Exception as e:

        import traceback

        traceback.print_exc()

        print(
            "SQL execution failed:",
            str(e)
        )

        return {

            "sql_result":
                f"SQL Error: {e}"
        }


# ============================================================
# UNKNOWN QUESTION
# ============================================================

def handel_unknown_question(
    state: QueryState
):

    print(
        "ENTER handel_unknown_question"
    )

    return {

        "result_summary":
            (
                "Sorry, this question cannot be answered "
                "using the available HR recruitment data."
            )
    }


# ============================================================
# RESULT SUMMARY
# ============================================================

def result_summary(
    state: QueryState
):

    print(
        "ENTER result_summary"
    )

    sql_result = (
        state.get(
            "sql_result",
            ""
        )
    )

    # ========================================================
    # EMPTY RESULT
    # ========================================================

    if not sql_result.strip():

        return {

            "result_summary":
                (
                    "No matching records were found."
                )
        }

    # ========================================================
    # CANNOT ANSWER
    # ========================================================

    if (
        sql_result.strip()
        ==
        "CANNOT_ANSWER_FROM_SCHEMA"
    ):

        return {

            "result_summary":
                (
                    "Sorry, this question cannot be answered "
                    "using the available HR recruitment data."
                )
        }

    # ========================================================
    # SUMMARIZER PROMPT
    # ========================================================

    template = """

You are an HR Recruitment Data Analysis Assistant.

Answer the user's question using ONLY the SQL result below.

Do not invent any information.

Do not add information that does not exist in the SQL result.

Do not mention SQL.

Do not mention the database.

Do not mention internal processing.

============================================================
USER QUESTION
============================================================

{question}

============================================================
SQL RESULT
============================================================

{sql_result}

============================================================
RULES
============================================================

1. Answer the question directly.

2. Use only information in the SQL result.

3. If there are multiple requisitions, clearly distinguish
   them using requisition number.

4. If there are multiple candidates, clearly distinguish
   them.

5. If the SQL result contains:

   requisition_number
   requisition_title
   requisition_state_name

   preserve the relationship between those values.

6. Do NOT say that information is missing if the SQL result
   contains valid rows.

7. If the SQL result is empty, state that no matching
   records were found.

8. If the user asks for a single value and exactly one
   matching value exists, answer directly.

9. If multiple values exist, list them clearly.

10. Keep the answer concise.

Examples:

Question:
"What is the state of Site Engineer?"

SQL result:

requisition_number requisition_title requisition_state_name
21                 Site Engineer     Posted
102                Site Engineer     Unposted

Answer:

There are multiple Site Engineer requisitions:

Requisition 21 — Posted
Requisition 102 — Unposted

Question:
"What is the state of Python SDE-1?"

SQL result:

requisition_number requisition_title requisition_state_name
138                Python SDE-1      In Progress

Answer:

Python SDE-1 is currently In Progress.

Return only the final answer.
"""

    prompt = PromptTemplate(

        input_variables=[
            "question",
            "sql_result"
        ],

        template=template
    )

    final_prompt_string = prompt.format(

        question=state["question"],

        sql_result=sql_result
    )

    response = result_summarizer_llm.invoke(
        final_prompt_string
    )

    summary = (
        response.content.strip()
    )

    print(
        "RESULT SUMMARY:"
    )

    print(
        summary
    )

    print(
        "EXIT result_summary"
    )

    return {

        "result_summary":
            summary
    }


# ============================================================
# BUILD LANGGRAPH
# ============================================================

builder = StateGraph(
    QueryState
)


# ============================================================
# ADD NODES
# ============================================================

builder.add_node(
    "handel_unknown_question",
    handel_unknown_question
)

builder.add_node(
    "intent_router",
    intent_router
)

builder.add_node(
    "generate_query_hybrid",
    generate_query_hybrid
)

builder.add_node(
    "evaluate_query_hybrid",
    evaluate_query_hybrid
)

builder.add_node(
    "optimize_query_hybrid",
    optimize_query_hybrid
)

builder.add_node(
    "run_sql",
    run_sql_node
)

builder.add_node(
    "result_summary",
    result_summary
)


# ============================================================
# ROUTE AFTER INTENT
# ============================================================

def route_after_intent(
    state: QueryState
):

    route = state.get(
        "route",
        "UNKNOWN_ROUTE"
    )

    print(
        "ROUTE AFTER INTENT:",
        route
    )

    if route == "HYBRID_ROUTE":

        return (
            "generate_query_hybrid"
        )

    return (
        "handel_unknown_question"
    )


# ============================================================
# ROUTE AFTER EVALUATION
# ============================================================

def route_after_hybrid_evaluation(
    state: QueryState
):

    query = state.get(
        "query",
        ""
    ).strip()

    evaluation = state.get(
        "evaluation",
        "needs_improvement"
    )

    iteration = state.get(
        "iteration",
        0
    )

    max_iteration = state.get(
        "max_iteration",
        5
    )

    print(
        "ROUTE AFTER EVALUATION"
    )

    print(
        "Query:",
        query
    )

    print(
        "Evaluation:",
        evaluation
    )

    print(
        "Iteration:",
        iteration
    )

    # ========================================================
    # CANNOT ANSWER
    # ========================================================

    if (
        query
        ==
        "CANNOT_ANSWER_FROM_SCHEMA"
    ):

        return (
            "handel_unknown_question"
        )

    # ========================================================
    # APPROVED
    # ========================================================

    if (
        evaluation
        ==
        "approved"
    ):

        return (
            "run_sql"
        )

    # ========================================================
    # MAX ITERATIONS
    # ========================================================

    if (
        iteration
        >=
        max_iteration
    ):

        return (
            "handel_unknown_question"
        )

    # ========================================================
    # OPTIMIZE
    # ========================================================

    return (
        "optimize_query_hybrid"
    )


# ============================================================
# GRAPH EDGES
# ============================================================

builder.add_edge(
    START,
    "intent_router"
)


builder.add_conditional_edges(

    "intent_router",

    route_after_intent,

    {
        "generate_query_hybrid":
            "generate_query_hybrid",

        "handel_unknown_question":
            "handel_unknown_question"
    }
)


builder.add_edge(
    "generate_query_hybrid",
    "evaluate_query_hybrid"
)


builder.add_conditional_edges(

    "evaluate_query_hybrid",

    route_after_hybrid_evaluation,

    {
        "optimize_query_hybrid":
            "optimize_query_hybrid",

        "run_sql":
            "run_sql",

        "handel_unknown_question":
            "handel_unknown_question"
    }
)


builder.add_edge(
    "optimize_query_hybrid",
    "evaluate_query_hybrid"
)


builder.add_edge(
    "run_sql",
    "result_summary"
)


builder.add_edge(
    "result_summary",
    END
)


builder.add_edge(
    "handel_unknown_question",
    END
)


# ============================================================
# COMPILE GRAPH
# ============================================================

sql_app = builder.compile()


# ============================================================
# EXECUTE HR Q&A
# ============================================================

def executeSql(
    question: str,
    master_df: pd.DataFrame,
    work_experience_df: pd.DataFrame
):

    print(
        "EXECUTE SQL START"
    )

    # ========================================================
    # INITIAL STATE
    # ========================================================

    initial_state = {

        "question":
            question,

        "master_df":
            master_df,

        "work_experience_df":
            work_experience_df,

        "route_reason":
            "",

        "route":
            "UNKNOWN_ROUTE",

        "query":
            "",

        "evaluation":
            "needs_improvement",

        "feedback":
            "",

        "iteration":
            0,

        "max_iteration":
            5,

        "sql_result":
            "",

        "result_summary":
            "",

        "query_history":
            [],

        "feedback_history":
            []
    }

    # ========================================================
    # RUN LANGGRAPH
    # ========================================================

    final_state = sql_app.invoke(
        initial_state
    )

    print(
        "EXECUTE SQL END"
    )

    # ========================================================
    # RETURN RESULT
    # ========================================================

    return {

        "question":
            final_state.get(
                "question"
            ),

        "route":
            final_state.get(
                "route"
            ),

        "route_reason":
            final_state.get(
                "route_reason"
            ),

        "query":
            final_state.get(
                "query"
            ),

        "sql_result":
            final_state.get(
                "sql_result"
            ),

        "result_summary":
            final_state.get(
                "result_summary"
            ),

        "evaluation":
            final_state.get(
                "evaluation"
            ),

        "feedback":
            final_state.get(
                "feedback"
            ),

        "feedback_history":
            final_state.get(
                "feedback_history",
                []
            ),

        "query_history":
            final_state.get(
                "query_history",
                []
            )
    }
