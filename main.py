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
# EXTRACT CANDIDATE NAME FROM USER QUESTION
# ============================================================

def extract_candidate_name(
    question: str
):
    """Extract a specific candidate name when the question contains one."""

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

    response = llm_intent.invoke(prompt)
    content = response.content.strip()

    if content.startswith("```"):
        content = content.replace("```json", "")
        content = content.replace("```", "")
        content = content.strip()

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        return None

    return result.get("candidate_name")


# ============================================================
# 6. Get HR Data
# ============================================================

# ============================================================
# 7. Get HR Data
# ============================================================

def get_hr_data():

    # Get Master API DataFrame
    # Get Work Experience API DataFrame
    master_df, work_experience_df = create_hr_tables()

    return (
        master_df,
        work_experience_df
    )


# ============================================================
# 11. HR RECRUITMENT DATABASE SCHEMA
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
- Example: "44".

requisition_id
- System requisition identifier.
- Data type: TEXT.

requisition_title
- Job requisition title.
- Data type: TEXT.
- Example: "Site Engineer (Trainee)".

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
- One application represents one candidate application.

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
- MOST IMPORTANT relationship key between the two tables.

screening_candidate_line_id
- Screening candidate line identifier.
- Data type: TEXT.

screening_requisition_header_id
- Screening requisition header identifier.
- Data type: TEXT.

screening_current_role
- Candidate's current or recent role.
- Data type: TEXT.

screening_education
- Candidate's education.
- Data type: TEXT.

screening_certifications
- Candidate's certifications.
- Data type: TEXT.

screening_skills

- Candidate's skills extracted during screening.
- Data type: TEXT.
- Contains the candidate's technical skills, soft skills,
  languages, tools, and other relevant skills.
- Example:
  "AutoCAD, ConstructionSiteExecutionDiploma,
  TechnicalOfficeDiploma, Microsoftoffice, MicrosoftExcel,
  ProblemSolving, LeadershipSkills, WorkunderPressure,
  QuickLearning, GoodPresentationSkills, GoodTimeManagement,
  TeamWorkingSkills, Arabic, English".

screening_ai_summary
- AI-generated candidate screening summary.
- Data type: TEXT.

screening_ai_score
- AI-generated candidate screening score.
- Data type: NUMBER/TEXT depending on API response.
- Higher score generally represents a stronger candidate match.

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
- Recruiter's/work email associated with screening.
- Data type: TEXT.


============================================================
TABLE 2: work_experience_df
============================================================

PURPOSE:
Contains individual work-experience records for candidates.

GRANULARITY:
ONE ROW represents ONE work-experience record.

A single candidate can therefore have MULTIPLE rows.

Example:

Candidate 114:

Row 1:
Company = Sekmo Company
Job Title = Civil Site Engineer
Duration = Jan 2026 – Present

Row 2:
Company = The Arab Contractors
Job Title = Civil Engineering Intern
Duration = Jul 2024 – Aug 2024


------------------------------------------------------------
WORK EXPERIENCE COLUMNS
------------------------------------------------------------

line_id
- Unique work-experience record identifier.

screening_header_id
- Screening header identifier.
- MOST IMPORTANT relationship key.

requisition_header_id
- Requisition header identifier.

candidate_line_id
- Candidate line identifier.

job_application_id
- Candidate application identifier.

candidate_person_id
- Candidate person identifier.
- This field may be NULL in the work-experience API.

company_name
- Company where the candidate worked.

job_title
- Job title/role associated with the work experience.

duration
- Duration of the work experience.
- Example:
  "Jan 2026 – Present"


============================================================
RELATIONSHIP BETWEEN THE TWO TABLES
============================================================

The two tables are related through THREE common fields:

1. screening_header_id
2. requisition_header_id
3. candidate_line_id

IMPORTANT:
screening_header_id is the MOST IMPORTANT matching key.

When information from both tables is required, use ALL THREE
keys to establish the relationship.

JOIN CONDITION:

m.screening_header_id = w.screening_header_id

AND

m.requisition_header_id = w.requisition_header_id

AND

m.candidate_line_id = w.candidate_line_id

where:

m = master_df
w = work_experience_df


DO NOT join the tables using candidate_name when the three
relationship keys are available.

DO NOT join only using candidate_line_id.

DO NOT join only using requisition_header_id.

DO NOT join only using screening_header_id when all three
keys are available.


============================================================
WHAT CAN BE ANSWERED FROM master_df
============================================================

Use master_df for questions about:

- Requisition number
- Requisition title
- Requisition status
- Requisition phase
- Requisition applications
- Job description
- Candidate name
- Candidate application
- Candidate application status
- Candidate education
- Candidate certifications
- Candidate current role
- Candidate recruiter
- Candidate email
- Candidate screening
- AI screening score
- AI screening summary


============================================================
WHAT CAN BE ANSWERED FROM
work_experience_df
============================================================

Use work_experience_df for questions about:

- Previous companies
- Previous employers
- Work history
- Previous job titles
- Work experience
- Experience duration
- Employment history


============================================================
WHEN TO USE BOTH TABLES
============================================================

Use BOTH tables when the user's question requires information
from candidate screening/master data AND work experience.

Examples:

1. "What is Mamdouh Salem's AI score and where did he work?"

2. "Who is the highest scoring candidate for Site Engineer
   and which companies did they work for?"

3. "Show candidates with an AI score above 70 and their
   previous companies."

4. "Which candidate for requisition 44 has the highest score
   and what is their work experience?"


For these questions:

1. Find the required candidate/master information from
   master_df.

2. Join work_experience_df using:

   screening_header_id
   requisition_header_id
   candidate_line_id

3. Return ALL matching work-experience records when the
   question asks for complete experience.


============================================================
WORK EXPERIENCE RULES
============================================================

IMPORTANT:

Work experience is NOT a column in master_df.

DO NOT generate:

SELECT WorkExperience
FROM master_df

DO NOT assume that these are columns in master_df:

CompanyName
JobTitle
Duration

They belong to work_experience_df as:

company_name
job_title
duration


A candidate may have multiple work-experience records.

For example:

Mamdouh Salem:

Record 1:
SekmoCompany
CivilSiteEngineer
Jan2026–Present

Record 2:
The Arab Contractors
Civil engineering intern
Jul2024–Aug2024

If the user asks for complete work experience, BOTH records
must be returned.


============================================================
SUPPORTED QUESTION TYPES
============================================================

The system can answer:

1. Requisition information
2. Candidate information
3. Candidate application status
4. Number of candidates/applications
5. Candidate education
6. Candidate certifications
7. Candidate work experience
8. Candidate skills when available in the master data
9. Candidate AI screening scores
10. Candidate ranking by AI score
11. Candidate comparison
12. Candidates belonging to a requisition
13. Candidates belonging to a job title
14. Candidate screening status
15. Recruiter-related information
16. Requisition-candidate relationships
17. Previous companies
18. Previous job titles
19. Experience duration
20. Combined screening and work-experience questions


============================================================
EXAMPLE 1
============================================================

QUESTION:

"Show all candidates for requisition 44."

TABLE:

master_df

USE:

candidate_name
candidate_job_application_id
candidate_public_state_name
requisition_number

LOGIC:

Filter using requisition_number = "44".


============================================================
EXAMPLE 2
============================================================

QUESTION:

"Who has the highest AI score for requisition 44?"

TABLE:

master_df

USE:

requisition_number
candidate_name
screening_ai_score

LOGIC:

Filter requisition_number = "44".

Order:

screening_ai_score DESC

Return the highest-scoring candidate.


============================================================
EXAMPLE 3
============================================================

QUESTION:

"How many candidates are under consideration?"

TABLE:

master_df

USE:

candidate_public_state_name
candidate_job_application_id

LOGIC:

Filter:

candidate_public_state_name = "Under Consideration"

Then:

COUNT(DISTINCT candidate_job_application_id)


============================================================
EXAMPLE 4
============================================================

QUESTION:

"What is the education of Mamdouh Salem?"

TABLE:

master_df

USE:

candidate_name
screening_education

LOGIC:

Find the candidate using candidate_name.

Return screening_education.


============================================================
EXAMPLE 5
============================================================

QUESTION:

"Who has the highest AI score?"

TABLE:

master_df

USE:

candidate_name
screening_ai_score

LOGIC:

ORDER BY screening_ai_score DESC

LIMIT 1.


============================================================
EXAMPLE 6
============================================================

QUESTION:

"Where did Mamdouh Salem work?"

TABLE:

work_experience_df

USE:

company_name

The query should return ALL matching company records.


============================================================
EXAMPLE 7
============================================================

QUESTION:

"What jobs did Mamdouh Salem have?"

TABLE:

work_experience_df

USE:

company_name
job_title
duration

Return ALL matching work-experience records.


============================================================
EXAMPLE 8
============================================================

QUESTION:

"Show Mamdouh Salem's complete work experience."

TABLE:

work_experience_df

USE:

company_name
job_title
duration

Do NOT use LIMIT 1.

Return every matching work-experience record.


============================================================
EXAMPLE 9
============================================================

QUESTION:

"What is Mamdouh Salem's AI score and where did he work?"

TABLES:

master_df
work_experience_df

USE:

Master:

candidate_name
screening_ai_score
screening_header_id
requisition_header_id
candidate_line_id

Work experience:

company_name
job_title
duration

JOIN:

m.screening_header_id = w.screening_header_id

AND

m.requisition_header_id = w.requisition_header_id

AND

m.candidate_line_id = w.candidate_line_id


============================================================
EXAMPLE 10
============================================================

QUESTION:

"Which company did the highest scoring candidate for
requisition 44 work for?"

TABLES:

master_df
work_experience_df

LOGIC:

1. Filter master_df using requisition_number = "44".

2. Find the candidate with the highest screening_ai_score.

3. Join that candidate to work_experience_df using:

   screening_header_id
   requisition_header_id
   candidate_line_id

4. Return company_name, job_title, and duration.


============================================================
COUNTING RULES
============================================================

For unique candidate applications:

COUNT(DISTINCT candidate_job_application_id)

Do NOT simply use COUNT(*) when the question asks for the
number of unique candidate applications.


The requisition_applications value represents the number of
applications associated with a requisition.

This value may be repeated on multiple candidate rows.

Therefore:

DO NOT SUM(requisition_applications).


For work-experience records:

COUNT(*)

means number of work-experience records.

It does NOT necessarily mean number of candidates.


============================================================
SQL SAFETY RULES
============================================================

1. Use ONLY these tables:

   master_df
   work_experience_df


2. Use ONLY columns explicitly defined in this schema.


3. Never invent columns.


4. Never invent tables.


5. Never invent candidate information.


6. Never invent work-experience information.


7. Never use SELECT *.


8. Always explicitly specify required columns.


9. Use SQLite-compatible SQL.


10. Only SELECT statements are allowed.


11. Never generate:

    INSERT
    UPDATE
    DELETE
    DROP
    ALTER
    CREATE


12. For flexible text searches use:

    LOWER(column) LIKE LOWER('%value%')


13. For exact matching use:

    LOWER(column) = LOWER('value')


14. Use LIMIT 50 for normal multi-row queries.


15. Do not use LIMIT for scalar aggregate queries.


16. Use LIMIT 1 for questions asking for a single highest
    or lowest candidate.


17. For highest AI score:

    ORDER BY screening_ai_score DESC


18. For lowest AI score:

    ORDER BY screening_ai_score ASC


19. If a question requires work experience, use
    work_experience_df.


20. If a question requires both master and work experience,
    use a JOIN.


21. When using both tables, use the three relationship keys.


============================================================
NO HALLUCINATION RULE
============================================================

The SQL generator MUST NOT create columns such as:

WorkExperience
CompanyName
JobTitle
Duration
YearsOfExperience
Salary
Location
PhoneNumber

unless those columns actually exist in the specified table.

The correct work-experience columns are:

work_experience_df.company_name
work_experience_df.job_title
work_experience_df.duration


============================================================
CANNOT ANSWER RULE
============================================================

If the question cannot be answered using the available
tables and columns, return:

CANNOT_ANSWER_FROM_SCHEMA

Do NOT invent a table.

Do NOT invent a column.

Do NOT invent data.


============================================================
FINAL SQL OUTPUT RULE
============================================================

Return SQL ONLY.

Do not return:

- Explanation
- Markdown
- Code fences
- Comments
- Natural-language answer
- JSON

The result summarizer will convert the SQL result into
natural-language business language.

"""

# ============================================================
# 12. CLEAN SQL
# ============================================================

def clean_sql(text: str) -> str:

    
    text = text.strip()

    # Case 1:
    # LLM returned SQL inside ```sql ... ```
    if "```sql" in text:
        return text.split("```sql")[1].split("```")[0].strip()

    # Case 2:
    # LLM returned SQL inside ``` ... ```
    if "```" in text:
        return text.split("```")[1].split("```")[0].strip()

    # Case 3:
    # LLM returned plain SQL without markdown
    return text.strip()
# ============================================================
# 13. EXTRACT JSON
# ============================================================

def extract_json(text: str) -> dict:

    # Remove unnecessary spaces from the beginning
    # and end of the response
    text = text.strip()

    # --------------------------------------------------------
    # CASE 1:
    # Try to directly convert the complete response
    # into a Python dictionary
    # --------------------------------------------------------

    try:
        return json.loads(text)

    except Exception:
        # If direct JSON parsing fails,
        # continue to the next method
        pass

    # --------------------------------------------------------
    # CASE 2:
    # Search for a JSON object inside the response
    # --------------------------------------------------------

    match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL
    )

    # If a JSON object was found
    if match:

        # Get only the JSON part
        json_text = match.group()

        # Convert JSON string into Python dictionary
        return json.loads(json_text)

    # --------------------------------------------------------
    # CASE 3:
    # No valid JSON was found
    # --------------------------------------------------------

    raise ValueError(
        "Could not parse JSON from evaluator response"
    )

# ============================================================
# 15. INTENT ROUTER
# ============================================================


def intent_router(state: QueryState):

    print("ENTER Intent Router")

    prompt = f"""
You are an intelligent routing agent for an HR Recruitment
Natural Language to SQL system.

Your task is to determine whether the user's question can
be answered using the available HR recruitment data.

Understand the BUSINESS MEANING of the user's question.
Do not depend only on exact column names.

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

2. UNKNOWN_ROUTE

Choose UNKNOWN_ROUTE only when the question cannot be
answered using the available HR recruitment data.

Examples:

"What is the weather today?"

"What is the company's annual revenue?"

"Send an email to the recruiter."

"Schedule an interview."

IMPORTANT HR BUSINESS TERMINOLOGY:

- job opening -> requisition
- position -> requisition/job
- applicant -> candidate
- candidate -> CandidateName
- application -> candidate application
- screening score -> AIScore
- AI score -> AIScore
- application status -> PublicStateName
- job title -> Title
- current job -> CurrentRole
- education -> Education
- experience -> WorkExperience
- skills -> SkillsAndCertifications
- certifications -> Certifications
- AI summary -> AISummary
- requisition status -> StateName
- requisition phase -> PhaseName

IMPORTANT JOIN KEY INFORMATION:

The HR system contains TWO related data sources:

1. HR Master data
2. Work Experience data

The most important relationship key is:

screening_header_id

The complete relationship hierarchy is:

screening_header_id
    -> requisition_header_id
        -> candidate_line_id

When matching candidate screening information with work
experience information, screening_header_id must be treated
as the PRIMARY and MOST IMPORTANT matching key.

Do not assume candidate_line_id alone is sufficient.

Do not assume requisition_header_id alone is sufficient.

The relationship should be interpreted in this priority:

1. screening_header_id
2. requisition_header_id
3. candidate_line_id

The available HR data may contain candidate information,
screening information, requisition information, and
candidate work experience.

If the user's question can be answered using these HR
recruitment sources, select HYBRID_ROUTE.

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

Do not return Markdown.
Do not return ```json.
Do not return any text outside the JSON object.
"""

    try:

        response = llm_intent.invoke(prompt)

        print("RAW INTENT RESPONSE:")
        print(response.content)

        data = extract_json(response.content)

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

        print("Route:", route)
        print("Reason:", reason)

        print("EXIT Intent Router")

        return {
            "route": route,
            "route_reason": reason
        }

    except Exception as e:

        import traceback

        traceback.print_exc()

        print(
            "Intent Router failed:",
            str(e)
        )

        return {
            "route": "UNKNOWN_ROUTE",
            "route_reason": f"Intent routing failed: {str(e)}"
        }



def generate_query_hybrid(state: QueryState):

    print("ENTER generate_query_hybrid")

    
    template = """
You are an expert SQLite SQL Generator for a Human Resources
Recruitment Question Answering system.

Your job is to convert the user's natural-language HR recruitment
question into ONE valid SQLite SQL query.

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

ONLY these two tables are available:

1. master_df
2. work_experience_df

Never invent another table.

============================================================
MASTER_DF BUSINESS MEANING
============================================================

master_df contains the main HR recruitment and candidate screening
information.

Important columns include:

- candidate_name
- candidate_job_application_id
- requisition_number
- requisition_title
- requisition_phase_name
- candidate_public_state_name
- screening_ai_score
- screening_ai_summary
- screening_current_role
- screening_skills
- screening_skills
- screening_certifications
- screening_header_id
- requisition_header_id
- candidate_line_id

Use ONLY columns that actually exist in the provided schema.

============================================================
WORK_EXPERIENCE_DF BUSINESS MEANING
============================================================

work_experience_df contains candidate previous work experience.

Important columns include:

- screening_header_id
- requisition_header_id
- candidate_line_id
- company_name
- job_title
- duration

Use ONLY columns that actually exist in the provided schema.

============================================================
CRITICAL BUSINESS MEANING RULES
============================================================

You MUST understand the difference between requisition-level
information and candidate-level information.

------------------------------------------------------------
1. OPEN REQUISITIONS
------------------------------------------------------------

If the user asks:

- open requisitions
- open requisition
- open jobs
- open job requisitions
- currently open requisitions
- which requisitions are open
- give me open requisitions
- show open requisitions

the question is about the REQUISITION.

Therefore you MUST use:

    master_df.requisition_phase_name

and filter using:

    LOWER(m.requisition_phase_name) = LOWER('Open')

DO NOT use:

    candidate_public_state_name

for an "open requisitions" question.

Example:

User:
"Can you give open requisitions?"

Correct SQL:

SELECT DISTINCT
    m.requisition_number,
    m.requisition_title,
    m.requisition_phase_name
FROM master_df m
WHERE LOWER(m.requisition_phase_name) = LOWER('Open')
LIMIT 50;

------------------------------------------------------------
2. NUMBER OF OPEN REQUISITIONS
------------------------------------------------------------

If the user asks:

"How many open requisitions?"

use:

SELECT
    COUNT(DISTINCT m.requisition_number) AS requisition_count
FROM master_df m
WHERE LOWER(m.requisition_phase_name) = LOWER('Open');

Do NOT use LIMIT for aggregate queries.

------------------------------------------------------------
3. CANDIDATE SCREENING STATUS
------------------------------------------------------------

If the user asks about:

- candidates completed screening
- candidates who completed screening
- candidates in screening
- candidate application status
- candidate state
- screening status of candidates

then use:

    candidate_public_state_name

Do NOT use:

    requisition_phase_name

because requisition_phase_name describes the requisition,
not the candidate.

------------------------------------------------------------
4. CANDIDATE NAME
------------------------------------------------------------

If the user asks:

- candidate name
- candidate
- who is the candidate
- candidates

use:

    candidate_name

------------------------------------------------------------
5. AI SCORE
------------------------------------------------------------

If the user asks:

- AI score
- AI screening score
- screening score
- candidate score

use:

    screening_ai_score

------------------------------------------------------------
6. REQUISITION NUMBER
------------------------------------------------------------

If the user asks:

- requisition number
- requisition no
- requisition
- job requisition number

use:

    requisition_number

============================================================
REQUISITION QUESTIONS VS CANDIDATE QUESTIONS
============================================================

Always determine whether the question is about a REQUISITION
or a CANDIDATE before selecting the column.

REQUISITION:

"open requisitions"

    -> requisition_phase_name

CANDIDATE:

"candidates who completed screening"

    -> candidate_public_state_name

These two columns MUST NOT be confused.

============================================================
CANDIDATE NAME MATCHING
============================================================

When the user gives a candidate name, use:

    LOWER(m.candidate_name) = LOWER('Full Name')

for an exact full-name match.

If the user gives only part of a candidate's name, for example:

"give me the AI score of Salem"

DO NOT assume which candidate the user means if multiple
candidates could match.

Instead, search using:

    LOWER(m.candidate_name) LIKE LOWER('%Salem%')

If the query can identify exactly one candidate, return that
candidate's information.

If multiple candidates match, return the matching candidate names
so the HR assistant can ask the user to clarify the full name.

For example:

SELECT DISTINCT
    m.candidate_name
FROM master_df m
WHERE LOWER(m.candidate_name) LIKE LOWER('%Salem%')
LIMIT 50;

IMPORTANT:

Never silently choose "Mamdouh Salem" merely because it is one
possible match for "Salem".

The assistant should ask the user to provide the full candidate
name when multiple candidates match.

============================================================
TEXT SEARCH RULE
============================================================

For flexible text searches use:

LOWER(column) LIKE LOWER('%value%')

For exact matching use:

LOWER(column) = LOWER('value')

============================================================
TABLE SELECTION
============================================================

Use master_df when the question is about:

- requisition information
- requisition number
- requisition title
- requisition phase
- requisition status
- open requisitions
- candidate name
- candidate application
- candidate application status
- candidate screening status
- candidate education
- candidate certifications
- candidate current role
- candidate recruiter
- AI screening score
- AI screening summary

Use work_experience_df when the question is about:

- previous companies
- previous employers
- work history
- previous job titles
- work experience
- experience duration
============================================================
SKILLS QUESTION RULE - VERY IMPORTANT
============================================================
When the user asks about a candidate's:

- skills
- technical skills
- professional skills
- soft skills
- abilities
- competencies
- capabilities
- candidate skills

ALWAYS use:

master_df.screening_skills

For skills-related questions, ALWAYS retrieve the
screening_skills column from master_df.

DO NOT use:

master_df.screening_certifications

unless the user explicitly asks for certifications.

DO NOT use:

master_df.screening_current_role

unless the user explicitly asks for the candidate's current role.

DO NOT use:

work_experience_df

for a skills question unless the user explicitly asks about
work experience.

IMPORTANT:

screening_skills is a valid column in master_df.

Therefore, NEVER return:

CANNOT_ANSWER_FROM_SCHEMA

when the user asks for candidate skills.

Example:

User:
"Can you give me the skills of Mamdouh Salem?"

Correct SQL:

SELECT
    m.candidate_name,
    m.screening_skills
FROM master_df m
WHERE LOWER(m.candidate_name) = LOWER('Mamdouh Salem');

Another example:

User:
"What are Mamdouh Salem's technical skills?"

Correct SQL:

SELECT
    m.candidate_name,
    m.screening_skills
FROM master_df m
WHERE LOWER(m.candidate_name) = LOWER('Mamdouh Salem');

Another example:

User:
"Give me the skills of candidates in requisition 44."

Correct SQL:

SELECT
    m.candidate_name,
    m.screening_skills
FROM master_df m
WHERE LOWER(m.requisition_number) = LOWER('44')
LIMIT 50;

The generated SQL MUST use:

m.screening_skills

for all skills-related questions.


============================================================
WHEN BOTH TABLES ARE REQUIRED
============================================================

Use BOTH tables when the question requires information from
candidate/master data AND work experience.

Example:

"What is Mamdouh Salem's AI score and where did he work?"

============================================================
JOIN RULE
============================================================

When joining master_df and work_experience_df, ALWAYS use ALL
THREE relationship keys:

m.screening_header_id = w.screening_header_id

AND

m.requisition_header_id = w.requisition_header_id

AND

m.candidate_line_id = w.candidate_line_id

where:

m = master_df
w = work_experience_df

IMPORTANT:

Do NOT join using candidate_name when the relationship keys
are available.

Do NOT join using only candidate_line_id.

Do NOT join using only requisition_header_id.

============================================================
SQL RULES
============================================================

1. Return SQL only.

2. Use SQLite-compatible SQL.

3. Use SELECT statements only.

4. Only use:

   master_df
   work_experience_df

5. Never use SELECT *.

6. Always explicitly specify the required columns.

7. Never invent columns.

8. Never invent tables.

9. Use only columns defined in the supplied schema.

10. For normal multi-row results use:

    LIMIT 50

11. Do NOT use LIMIT for scalar aggregate queries.

12. For unique candidate/application counts use:

    COUNT(DISTINCT candidate_job_application_id)

13. Do NOT use:

    SUM(requisition_applications)

14. For highest AI score:

    ORDER BY screening_ai_score DESC

15. For lowest AI score:

    ORDER BY screening_ai_score ASC

16. If the user asks for all work experience, return all matching
    work-experience records.

============================================================
IMPORTANT DATA VALUE RULE
============================================================

Do NOT invent database values.

The schema and available data determine the actual values.

For requisition phase questions, use:

    requisition_phase_name

For example, if the actual data contains:

    requisition_phase_name = "Open"

then the SQL must use:

    LOWER(m.requisition_phase_name) = LOWER('Open')

For candidate screening status, use the actual values represented
by candidate_public_state_name.

Do not automatically change:

"Screening Completed"

into:

"Completed Screening"

or vice versa.

Use the actual value represented in the supplied schema/data.

============================================================
EXAMPLES
============================================================

Question:

"Can you give open requisitions?"

Correct SQL:

SELECT DISTINCT
    m.requisition_number,
    m.requisition_title,
    m.requisition_phase_name
FROM master_df m
WHERE LOWER(m.requisition_phase_name) = LOWER('Open')
LIMIT 50;

------------------------------------------------------------

Question:

"How many open requisitions?"

Correct SQL:

SELECT
    COUNT(DISTINCT m.requisition_number) AS requisition_count
FROM master_df m
WHERE LOWER(m.requisition_phase_name) = LOWER('Open');

------------------------------------------------------------

Question:

"Who is the highest scoring candidate for requisition 44?"

Correct SQL:

SELECT
    m.candidate_name,
    m.requisition_number,
    m.screening_ai_score
FROM master_df m
WHERE LOWER(m.requisition_number) = LOWER('44')
ORDER BY m.screening_ai_score DESC
LIMIT 1;

------------------------------------------------------------

Question:

"Give me the candidates who completed screening in requisition 44."

Correct SQL pattern:

SELECT
    m.candidate_name
FROM master_df m
WHERE LOWER(m.requisition_number) = LOWER('44')
AND LOWER(m.candidate_public_state_name) =
    LOWER('<ACTUAL SCREENING COMPLETED VALUE>')
LIMIT 50;

IMPORTANT:

Use the actual candidate_public_state_name value from the
available data/schema. Do not invent a different status value.

------------------------------------------------------------

Question:

"How many candidates completed screening in requisition 44?"

Correct SQL pattern:

SELECT
    COUNT(DISTINCT m.candidate_job_application_id) AS candidate_count
FROM master_df m
WHERE LOWER(m.requisition_number) = LOWER('44')
AND LOWER(m.candidate_public_state_name) =
    LOWER('<ACTUAL SCREENING COMPLETED VALUE>');

------------------------------------------------------------

Question:

"Where did Mamdouh Salem work?"

Correct SQL:

SELECT
    m.candidate_name,
    w.company_name,
    w.job_title,
    w.duration
FROM master_df m
JOIN work_experience_df w
ON m.screening_header_id = w.screening_header_id
AND m.requisition_header_id = w.requisition_header_id
AND m.candidate_line_id = w.candidate_line_id
WHERE LOWER(m.candidate_name) = LOWER('Mamdouh Salem')
LIMIT 50;

------------------------------------------------------------

Question:

"What is Mamdouh Salem's AI score and where did he work?"

Correct SQL:

SELECT
    m.candidate_name,
    m.screening_ai_score,
    w.company_name,
    w.job_title,
    w.duration
FROM master_df m
JOIN work_experience_df w
ON m.screening_header_id = w.screening_header_id
AND m.requisition_header_id = w.requisition_header_id
AND m.candidate_line_id = w.candidate_line_id
WHERE LOWER(m.candidate_name) = LOWER('Mamdouh Salem')
LIMIT 50;

============================================================
FINAL INSTRUCTIONS
============================================================

Before generating SQL, perform these steps internally:

1. Understand exactly what the user is asking.

2. Determine whether the question is about:
   - requisition
   - candidate
   - work experience
   - both

3. Select the correct table.

4. Select the correct column based on business meaning.

5. Verify that every column exists in the supplied schema.

6. Use actual database values when filtering.

7. If the user provides only a partial candidate name,
   do not assume the full candidate.

8. Generate one valid SQLite SELECT query.

9. Return SQL only.

Do not return explanations.

Do not return markdown.

Do not return natural-language answers.

Do not return JSON.

Return only the SQL query.
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

    sql = clean_sql(response.content)

    print("Generated SQL:")
    print(sql)

    print("EXIT generate_query_hybrid")

    return {
        "query": sql,
        "query_history": [sql]
    }


def evaluate_query_hybrid(state: QueryState):

    print("ENTER evaluate_query_hybrid")

    template = """
You are an expert SQL Quality Assurance Agent for an HR Recruitment
Question Answering system.

Your task is to evaluate whether the generated SQL query correctly
answers the user's HR recruitment question and follows the available
HR database schema and SQL rules.

The system contains TWO HR tables:

1. master_df
2. work_experience_df

The tables are related using these three keys:

- screening_header_id
- requisition_header_id
- candidate_line_id

IMPORTANT JOIN RULE:

screening_header_id is the MOST IMPORTANT matching key.

When work experience information is required, the preferred
relationship is:

master_df.screening_header_id =
work_experience_df.screening_header_id

AND

master_df.requisition_header_id =
work_experience_df.requisition_header_id

AND

master_df.candidate_line_id =
work_experience_df.candidate_line_id

Do not join the tables using only candidate name.

--------------------------------------------------
USER QUESTION
--------------------------------------------------

{question}

--------------------------------------------------
GENERATED SQL
--------------------------------------------------

{query}

--------------------------------------------------
HR DATABASE SCHEMA
--------------------------------------------------

{hr_database_schema}

--------------------------------------------------
TABLE 1: master_df
--------------------------------------------------

This table contains:

- requisition_header_id
- requisition_number
- requisition_id
- requisition_title
- requisition_state_name
- requisition_phase_name
- requisition_applications
- requisition_jd_title
- requisition_jd_about
- requisition_jd_responsibilities
- requisition_creation_date

Candidate information:

- candidate_line_id
- candidate_job_application_id
- candidate_person_id
- candidate_name
- candidate_requisition_id
- candidate_requisition_number
- candidate_public_state_name
- candidate_recruiter_id
- candidate_phase_id
- candidate_state_id
- candidate_email

Screening information:

- screening_header_id
- screening_candidate_line_id
- screening_requisition_header_id
- screening_current_role
- screening_skills
- screening_skills
- screening_education
- screening_certifications
- screening_ai_summary
- screening_ai_score
- screening_person_id
- screening_person_number
- screening_recruiter
- screening_work_email

--------------------------------------------------
TABLE 2: work_experience_df
--------------------------------------------------

This table contains one row for each work-experience record.

Columns:

- line_id
- screening_header_id
- requisition_header_id
- candidate_line_id
- job_application_id
- candidate_person_id
- company_name
- job_title
- duration

A candidate can have MULTIPLE work-experience rows.

Example:

screening_header_id = 47
requisition_header_id = 61
candidate_line_id = 114

can have:

Company:
Sekmo Company

Job Title:
Civil Site Engineer

Duration:
Jan 2026–Present

AND another row:

Company:
The Arab Contractors

Job Title:
Civil engineering intern

Duration:
Jul 2024–Aug 2024

Therefore, do NOT assume that one candidate has only one
work-experience record.

--------------------------------------------------
EVALUATION RULES
--------------------------------------------------

1. TABLE VALIDATION

The SQL may use:

master_df

and/or

work_experience_df

depending on the user's question.

Do not use any other table.

--------------------------------------------------

2. MASTER TABLE QUESTIONS

For questions about:

- requisitions
- candidates
- candidate names
- application status
- requisition status
- requisition phase
- education
- certifications
- AI score
- AI summary
- recruiter
- job title
- job description

the SQL should normally use:

master_df

--------------------------------------------------

3. WORK EXPERIENCE QUESTIONS

If the user asks about:

- work experience
- companies worked for
- previous companies
- previous jobs
- job titles held
- duration of employment
- years of experience
- employment history

the SQL must use:

work_experience_df

--------------------------------------------------

4. QUESTIONS REQUIRING BOTH TABLES

If the question asks for candidate information together
with work experience, both tables should be used.

Example:

"Which companies did Mamdouh Salem work for?"

The SQL should join:

master_df

with:

work_experience_df

using:

screening_header_id
requisition_header_id
candidate_line_id

--------------------------------------------------

5. JOIN VALIDATION

When both tables are used, validate that the SQL joins them
using the three common keys:

screening_header_id
requisition_header_id
candidate_line_id

Preferred join:

FROM master_df m
JOIN work_experience_df w
  ON m.screening_header_id = w.screening_header_id
 AND m.requisition_header_id = w.requisition_header_id
 AND m.candidate_line_id = w.candidate_line_id

Do not approve a join based only on:

candidate_name

or:

candidate_person_id

or:

job_application_id

when the three common keys are available.

--------------------------------------------------

6. CANDIDATE SEARCH

If the user asks about a specific candidate,
the SQL should normally search:

m.candidate_name

Example:

LOWER(m.candidate_name) LIKE LOWER('%Mamdouh Salem%')

--------------------------------------------------

7. REQUISITION SEARCH

If the user asks about a requisition,
the SQL should use:

m.requisition_number

or:

m.requisition_id

--------------------------------------------------

8. JOB SEARCH

If the user asks about a job title,
the SQL should normally use:

m.requisition_title

Example:

LOWER(m.requisition_title)
LIKE LOWER('%Draughtsman%')

--------------------------------------------------

9. AI SCORE

If the user asks about AI screening scores,
the SQL should use:

m.screening_ai_score

Highest score:

ORDER BY m.screening_ai_score DESC

Lowest score:

ORDER BY m.screening_ai_score ASC

--------------------------------------------------

10. APPLICATION STATUS

For candidate application status use:

m.candidate_public_state_name

--------------------------------------------------

11. EDUCATION

For education questions use:

m.screening_education

--------------------------------------------------

12. CERTIFICATIONS

For certification questions use:

m.screening_certifications

--------------------------------------------------

13. CURRENT ROLE

For current role questions use:

m.screening_current_role

--------------------------------------------------

14. WORK EXPERIENCE

For work experience questions use:

w.company_name
w.job_title
w.duration

Do not expect these columns inside master_df.

--------------------------------------------------

15. YEARS OF EXPERIENCE

If the user asks:

"How many years of experience does Mamdouh Salem have?"

The query should retrieve the relevant work-experience records
from work_experience_df.

Do not invent a years_of_experience column unless it exists.

The result summarizer may calculate or explain experience based
on the returned duration values.

--------------------------------------------------

16. COMPANY QUESTIONS

If the user asks:

"Which companies did Mamdouh Salem work for?"

Return:

w.company_name

and, when useful:

w.job_title
w.duration

--------------------------------------------------

17. MULTIPLE WORK EXPERIENCE RECORDS

A candidate may have multiple work-experience records.

Do NOT use:

LIMIT 1

when the user asks for all previous companies or complete
work history.

Return all matching work-experience records.

--------------------------------------------------

18. SQL SYNTAX

The query must use valid SQLite-compatible SQL.

Only SELECT statements are allowed.

Do not allow:

- INSERT
- UPDATE
- DELETE
- DROP
- ALTER
- CREATE

--------------------------------------------------

19. SELECT *

Do not allow:

SELECT *

Always explicitly specify the required columns.

--------------------------------------------------

20. TEXT SEARCH

For flexible case-insensitive text searches use:

LOWER(column) LIKE LOWER('%value%')

For exact matching use:

LOWER(column) = LOWER('value')

--------------------------------------------------

21. LIMIT

Use LIMIT 50 for normal list queries.

Do not use LIMIT 1 when the user asks for all work-experience
records.

LIMIT 1 is appropriate only when the user explicitly asks
for one highest/lowest result.

For aggregate queries such as COUNT or AVG, LIMIT is not required.

--------------------------------------------------

22. COUNTING APPLICATIONS

For candidate/application counts, prefer:

COUNT(DISTINCT m.candidate_job_application_id)

Do not simply count rows if duplicate records may exist.

--------------------------------------------------

23. REQUISITION APPLICATIONS

The value:

m.requisition_applications

belongs to the requisition and may be repeated for multiple
candidate rows.

Do not SUM this value across candidate rows.

--------------------------------------------------

24. NO HALLUCINATION

Do not invent columns.

Do not use columns such as:

- salary
- location
- phone_number
- date_of_birth

unless they are explicitly available in the schema.

--------------------------------------------------

25. QUESTION INTENT

The SQL must actually answer the user's question.

Example:

Question:

"Who is the highest scoring candidate for Draughtsman?"

Correct logic:

- Filter the job title.
- Use screening_ai_score.
- Sort descending.
- Return the highest candidate.

Example:

Question:

"Which companies did Mamdouh Salem work for?"

Correct logic:

- Join master and work-experience tables.
- Identify Mamdouh Salem using the master table.
- Match using the three common keys.
- Return company_name.

--------------------------------------------------

26. DO NOT GENERATE NEW SQL

You are only evaluating the generated SQL.

Do not rewrite or generate a replacement SQL query.

--------------------------------------------------

27. JSON OUTPUT

Return strictly:

{{
    "evaluation": "approved",
    "feedback": "The SQL correctly answers the question and follows the HR database schema."
}}

OR:

{{
    "evaluation": "needs_improvement",
    "feedback": "Explain specifically what is wrong with the generated SQL."
}}

--------------------------------------------------

IMPORTANT

Evaluate the SQL based on:

1. User question
2. Master table schema
3. Work experience table schema
4. Required relationship between the tables
5. SQL correctness
6. Question intent

Only evaluate the generated SQL.

Return JSON only.
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
        hr_database_schema=HR_DATABASE_SCHEMA
    )

    response = query_evaluator.invoke(
        final_prompt_string
    )

    data = extract_json(response.content)

    evaluation = data.get(
        "evaluation",
        "needs_improvement"
    )

    feedback = data.get(
        "feedback",
        "No feedback provided"
    )

    if evaluation not in [
        "approved",
        "needs_improvement"
    ]:
        evaluation = "needs_improvement"

    print("Evaluation:", evaluation)
    print("Feedback:", feedback)

    print("EXIT evaluate_query_hybrid")

    return {
        "evaluation": evaluation,
        "feedback": feedback,
        "feedback_history": [feedback]
    }


def optimize_query_hybrid(state: QueryState):

    print("ENTER optimize_query_hybrid")

    template = """
You are an expert SQLite SQL Optimization Agent for an HR Recruitment
Question Answering system.

Your task is to correct and improve the generated SQL query based on:

1. The user's original HR recruitment question.
2. The current generated SQL query.
3. The SQL evaluator's feedback.
4. The HR recruitment database schema.

You must return ONLY the corrected SQL query.

--------------------------------------------------
USER QUESTION
--------------------------------------------------

{question}

--------------------------------------------------
CURRENT SQL QUERY
--------------------------------------------------

{query}

--------------------------------------------------
EVALUATOR FEEDBACK
--------------------------------------------------

{feedback}

--------------------------------------------------
HR DATABASE SCHEMA
--------------------------------------------------

{hr_database_schema}

--------------------------------------------------
AVAILABLE TABLES
--------------------------------------------------

There are TWO available SQLite tables.

1. master_df

This table contains:

- Requisition information
- Candidate information
- Candidate application information
- Screening information
- AI screening score
- Candidate education
- Candidate certifications
- Candidate summary

2. work_experience_df

This table contains candidate work experience.

Its important columns are:

- line_id
- screening_header_id
- requisition_header_id
- candidate_line_id
- job_application_id
- candidate_person_id
- company_name
- job_title
- duration

--------------------------------------------------
IMPORTANT RELATIONSHIP BETWEEN TABLES
--------------------------------------------------

The master table and work experience table are related using:

screening_header_id
requisition_header_id
candidate_line_id

IMPORTANT:

screening_header_id is the MOST IMPORTANT relationship key.

When joining the two tables, use all three keys:

master.screening_header_id =
work_experience.screening_header_id

AND

master.requisition_header_id =
work_experience.requisition_header_id

AND

master.candidate_line_id =
work_experience.candidate_line_id

Do NOT join the tables using only candidate_name.

Do NOT join the tables using only candidate_person_id.

Do NOT join the tables using only requisition_header_id.

--------------------------------------------------
TABLE USAGE RULES
--------------------------------------------------

Use master_df when the question is about:

- Requisition
- Job title
- Candidate
- Candidate application
- Application status
- Requisition status
- Requisition phase
- Education
- Certifications
- AI score
- AI summary
- Recruiter
- Candidate screening

Use work_experience_df when the question is about:

- Previous companies
- Work experience
- Previous job titles
- Employment duration
- Number of previous jobs
- Companies worked for
- Candidate employment history

--------------------------------------------------
WHEN BOTH TABLES ARE REQUIRED
--------------------------------------------------

Use a JOIN when the question requires both candidate/screening
information and work experience.

Example question:

"Which companies did Mamdouh Salem work for?"

Use:

master_df
+
work_experience_df

Example:

SELECT
    m.candidate_name,
    w.company_name,
    w.job_title,
    w.duration
FROM master_df m
JOIN work_experience_df w
    ON m.screening_header_id = w.screening_header_id
    AND m.requisition_header_id = w.requisition_header_id
    AND m.candidate_line_id = w.candidate_line_id
WHERE LOWER(m.candidate_name) LIKE LOWER('%Mamdouh Salem%')
LIMIT 50

--------------------------------------------------
WORK EXPERIENCE QUESTIONS
--------------------------------------------------

If the user asks:

"How many years of work experience does Mamdouh Salem have?"

Use the work experience table.

Do not assume that WorkExperience is a column in the master
table.

Use:

work_experience_df

and its:

duration

column.

If the duration values cannot safely be converted into a numeric
number of years using SQLite alone, return the available
employment records instead of inventing a total.

--------------------------------------------------
COMPANY QUESTIONS
--------------------------------------------------

If the user asks:

"Which companies did Mamdouh Salem work for?"

Use:

w.company_name

If the user asks:

"Where did Mamdouh Salem work?"

Return:

candidate_name
company_name
job_title
duration

--------------------------------------------------
JOB TITLE QUESTIONS
--------------------------------------------------

If the user asks:

"What positions did Mamdouh Salem hold?"

Use:

w.job_title

Do not use the master table's CurrentRole when the user is asking
for complete previous employment history.

--------------------------------------------------
DURATION QUESTIONS
--------------------------------------------------

If the user asks about employment duration, use:

w.duration

Do not invent a numeric duration if the API provides textual
duration values such as:

"Jan 2026 – Present"

"Jul 2024 – Aug 2024"

--------------------------------------------------
CANDIDATE SEARCH
--------------------------------------------------

If the question identifies a candidate, normally use:

m.candidate_name

Example:

LOWER(m.candidate_name)
LIKE
LOWER('%Mamdouh Salem%')

--------------------------------------------------
REQUISITION SEARCH
--------------------------------------------------

If the question identifies a requisition, use the appropriate
master table column:

m.requisition_number

or:

m.requisition_id

--------------------------------------------------
SCREENING SEARCH
--------------------------------------------------

For screening information use:

m.screening_ai_score
m.screening_ai_summary
m.screening_current_role
m.screening_skills
m.screening_education
m.screening_certifications

--------------------------------------------------
AI SCORE
--------------------------------------------------

For highest AI score:

ORDER BY CAST(m.screening_ai_score AS REAL) DESC

For lowest AI score:

ORDER BY CAST(m.screening_ai_score AS REAL) ASC

--------------------------------------------------
APPLICATION STATUS
--------------------------------------------------

Use:

m.candidate_public_state_name

--------------------------------------------------
REQUISITION STATUS
--------------------------------------------------

Use:

m.requisition_state_name

--------------------------------------------------
REQUISITION PHASE
--------------------------------------------------

Use:

m.requisition_phase_name

--------------------------------------------------
TEXT SEARCH
--------------------------------------------------

For case-insensitive searches use:

LOWER(column) LIKE LOWER('%value%')

--------------------------------------------------
EXACT MATCH
--------------------------------------------------

When the user provides an exact ID, use an exact comparison.

Example:

m.screening_header_id = 47

--------------------------------------------------
SQL RULES
--------------------------------------------------

1. Use only:

   master_df

   and/or

   work_experience_df

2. Only SELECT statements are allowed.

3. Never use:

   INSERT
   UPDATE
   DELETE
   DROP
   ALTER
   CREATE

4. Never use:

   SELECT *

5. Always explicitly specify columns.

6. Use SQLite-compatible SQL syntax.

7. Do not invent columns.

8. Do not invent candidate information.

9. Use table aliases:

   m = master_df
   w = work_experience_df

10. Use LIMIT 50 for normal multi-row results.

11. Use LIMIT 1 when the question asks for one highest,
    lowest, or single result.

12. Do not use LIMIT for scalar aggregate queries.

--------------------------------------------------
JOIN RULE
--------------------------------------------------

Whenever work experience is joined with master data, ALWAYS use:

ON m.screening_header_id = w.screening_header_id
AND m.requisition_header_id = w.requisition_header_id
AND m.candidate_line_id = w.candidate_line_id

screening_header_id has the highest importance.

--------------------------------------------------
NO HALLUCINATION
--------------------------------------------------

Do not invent columns such as:

Salary
Location
PhoneNumber
DateOfBirth

unless they exist in the provided schema.

Do not invent work experience.

Use only records available in:

work_experience_df

--------------------------------------------------
BUSINESS MEANING
--------------------------------------------------

Do not change the user's business meaning.

Do not blindly follow evaluator feedback if it conflicts with
the actual schema.

Verify the query against the provided schema before returning it.

--------------------------------------------------
OUTPUT
--------------------------------------------------

Return ONLY the corrected SQL query.

Do not return:

- Explanation
- Comments
- Markdown
- Code fences
- JSON
- Feedback

--------------------------------------------------
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
        hr_database_schema=HR_DATABASE_SCHEMA
    )

    response = query_optimizer.invoke(
        final_prompt_string
    )

    optimized_sql = clean_sql(
        response.content
    )

    print("Optimized SQL:")
    print(optimized_sql)

    print("EXIT optimize_query_hybrid")

    return {
        "query": optimized_sql,
        "iteration": state["iteration"] + 1,
        "query_history": [optimized_sql]
    }



def run_sql_node(state: QueryState):

    print("ENTER run_sql_node")

    sql_query = state["query"]

    try:

        # =====================================================
        # 1. Get MASTER DataFrame
        # =====================================================

        master_df = state[
            "master_df"
        ].copy()

        # =====================================================
        # 2. Get WORK EXPERIENCE DataFrame
        # =====================================================

        work_experience_df = state[
            "work_experience_df"
        ].copy()

        # =====================================================
        # 3. Convert ID columns to numeric where possible
        # =====================================================

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

        # =====================================================
        # 4. SQL Environment
        # =====================================================

        env = {
            "master_df": master_df,
            "work_experience_df": work_experience_df
        }

        # =====================================================
        # 5. Prevent invalid special value from reaching SQLite
        # =====================================================

        if sql_query.strip() == "CANNOT_ANSWER_FROM_SCHEMA":

            return {
                "sql_result": "CANNOT_ANSWER_FROM_SCHEMA"
            }

        # =====================================================
        # 6. Execute SQL
        # =====================================================

        print("SQL QUERY:")
        print(sql_query)

        result = sqldf(
            sql_query,
            env
        )

        print("SQL RESULT:")
        print(result)

        return {
            "sql_result": result.to_string(
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
            "sql_result": f"SQL Error: {e}"
        }


def handel_unknown_question(state: QueryState):

    print("ENTER handel_unknown_question")

    return {
        "result_summary": (
            "Sorry, this question cannot be answered "
            "using the available HR recruitment data."
        )
    }

def result_summary(state: QueryState):

    print("ENTER result_summary")

    template = """
You are an HR Recruitment Data Analysis Assistant.

Your job is to answer the user's question using ONLY the SQL
result provided below.

Do not invent any information.

Do not add information that is not present in the SQL result.

If the SQL result is empty, clearly state that no matching
records were found.

Give the answer in clear and simple business language.

--------------------------------------------------
USER QUESTION
--------------------------------------------------

{question}

--------------------------------------------------
SQL RESULT
--------------------------------------------------

{sql_result}

--------------------------------------------------
INSTRUCTIONS
--------------------------------------------------

1. Answer the user's question directly.

2. Use only the information available in the SQL result.

3. Do not mention SQL, database tables, or internal processing.

4. Do not invent candidate names, scores, skills, or other data.

5. If multiple candidates are returned, summarize them clearly.

6. If the user asks "who is the highest", identify the highest
   value from the SQL result.

7. If the user asks "who is the lowest", identify the lowest
   value from the SQL result.

8. If the SQL result is empty, say that no matching records
   were found.

9. Keep the response concise and easy to understand.

--------------------------------------------------
RETURN
--------------------------------------------------

Return only the final answer to the user.
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
        sql_result=state["sql_result"]
    )

    response = result_summarizer_llm.invoke(
        final_prompt_string
    )

    summary = response.content.strip()

    print("RESULT SUMMARY:")
    print(summary)

    print("EXIT result_summary")

    return {
        "result_summary": summary
    }


builder = StateGraph(QueryState)

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


def route_after_intent(state: QueryState):

    route = state.get(
        "route",
        "UNKNOWN_ROUTE"
    )

    print("ROUTE AFTER INTENT:", route)

    if route == "HYBRID_ROUTE":
        return "generate_query_hybrid"

    if route == "UNKNOWN_ROUTE":
        return "handel_unknown_question"

    # Safety fallback
    return "handel_unknown_question"





def route_after_hybrid_evaluation(state: QueryState):

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

    # ============================================================
    # 1. CANNOT ANSWER FROM SCHEMA
    # ============================================================

    if query == "CANNOT_ANSWER_FROM_SCHEMA":

        print(
            "Query cannot be answered from schema."
        )

        return "handel_unknown_question"

    # ============================================================
    # 2. APPROVED QUERY
    # ============================================================

    if evaluation == "approved":

        print(
            "Evaluation approved -> run_sql"
        )

        return "run_sql"

    # ============================================================
    # 3. MAX ITERATIONS
    # ============================================================

    if iteration >= max_iteration:

        print(
            "Maximum query optimization iterations reached."
        )

        return "handel_unknown_question"

    # ============================================================
    # 4. NEEDS IMPROVEMENT
    # ============================================================

    print(
        "Query needs improvement -> optimize_query_hybrid"
    )

    return "optimize_query_hybrid"




builder.add_edge(
    START,
    "intent_router"
)

builder.add_conditional_edges(
    "intent_router",
    route_after_intent,
    {
        "generate_query_hybrid": "generate_query_hybrid",
        "handel_unknown_question": "handel_unknown_question"
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
        "optimize_query_hybrid": "optimize_query_hybrid",
        "run_sql": "run_sql",
        "handel_unknown_question": "handel_unknown_question"
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

sql_app = builder.compile()
# ============================================================
# 7. Execute HR Q&A
# ============================================================


def executeSql(
    question: str,
    master_df: pd.DataFrame,
    work_experience_df: pd.DataFrame
):

    print("EXECUTE SQL START")

    # Create the initial state
    initial_state = {
    "question": question,

    "master_df": master_df,

    "work_experience_df": work_experience_df,

    "route_reason": "",
    "route": "UNKNOWN_ROUTE",

    "query": "",

    "evaluation": "needs_improvement",
    "feedback": "",

    "iteration": 0,
    "max_iteration": 5,

    "sql_result": "",
    "result_summary": "",

    "query_history": [],
    "feedback_history": []
}
    # Start the LangGraph workflow
    final_state = sql_app.invoke(
        initial_state
    )

    print("EXECUTE SQL END")

    # Return the final results
    return {
        "question": final_state["question"],
        "route": final_state["route"],
        "route_reason": final_state["route_reason"],
        "query": final_state["query"],
        "sql_result": final_state["sql_result"],
        "result_summary": final_state["result_summary"],
        "evaluation": final_state["evaluation"],
        "feedback": final_state["feedback"],
        "feedback_history": final_state["feedback_history"],
        "query_history": final_state["query_history"]
    }