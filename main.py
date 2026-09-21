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
CANDIDATE APPLICATION STATE — INTENT NORMALIZATION
==================================================

The user's wording for a candidate application state may NOT
exactly match the value stored in the database.

Before generating SQL, FIRST understand the user's intended
candidate state.

Do NOT blindly copy the user's wording into the SQL WHERE
clause.

The LLM must:

1. Understand the meaning of the complete user question.
2. Identify whether the user is asking about candidate
   application state/status.
3. Normalize the user's natural-language state expression
   to the canonical state value stored in PublicStateName.
4. Use the canonical database value in the SQL.
5. Do NOT invent a new state value from the user's wording.
6. Do NOT assume word order in the user's question must match
   the database value.
7. Ignore capitalization and harmless grammatical variations.

============================================================
CANONICAL CANDIDATE STATES
==========================

The candidate application states available in the HR data are:

1. Screening Completed
2. 1st Level Interview Scheduled
3. 1st level Interview to be Scheduled
4. Selected for Offer
5. Rejected by Employer
6. 2nd Level Interview to be Scheduled
7. 2nd Level Interview Scheduled
8. 2nd Level Interview Completed
9. To be Created

When a user asks about candidate status, map the user's wording
to one of these canonical states.

============================================================
STATE 1 — SCREENING COMPLETED
=============================

The following expressions should be understood as:

PublicStateName = 'Screening Completed'

Examples:

* "completed screening"
* "screening completed"
* "finished screening"
* "done with screening"
* "screening is complete"
* "completed the screening"
* "candidates who completed screening"
* "candidates who have completed the screening"
* "who finished screening?"
* "who has finished the screening?"

IMPORTANT:

"completed screening" and "screening completed" have the same
business meaning.

The database value is:

'Screening Completed'

Therefore, do NOT generate:

PublicStateName = 'Completed Screening'

Generate:

PublicStateName = 'Screening Completed'

============================================================
STATE 2 — 1ST LEVEL INTERVIEW SCHEDULED
=======================================

The following expressions should be understood as:

PublicStateName = '1st Level Interview Scheduled'

Examples:

* "first level interview scheduled"
* "1st level interview scheduled"
* "first-level interview is scheduled"
* "candidates with a scheduled first level interview"
* "who has their first level interview scheduled?"

Use the canonical database state:

'1st Level Interview Scheduled'

============================================================
STATE 3 — 1ST LEVEL INTERVIEW TO BE SCHEDULED
=============================================

The following expressions should be understood as:

PublicStateName = '1st level Interview to be Scheduled'

Examples:

* "first level interview to be scheduled"
* "1st level interview to be scheduled"
* "first level interview still needs to be scheduled"
* "who needs a first level interview scheduled?"
* "candidates waiting for first level interview scheduling"

Use the canonical database state:

'1st level Interview to be Scheduled'

============================================================
STATE 4 — SELECTED FOR OFFER
============================

The following expressions should be understood as:

PublicStateName = 'Selected for Offer'

Examples:

* "selected for offer"
* "candidates selected for offer"
* "who was selected for an offer?"
* "who are selected for offer?"

Use:

'Selected for Offer'

============================================================
STATE 5 — REJECTED BY EMPLOYER
==============================

The following expressions should be understood as:

PublicStateName = 'Rejected by Employer'

Examples:

* "rejected by employer"
* "candidates rejected by the employer"
* "who was rejected?"
* "who are the rejected candidates?"

Use:

'Rejected by Employer'

============================================================
STATE 6 — 2ND LEVEL INTERVIEW TO BE SCHEDULED
=============================================

The following expressions should be understood as:

PublicStateName = '2nd Level Interview to be Scheduled'

Examples:

* "second level interview to be scheduled"
* "2nd level interview to be scheduled"
* "candidates waiting for second level interview scheduling"
* "who still needs a second level interview?"

Use:

'2nd Level Interview to be Scheduled'

============================================================
STATE 7 — 2ND LEVEL INTERVIEW SCHEDULED
=======================================

The following expressions should be understood as:

PublicStateName = '2nd Level Interview Scheduled'

Examples:

* "second level interview scheduled"
* "2nd level interview scheduled"
* "candidates with a scheduled second level interview"
* "who has their second level interview scheduled?"

Use:

'2nd Level Interview Scheduled'

============================================================
STATE 8 — 2ND LEVEL INTERVIEW COMPLETED
=======================================

The following expressions should be understood as:

PublicStateName = '2nd Level Interview Completed'

Examples:

* "second level interview completed"
* "2nd level interview completed"
* "finished second level interview"
* "completed the second interview"
* "candidates who finished the second level interview"

Use:

'2nd Level Interview Completed'

============================================================
STATE 9 — TO BE CREATED
=======================

The following expressions should be understood as:

PublicStateName = 'To be Created'

Examples:

* "to be created"
* "candidates in to be created"
* "which candidates are to be created?"

Use:

'To be Created'

============================================================
IMPORTANT QUERY UNDERSTANDING RULE
==================================

The LLM must understand the COMPLETE USER INTENT.

Do NOT perform literal keyword matching.

For example:

User:
"Can you give those who are completed screening in
Oracle HCM Functional Specialist?"

Interpretation:

candidate state = Screening Completed

Do NOT interpret the state as:

'Completed Screening'

Instead generate SQL using:

PublicStateName = 'Screening Completed'

---

User:
"Can you give those who finished screening in Oracle HCM
Functional Specialist?"

Interpretation:

candidate state = Screening Completed

---

User:
"Show candidates whose first interview has already been
scheduled for Oracle HCM Functional Specialist."

Interpretation:

candidate state = 1st Level Interview Scheduled

---

User:
"Who is still waiting for the second level interview to
be scheduled?"

Interpretation:

candidate state = 2nd Level Interview to be Scheduled

============================================================
STATE QUERY GENERATION
======================

When the user asks:

"Give me the candidates who <state expression> for <job title>"

the SQL should contain BOTH:

1. The correct requisition/job title filter.
2. The normalized canonical PublicStateName filter.

Example:

User:
"Can you give those who completed screening in
Oracle HCM Functional Specialist?"

Correct conceptual SQL:

SELECT DISTINCT
m.candidate_name
FROM master_df AS m
WHERE
m.requisition_number = '130'
AND LOWER(TRIM(m.requisition_title)) =
LOWER(TRIM('Oracle HCM Functional Specialist'))
AND LOWER(TRIM(m.candidate_public_state_name)) =
LOWER(TRIM('Screening Completed'));

============================================================
CRITICAL RULE
=============

The wording used by the user and the value stored in the
database do NOT need to be identical.

Always distinguish:

USER EXPRESSION
from
DATABASE VALUE

Examples:

"completed screening"
-> "Screening Completed"

"finished screening"
-> "Screening Completed"

"first interview is scheduled"
-> "1st Level Interview Scheduled"

"second interview waiting to be scheduled"
-> "2nd Level Interview to be Scheduled"

"finished second interview"
-> "2nd Level Interview Completed"

The LLM must normalize the meaning before generating SQL.

============================================================
DO NOT INVENT STATES
====================

Only use the canonical states actually available in the
HR data.

Never generate states such as:

* "Completed Screening"
* "First Interview Done"
* "Interview Pending"
* "Offer Selected"
* "Employer Rejection"

unless those exact values actually exist in the database.

Map natural language to the closest supported canonical
business state.

============================================================
FINAL VALIDATION
================

Before returning SQL, verify:

* What is the user asking for?
* Is the user asking about candidate application state?
* What candidate state does the user's wording mean?
* What is the exact canonical state stored in the database?
* Is the canonical state used in the WHERE clause?
* Is the correct requisition/job title also filtered?
* Is candidate_name returned when the user asks for candidates?

Never treat the user's wording as the database value without
first checking its intended meaning.


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

contains a date range in TEXT format.

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

1. COMPLETED EXPERIENCE

<start_month> <start_year> – <end_month> <end_year>

Example:

Jun 2018 – Jan 2020

2. CURRENT EXPERIENCE

<start_month> <start_year> – Present

Example:

Jan 2025 – Present

The SQL MUST support both formats.

The separator between the start and end values may be:

*

–
—

The spacing around the separator may also vary.

Examples:

Jun 2018 – Jan 2020

Jun 2018- Jan 2020

Jun 2018 - Jan 2020

Jun 2018–Jan 2020

Jun 2018—Jan 2020

Therefore, DO NOT rely on fixed character positions in the
original w.duration string.

============================================================
DURATION NORMALIZATION
======================

Before parsing the duration, normalize the separator.

Convert the following separators:

*

–
—

into:

|

Conceptually use:

REPLACE(
REPLACE(
REPLACE(
TRIM(w.duration),
'—',
'|'
),
'–',
'|'
),
'-',
'|'
)

For example:

Jun 2018 – Jan 2020

must become conceptually:

Jun 2018|Jan 2020

And:

Jun 2018-Jan 2020

must become:

Jun 2018|Jan 2020

And:

Jun 2018—Jan 2020

must become:

Jun 2018|Jan 2020

IMPORTANT:

Normalization MUST happen before extracting the start and
end values.

============================================================
START PART EXTRACTION
=====================

After normalization, extract the portion BEFORE:

|

For example:

Jun 2018|Jan 2020

must produce:

start_part = Jun 2018

Conceptually:

TRIM(
SUBSTR(
normalized_duration,
1,
INSTR(normalized_duration, '|') - 1
)
)

Do NOT extract the start year directly from the original
w.duration before normalization.

============================================================
END PART EXTRACTION
===================

After normalization, extract the portion AFTER:

|

For example:

Jun 2018|Jan 2020

must produce:

end_part = Jan 2020

Conceptually:

TRIM(
SUBSTR(
normalized_duration,
INSTR(normalized_duration, '|') + 1
)
)

Do NOT extract the end month directly from the original
w.duration before normalization.

============================================================
MANDATORY CTE PARSING STRUCTURE
===============================

When the duration calculation is complex, prefer using
separate CTEs so that parsing is clear and safe.

Preferred conceptual structure:

WITH work_rows AS (
SELECT DISTINCT
screening_header_id,
requisition_header_id,
candidate_line_id,
job_title,
company_name,
duration
FROM work_experience_df
),

normalized_rows AS (
SELECT
screening_header_id,
requisition_header_id,
candidate_line_id,
job_title,
company_name,
duration,

```
    REPLACE(
        REPLACE(
            REPLACE(
                TRIM(duration),
                '—',
                '|'
            ),
            '–',
            '|'
        ),
        '-',
        '|'
    ) AS normalized_duration

FROM work_rows
```

),

split_rows AS (
SELECT
screening_header_id,
requisition_header_id,
candidate_line_id,
job_title,
company_name,
duration,
normalized_duration,

```
    TRIM(
        SUBSTR(
            normalized_duration,
            1,
            INSTR(normalized_duration, '|') - 1
        )
    ) AS start_part,

    TRIM(
        SUBSTR(
            normalized_duration,
            INSTR(normalized_duration, '|') + 1
        )
    ) AS end_part

FROM normalized_rows
```

)

Additional CTEs may then be used to calculate:

start_month
start_year
end_month
end_year
duration_months

IMPORTANT:

Using multiple CTEs is preferred because SQL aliases created
in one SELECT should not be assumed to be reusable in the
same SELECT.

============================================================
HOW TO PARSE START DATE
=======================

After extracting:

start_part

the start month is the first three characters.

Use:

LOWER(
SUBSTR(
start_part,
1,
3
)
)

Examples:

Jan
JAN
jan

must all become:

jan

The start year is the final four characters of start_part.

Use:

CAST(
SUBSTR(
start_part,
-4
)
AS INTEGER
)

Examples:

Jun 2018
-> 2018

Jan 2025
-> 2025

IMPORTANT:

The start month MUST be normalized using LOWER().

============================================================
START MONTH TO MONTH NUMBER
===========================

Use:

CASE LOWER(
SUBSTR(
start_part,
1,
3
)
)
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

DO NOT use:

CASE SUBSTR(...)

The SQL MUST use:

CASE LOWER(SUBSTR(...))

============================================================
HOW TO PARSE END DATE
=====================

For a COMPLETED duration:

Jun 2018 – Jan 2020

after normalization:

Jun 2018|Jan 2020

end_part is:

Jan 2020

Extract the end month using:

LOWER(
SUBSTR(
end_part,
1,
3
)
)

Extract the end year using:

CAST(
SUBSTR(
end_part,
-4
)
AS INTEGER
)

IMPORTANT:

Do NOT use fixed positions such as:

SUBSTR(TRIM(w.duration), -8, 3)

on the original duration.

The SQL must first create end_part.

============================================================
END MONTH TO MONTH NUMBER
=========================

Use:

CASE LOWER(
SUBSTR(
end_part,
1,
3
)
)
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

IMPORTANT:

Always normalize the month with LOWER().

============================================================
HANDLING "PRESENT"
==================

IMPORTANT:

The end part may be:

Present

Example:

Jan 2025 – Present

Present means the candidate is still working in that role.

DO NOT treat Present as a missing duration.

DO NOT return NULL for a valid Present row.

DO NOT attempt:

CAST(end_part AS INTEGER)

when end_part is Present.

DO NOT attempt to extract a year from Present.

Determine Present using:

LOWER(TRIM(end_part)) = 'present'

or an equivalent case-insensitive condition.

============================================================
CURRENT DATE FOR PRESENT
========================

For Present rows, use the current month:

CAST(
STRFTIME(
'%m',
'now'
)
AS INTEGER
)

Use the current year:

CAST(
STRFTIME(
'%Y',
'now'
)
AS INTEGER
)

IMPORTANT:

strftime() is allowed with:

'now'

because 'now' is a valid SQLite date/time value.

DO NOT use strftime() directly on:

Jun 2018
Jan 2020
Jan 2025

============================================================
DETERMINE WHETHER ROW IS PRESENT
================================

Use:

LOWER(TRIM(end_part)) = 'present'

or an equivalent case-insensitive check.

Example:

CASE
WHEN LOWER(TRIM(end_part)) = 'present'
THEN ...
ELSE ...
END

The Present branch MUST use the current month and current
year.

============================================================
CALCULATE COMPLETED EXPERIENCE IN MONTHS
========================================

For:

Jun 2018 – Jan 2020

use:

start_month = 6
start_year = 2018

end_month = 1
end_year = 2020

Then:

(end_year - start_year) * 12
+
(end_month - start_month)

Therefore:

(2020 - 2018) * 12
+
(1 - 6)

= 19 months

============================================================
CALCULATE PRESENT EXPERIENCE IN MONTHS
======================================

For:

Jan 2025 – Present

use:

start_month = 1
start_year = 2025

current_month = current month
current_year = current year

Then:

(current_year - start_year) * 12
+
(current_month - start_month)

If current month/year is September 2026:

(2026 - 2025) * 12
+
(9 - 1)

= 20 months

============================================================
COMPLETED AND PRESENT ROWS
==========================

The SQL MUST support:

1. Completed:

Jun 2018 – Jan 2020

2. Present:

Jan 2025 – Present

Completed:

Use parsed end_month and end_year.

Present:

Use current month and current year.

The SQL MUST NOT allow a valid Present row to become NULL.

============================================================
UNIQUE WORK EXPERIENCE ROWS
===========================

For TOTAL work-experience calculations, first create unique
work-experience records.

Use:

WITH work_rows AS (
SELECT DISTINCT
screening_header_id,
requisition_header_id,
candidate_line_id,
job_title,
company_name,
duration
FROM work_experience_df
)

IMPORTANT:

Each unique work-experience record must be counted only once.

============================================================
WORK EXPERIENCE JOIN DUPLICATE PREVENTION
=========================================

IMPORTANT:

Do NOT allow duplicate master_df rows to multiply a
work-experience record.

master_df may contain multiple records associated with the
same candidate.

Therefore, for total work-experience calculations:

DO NOT directly do:

FROM master_df m
JOIN work_experience_df w
ON ...

followed by:

SUM(duration_calculation)

unless the query has already guaranteed that each
work-experience record can match only once.

PREFERRED METHOD:

Use work_experience_df as the main table.

Create:

work_rows

with DISTINCT.

Then use:

EXISTS

to verify the requested candidate.

Preferred structure:

WITH work_rows AS (
SELECT DISTINCT
screening_header_id,
requisition_header_id,
candidate_line_id,
job_title,
company_name,
duration
FROM work_experience_df
)

SELECT ...

FROM work_rows w

WHERE EXISTS (
SELECT 1
FROM master_df m
WHERE LOWER(TRIM(m.candidate_name)) =
LOWER(TRIM('Candidate Name'))

```
  AND m.screening_header_id =
      w.screening_header_id

  AND m.requisition_header_id =
      w.requisition_header_id

  AND m.candidate_line_id =
      w.candidate_line_id
```

)

IMPORTANT:

EXISTS verifies that the work-experience row belongs to
the requested candidate without multiplying the row.

============================================================
CANDIDATE MATCHING
==================

Match the candidate using:

LOWER(TRIM(m.candidate_name)) =
LOWER(TRIM('Candidate Name'))

The relationship keys are:

m.screening_header_id =
w.screening_header_id

AND

m.requisition_header_id =
w.requisition_header_id

AND

m.candidate_line_id =
w.candidate_line_id

Do not invent other relationship keys.

============================================================
TOTAL WORK EXPERIENCE
=====================

When the user asks:

* total work experience
* total years of experience
* how many years of work experience
* total how many years
* overall work experience
* overall years of experience
* how many years has the candidate worked
* total experience
* total employment experience

the SQL MUST:

1. Find all UNIQUE work-experience records for the candidate.

2. Prevent duplicate work-experience records.

3. Normalize the duration separator.

4. Extract start_part.

5. Extract end_part.

6. Parse the start month.

7. Parse the start year.

8. Detect whether the end is Present.

9. If Present, use current month/current year.

10. Otherwise parse the end month/year.

11. Calculate each duration in MONTHS.

12. SUM the unique duration months.

13. Divide the total months by 12.0.

14. ROUND the final result to 2 decimals.

The final calculation MUST conceptually be:

ROUND(
SUM(duration_months) / 12.0,
2
)

The final result is YEARS.

============================================================
DO NOT SUM ROUNDED YEARS
========================

Correct:

Record 1 -> months
Record 2 -> months
Record 3 -> months

Then:

SUM(months)

Then:

SUM(months) / 12.0

Then:

ROUND(..., 2)

Incorrect:

Record 1 -> years
Record 2 -> years
Record 3 -> years

Then:

SUM(years)

Do NOT round individual rows to years before summing.

============================================================
TOTAL WORK EXPERIENCE QUERY STRATEGY
====================================

For total work experience, prefer this conceptual structure:

WITH work_rows AS (
SELECT DISTINCT
screening_header_id,
requisition_header_id,
candidate_line_id,
job_title,
company_name,
duration
FROM work_experience_df
),

normalized_rows AS (
SELECT
screening_header_id,
requisition_header_id,
candidate_line_id,
job_title,
company_name,
duration,

```
    REPLACE(
        REPLACE(
            REPLACE(
                TRIM(duration),
                '—',
                '|'
            ),
            '–',
            '|'
        ),
        '-',
        '|'
    ) AS normalized_duration

FROM work_rows
```

),

split_rows AS (
SELECT
screening_header_id,
requisition_header_id,
candidate_line_id,
job_title,
company_name,
duration,

```
    TRIM(
        SUBSTR(
            normalized_duration,
            1,
            INSTR(normalized_duration, '|') - 1
        )
    ) AS start_part,

    TRIM(
        SUBSTR(
            normalized_duration,
            INSTR(normalized_duration, '|') + 1
        )
    ) AS end_part

FROM normalized_rows
```

),

duration_rows AS (
SELECT
screening_header_id,
requisition_header_id,
candidate_line_id,
job_title,
company_name,
duration,
start_part,
end_part,

```
    CASE
        WHEN LOWER(TRIM(end_part)) = 'present'
        THEN
            (
                CAST(STRFTIME('%Y', 'now') AS INTEGER)
                -
                CAST(SUBSTR(start_part, -4) AS INTEGER)
            ) * 12
            +
            (
                CAST(STRFTIME('%m', 'now') AS INTEGER)
                -
                CASE LOWER(SUBSTR(start_part, 1, 3))
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

        ELSE
            (
                CAST(SUBSTR(end_part, -4) AS INTEGER)
                -
                CAST(SUBSTR(start_part, -4) AS INTEGER)
            ) * 12
            +
            (
                CASE LOWER(SUBSTR(end_part, 1, 3))
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

                CASE LOWER(SUBSTR(start_part, 1, 3))
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
    END AS duration_months

FROM split_rows
```

)

SELECT
ROUND(
SUM(duration_months) / 12.0,
2
) AS total_years_experience

FROM duration_rows w

WHERE EXISTS (
SELECT 1
FROM master_df m
WHERE LOWER(TRIM(m.candidate_name)) =
LOWER(TRIM('Candidate Name'))

```
  AND m.screening_header_id =
      w.screening_header_id

  AND m.requisition_header_id =
      w.requisition_header_id

  AND m.candidate_line_id =
      w.candidate_line_id
```

)

IMPORTANT:

This is the PREFERRED structure.

The actual SQL may use equivalent CTEs or equivalent
logic, but it MUST preserve the same behavior.

============================================================
WORK EXPERIENCE JOB TITLE
=========================

When the user asks:

How many years did Akhil Kotha work as Oracle HCM Consultant?

The requested role refers to:

w.job_title

NOT:

m.requisition_title

Use:

LOWER(TRIM(w.job_title)) =
LOWER(TRIM('Oracle HCM Consultant'))

Candidate matching:

LOWER(TRIM(m.candidate_name)) =
LOWER(TRIM('Akhil Kotha'))

============================================================
WORK EXPERIENCE JOB TITLE FILTER
================================

When the user asks for experience in a specific
work-experience role:

filter:

LOWER(TRIM(w.job_title)) =
LOWER(TRIM('Requested Job Title'))

Do NOT use:

m.requisition_title

to identify the previous/current employment role.

The query should conceptually use:

WITH work_rows AS (
SELECT DISTINCT
screening_header_id,
requisition_header_id,
candidate_line_id,
job_title,
company_name,
duration
FROM work_experience_df
)

Then:

FROM work_rows w

WHERE LOWER(TRIM(w.job_title)) =
LOWER(TRIM('Requested Job Title'))

AND EXISTS (
SELECT 1
FROM master_df m
WHERE LOWER(TRIM(m.candidate_name)) =
LOWER(TRIM('Candidate Name'))

```
  AND m.screening_header_id =
      w.screening_header_id

  AND m.requisition_header_id =
      w.requisition_header_id

  AND m.candidate_line_id =
      w.candidate_line_id
```

)

============================================================
WORK EXPERIENCE COMPANY FILTER
==============================

If the user explicitly asks about a company:

Use:

w.company_name

Match:

LOWER(TRIM(w.company_name)) =
LOWER(TRIM('Requested Company'))

Example:

How many years did Akhil Kotha work at Nalsoft Middle East?

Use:

LOWER(TRIM(w.company_name)) =
LOWER(TRIM('Nalsoft Middle East'))

If the user asks for TOTAL work experience across
all companies:

DO NOT add a company filter unless the user explicitly
requested one.

============================================================
WORK EXPERIENCE DETAILS
=======================

When the user asks:

* give the work experience
* show work experience
* list work experience
* provide employment history
* show employment history

return individual work-experience records.

Use:

w.job_title
w.company_name
w.duration

Do NOT calculate total years unless the user explicitly
asks for total years.

The returned work-experience records should be unique.

============================================================
DO NOT USE FIXED POSITIONS ON ORIGINAL DURATION
===============================================

INVALID:

SUBSTR(TRIM(w.duration), 5, 4)

as the universal start-year parser.

INVALID:

SUBSTR(TRIM(w.duration), -8, 3)

as the universal end-month parser.

These expressions depend on the exact separator and spacing.

Correct approach:

w.duration
↓
normalize separator
↓
normalized_duration
↓
start_part
↓
end_part
↓
parse month/year

============================================================
DO NOT USE STRFTIME DIRECTLY ON TEXT
====================================

INVALID:

strftime('%Y', w.duration)

INVALID:

strftime('%m', w.duration)

INVALID:

strftime('%Y', 'Jun 2018')

INVALID:

strftime('%m', 'Jan 2020')

Use explicit parsing for text month/year values.

Allowed:

strftime('%Y', 'now')

strftime('%m', 'now')

only when processing Present.

============================================================
DO NOT CAST MONTH NAMES
=======================

INVALID:

CAST('Jun' AS INTEGER)

INVALID:

CAST('Jan' AS INTEGER)

INVALID:

CAST(w.duration AS INTEGER)

Month names must be converted using CASE.

Correct:

CASE LOWER(SUBSTR(start_part, 1, 3))
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

============================================================
MANDATORY PRESENT VALIDATION
============================

For:

Jan 2025 – Present

the SQL MUST:

1. Extract:

Jan 2025

as start_part.

2. Detect:

Present

as end_part.

3. Extract:

start_month = 1

start_year = 2025

4. Use current month/year.

5. Calculate elapsed months.

DO NOT do:

CAST(
SUBSTR(
end_part,
-4
)
AS INTEGER
)

for Present.

============================================================
MANDATORY MONTH PARSING VALIDATION
==================================

For:

Jun 2018 – Jan 2020

after normalization:

Jun 2018|Jan 2020

start_part:

Jun 2018

end_part:

Jan 2020

Then:

LOWER(SUBSTR(start_part, 1, 3))

must produce:

jun

and:

LOWER(SUBSTR(end_part, 1, 3))

must produce:

jan

Therefore:

jun = 6

jan = 1

Then:

(2020 - 2018) * 12 + (1 - 6)

= 19 months

============================================================
MANDATORY TOTAL EXPERIENCE VALIDATION
=====================================

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

8.17 years

============================================================
MANDATORY DUPLICATE VALIDATION
==============================

Before approving a total work-experience query, verify:

1. work_experience_df is the main source.

2. Unique work-experience rows are created.

3. master_df is used only for candidate verification.

4. EXISTS is preferred.

5. A duplicate master_df row cannot multiply a
   work-experience record.

6. Each unique work-experience record contributes once.

============================================================
NEGATIVE DURATION VALIDATION
============================

A calculated duration_months must not be negative.

Valid:

duration_months >= 0

If:

duration_months < 0

the duration is invalid or the query parsed it incorrectly.

Such a query MUST NOT be approved.

============================================================
MALFORMED DURATION VALIDATION
=============================

The SQL must not silently create a huge total from malformed
duration text.

Examples of suspicious output:

1825.33 years

500 years

1000 years

or any other value that is clearly inconsistent with the
candidate's actual work-history records.

The evaluator MUST NOT approve such a result merely because:

* the SQL executed
* the syntax is valid
* the columns are valid
* the tables are valid
* the month CASE statements exist
* /12.0 exists

The evaluator must inspect the underlying matching
work-experience rows and their calculated duration_months.

============================================================
SUSPICIOUS RESULT VALIDATION
============================

When a result appears unusually large:

inspect the individual work-experience rows.

Conceptually:

SELECT
w.job_title,
w.company_name,
w.duration
FROM work_rows w
WHERE EXISTS (
SELECT 1
FROM master_df m
WHERE LOWER(TRIM(m.candidate_name)) =
LOWER(TRIM('Candidate Name'))

```
  AND m.screening_header_id =
      w.screening_header_id

  AND m.requisition_header_id =
      w.requisition_header_id

  AND m.candidate_line_id =
      w.candidate_line_id
```

)

The evaluator should inspect:

* job_title
* company_name
* duration
* parsed start_part
* parsed end_part
* start month
* start year
* end month
* end year
* duration_months

============================================================
RESULT UNIT
===========

duration_months is MONTHS.

Therefore:

SUM(duration_months)

is also MONTHS.

The final years calculation MUST be:

SUM(duration_months) / 12.0

For decimal years:

ROUND(
SUM(duration_months) / 12.0,
2
)

Never return:

ROUND(
SUM(duration_months),
2
)

when the user asks for years.

============================================================
INCORRECT QUERY PATTERNS
========================

INVALID:

CAST(w.duration AS INTEGER)

---

INVALID:

strftime('%Y', w.duration)

---

INVALID:

strftime('%m', w.duration)

---

INVALID:

CASE SUBSTR(...)

when comparing lowercase month names.

---

CORRECT:

CASE LOWER(SUBSTR(...))

---

INVALID:

m.requisition_title

for identifying the candidate's previous employment role.

---

CORRECT:

w.job_title

---

INVALID:

SUM(months) without dividing by 12.0

when years are requested.

---

CORRECT:

SUM(months) / 12.0

---

INVALID:

ROUND(
SUM(months),
2
)

when years are requested.

---

CORRECT:

ROUND(
SUM(months) / 12.0,
2
)

---

INVALID:

master_df m
JOIN work_experience_df w
ON ...

followed directly by:

SUM(duration_calculation)

when duplicate master rows may multiply work rows.

---

CORRECT:

DISTINCT work_rows

plus:

EXISTS

for candidate verification.

============================================================
FINAL WORK EXPERIENCE RULES
===========================

When answering work-experience duration questions:

1. Use work_experience_df.

2. Make work_experience_df the primary table.

3. Create UNIQUE work-experience rows.

4. Normalize the duration separator.

5. Extract start_part.

6. Extract end_part.

7. Parse start month/year from start_part.

8. Detect Present from end_part.

9. If Present, use current month/year.

10. Otherwise parse end month/year from end_part.

11. Use LOWER() for month matching.

12. Convert months with CASE.

13. Calculate each duration in MONTHS.

14. Verify candidate membership using EXISTS.

15. Do not allow master_df duplicates to multiply durations.

16. SUM unique months.

17. Divide total months by 12.0.

18. ROUND the final years value to 2 decimals.

19. Use w.job_title for work roles.

20. Use w.company_name for company-specific questions.

21. Use m.candidate_name for candidate identification.

22. Do not use m.requisition_title as the candidate's
    previous work role.

23. Do not use strftime() directly on text month/year values.

24. Do not cast w.duration directly to INTEGER.

25. Do not cast month names directly to INTEGER.

26. Do not ignore Present rows.

27. Do not silently accept negative durations.

28. Do not silently accept obviously malformed duration
    values.

29. Do not count the same unique work-experience record more
    than once.

30. Do not return months while labeling them as years.

============================================================
MANDATORY FINAL SQL CHECK
=========================

Before returning SQL, verify:

* candidate is correct
* work_experience_df is used
* work rows are unique
* candidate relationship is correct
* screening_header_id is correct
* requisition_header_id is correct
* candidate_line_id is correct
* EXISTS is used when appropriate
* no duplicate master rows can multiply work rows
* duration separator is normalized
* start_part is extracted
* end_part is extracted
* start month is parsed
* start year is parsed
* Present is detected correctly
* completed end month is parsed
* completed end year is parsed
* LOWER() is used for month matching
* CASE is used for month-number conversion
* completed months are calculated correctly
* Present months are calculated correctly
* Present rows are included
* duration_months is non-negative
* multiple rows are summed in months
* total months are divided by 12.0
* final value is rounded to 2 decimals
* final value is YEARS
* w.job_title is used for role-specific experience
* w.company_name is used for company-specific experience
* m.requisition_title is not used as previous employment role
* strftime() is not applied directly to text durations
* duration is not directly CAST to INTEGER
* month names are not directly CAST to INTEGER
* fixed-position parsing is not blindly applied to original
  w.duration
* duplicate-prone JOIN aggregation is avoided
* suspiciously large results are not automatically approved

============================================================
EVALUATOR RULE
==============

The evaluator MUST evaluate both:

1. SQL correctness
2. Numerical result correctness

A query is NOT correct merely because it executes.

The evaluator MUST reject a work-experience query when:

* duration parsing is incorrect
* Present is lost
* month parsing fails
* duplicate work rows are counted
* candidate matching is incorrect
* total months are not converted to years
* the result is clearly abnormal because of parsing or
  duplication
* a malformed duration produces an unrealistic total

For example:

1825.33 years

MUST NOT be automatically approved.

The evaluator must inspect the matching work-experience
records and verify the calculated duration_months values.

============================================================
FINAL CONCEPTUAL FLOW
=====================

For TOTAL work experience:

work_experience_df
↓
SELECT DISTINCT work rows
↓
normalize duration separator
↓
extract start_part
↓
extract end_part
↓
parse start month/year
↓
detect Present
↓
parse end month/year OR use current month/year
↓
calculate duration_months
↓
EXISTS candidate verification
↓
SUM unique duration_months
↓
divide by 12.0
↓
ROUND(..., 2)
↓
TOTAL YEARS

============================================================
FINAL INSTRUCTION
=================

Generate SQL that answers the user's actual work-experience
question using only the available HR data.

Do not invent:

* candidate names
* job titles
* companies
* requisition numbers
* durations
* tables
* columns

For work-experience duration questions, the SQL must calculate
the result from the candidate's actual UNIQUE work-experience
records.

Correctness of the numerical result is required.

A query that executes successfully but returns an incorrect
work-experience total is INVALID.

============================================================



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

13. 13. Candidate application status must use
    candidate_public_state_name.

    The user's wording does not have to exactly match the
    value stored in candidate_public_state_name.

    Evaluate the meaning of the user's requested application
    status and map it to the correct canonical Oracle HCM state.

    --------------------------------------------------------
    CANONICAL CANDIDATE APPLICATION STATES
    --------------------------------------------------------

    1. "1st Level Interview Scheduled"

    Possible user wording:
    - first level interview scheduled
    - 1st level interview is scheduled
    - first interview scheduled

    Canonical state:
    "1st Level Interview Scheduled"


    2. "1st level Interview to be Scheduled"

    Possible user wording:
    - first level interview to be scheduled
    - first level interview needs to be scheduled
    - waiting for first level interview
    - first interview needs scheduling

    Canonical state:
    "1st level Interview to be Scheduled"


    3. "Selected for Offer"

    Possible user wording:
    - selected for offer
    - candidate selected for offer
    - selected to receive offer
    - offer selected

    Canonical state:
    "Selected for Offer"


    4. "Rejected by Employer"

    Possible user wording:
    - rejected by employer
    - employer rejected
    - candidate was rejected
    - rejected candidate

    Canonical state:
    "Rejected by Employer"


    5. "2nd Level Interview to be Scheduled"

    Possible user wording:
    - 2nd level interview to be scheduled
    - second level interview to be scheduled
    - second level interview needs to be scheduled
    - waiting for second level interview
    - candidates waiting for second interview

    Canonical state:
    "2nd Level Interview to be Scheduled"


    6. "2nd Level Interview Scheduled"

    Possible user wording:
    - 2nd level interview scheduled
    - second level interview scheduled
    - second interview is scheduled

    Canonical state:
    "2nd Level Interview Scheduled"


    7. "2nd Level Interview Completed"

    Possible user wording:
    - 2nd level interview completed
    - second level interview completed
    - second interview completed
    - finished second level interview
    - completed second interview

    Canonical state:
    "2nd Level Interview Completed"


    8. "To be Created"

    Possible user wording:
    - to be created
    - candidate record to be created
    - waiting to be created

    Canonical state:
    "To be Created"


    9. "Screening Completed"

    Possible user wording:
    - screening completed
    - completed screening
    - screening is complete
    - finished screening
    - screening finished
    - done with screening

    Canonical state:
    "Screening Completed"


    --------------------------------------------------------
    IMPORTANT EVALUATION RULE
    --------------------------------------------------------

    Do not reject SQL merely because the user's wording
    differs from the canonical state name.

    Example:

    User question:
    "give me candidates whose completed screening
     in Oracle HCM Functional Specialist"

    Correct interpretation:

    candidate_public_state_name =
    "Screening Completed"

    Therefore this SQL is CORRECT:

    LOWER(m.candidate_public_state_name) =
    LOWER('Screening Completed')


    Another example:

    User question:
    "give me candidates whose 2nd level interview
     to be scheduled"

    Correct interpretation:

    candidate_public_state_name =
    "2nd Level Interview to be Scheduled"

    Therefore this SQL is CORRECT:

    LOWER(m.candidate_public_state_name) =
    LOWER('2nd Level Interview to be Scheduled')


    --------------------------------------------------------
    IMPORTANT
    --------------------------------------------------------

    The evaluator must evaluate the USER'S INTENDED MEANING,
    not simply compare the generated SQL text with the exact
    words used by the user.

    If the generated SQL uses the correct canonical state
    corresponding to the user's intended meaning,
    approve the SQL.

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
