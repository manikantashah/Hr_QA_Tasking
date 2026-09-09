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

def extract_title_name(
    question: str
):
    """
    Extract a job/requisition title from the user's question.

    This function does NOT resolve or correct the title.

    Example:

        "What is the state of the Site Engineer?"

        ->
        "Site Engineer"

    Example:

        "Tell me about Python SDE-1."

        ->
        "Python SDE-1"

    Example:

        "What is the state of requisition 44?"

        ->
        None
    """

    prompt = f"""

You are an HR Recruitment Question Analyzer.

Determine whether the user's question refers to a specific
job title / position / requisition title.

USER QUESTION:

{question}

Rules:

1. Extract the job title if a specific job title is mentioned.

2. Preserve the title exactly as the user typed it.

3. Do not correct spelling.

4. Do not invent a title.

5. If no specific job title is mentioned, return null.

6. Do not extract requisition numbers as titles.

7. Do not return a candidate name as a title.

8. The title may contain:
   - spaces
   - hyphens
   - numbers
   - parentheses
   - abbreviations

Examples:

Question:
"What is the state of the Site Engineer?"

Return:
{{"title_name": "Site Engineer"}}

Question:
"What is the state of Site Enginner?"

Return:
{{"title_name": "Site Enginner"}}

Question:
"Tell me about Python SDE-1."

Return:
{{"title_name": "Python SDE-1"}}

Question:
"What is the status of requisition 44?"

Return:
{{"title_name": null}}

Question:
"Show all candidates in requisition 44."

Return:
{{"title_name": null}}

Question:
"What is the AI score of Jithu Daniel?"

Return:
{{"title_name": null}}

Question:
"Who is the highest scoring candidate?"

Return:
{{"title_name": null}}

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

        title = result.get(
            "title_name"
        )

        if title is None:

            return None

        title = str(
            title
        ).strip()

        return (
            title
            if title
            else None
        )

    except Exception:

        return None


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

def intent_router(
    state: QueryState
):

    print(
        "ENTER Intent Router"
    )

    prompt = f"""

You are an intelligent routing agent for an HR Recruitment
Natural Language to SQL system.

Your task is to determine whether the user's question can
be answered using the available HR recruitment data.

AVAILABLE DATABASE SCHEMA:

{HR_DATABASE_SCHEMA}

ROUTING RULES:

1. HYBRID_ROUTE

Choose HYBRID_ROUTE if the user's question can be answered,
calculated, filtered, sorted, compared, or derived using
the available HR recruitment data.

Examples:

"Which candidate has the highest AI score?"

"Show candidates for requisition 42."

"How many candidates are there for requisition 42?"

"Which candidates completed screening?"

"Compare the AI scores of candidates."

"What is the education of Mamdouh Salem?"

"What is the work experience of candidate Mamdouh Salem?"

"Which candidates have AutoCAD experience?"

"What is the state of Site Engineer?"

2. UNKNOWN_ROUTE

Choose UNKNOWN_ROUTE only when the question cannot be
answered using the available HR recruitment data.

Examples:

"What is the weather today?"

"What is the company's annual revenue?"

"Send an email."

"Schedule an interview."

IMPORTANT BUSINESS TERMINOLOGY:

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

USER QUESTION:

{state["question"]}

Return ONLY valid JSON.

Required format:

{{
    "route": "HYBRID_ROUTE",
    "reason": "The question can be answered using the available HR recruitment data."
}}

OR

{{
    "route": "UNKNOWN_ROUTE",
    "reason": "The question cannot be answered using the available HR recruitment data."
}}

Do not return markdown.
"""

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
IMPORTANT JOB TITLE RULE
============================================================

When the user asks a question about a job title, return
the identifying requisition information together with the
requested property whenever appropriate.

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

        hr_database_schema=
            HR_DATABASE_SCHEMA
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
