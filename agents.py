# ============================================================
# agents.py
# ============================================================

AGENTS = {

    # ========================================================
    # 1. JOB REQUISITION HR
    # ========================================================

    "JOBREQUISITIONHR": {

        "description": (
            "Gets all job requisitions and the number of "
            "applications for each requisition."
        ),

        "parameters": {

            "UserInput": "string",

            "AgentName": "string",

            "triggerType": "string"
        },

        "user_parameters": [
            "UserInput"
        ],

        "system_parameters": [
            "AgentName",
            "triggerType"
        ],

        "body": {
            "parameters": {

                "UserInput":
                    "4",

                "AgentName":
                    "job_requisition_hr",

                "triggerType":
                    "REST"
            }
        }
    },


    # ========================================================
    # 2. CANDIDATE REQUISITION
    # ========================================================

    "CANDIDATEREQUISTION": {

        "description": (
            "Gets all candidates and job applications "
            "for a particular requisition."
        ),

        "parameters": {

            "AgentName": "string",

            "requisitionheaderid": "string",

            "RequisitionNumber": "string",

            "triggerType": "string"
        },

        "user_parameters": [
            "RequisitionNumber"
        ],

        "system_parameters": [
            "AgentName",
            "requisitionheaderid",
            "triggerType"
        ],

        "body": {
            "parameters": {

                "AgentName":
                    "candidate_requisition",

                "requisitionheaderid":
                    "11",

                "RequisitionNumber":
                    None,

                "triggerType":
                    "REST"
            }
        }
    },


    # ========================================================
    # 3. SCREENING AGENT
    # ========================================================

    "SCREENINGAGENT": {

        "description": (
            "Screens candidates for a particular "
            "job requisition."
        ),

        "parameters": {

            "AgentName": "string",

            "CandidateLineID": "integer",

            "RequisitionHeaderID": "string",

            "JobApplicationId": "array",

            "triggerType": "string"
        },

        "user_parameters": [
            "JobApplicationId"
        ],

        "system_parameters": [
            "AgentName",
            "CandidateLineID",
            "RequisitionHeaderID",
            "triggerType"
        ],

        "body": {
            "parameters": {

                "AgentName":
                    "SCREENINGAGENT",

                "CandidateLineID":
                    2,

                "RequisitionHeaderID":
                    "11",

                "JobApplicationId":
                    None,

                "triggerType":
                    "REST"
            }
        }
    },


    # ========================================================
    # 4. SCHEDULING TEAMS MEETING
    # ========================================================

    "SCHEDULING_TEAMS_MEETING": {

        "description": (
            "Schedules a candidate interview using "
            "Microsoft Teams. The agent creates the "
            "interview meeting and handles the scheduling "
            "workflow."
        ),

        "parameters": {

            "candidateName": "string",

            "email": "string",

            "startDateTime": "string",

            "endDateTime": "string",

            "subject": "string",

            "interviewers": "array",

            "interviewersEmail": "array",

            "JobApplicationId": "integer",

            "triggerType": "string"
        },

        "user_parameters": [

            "candidateName",

            "email",

            "startDateTime",

            "endDateTime",

            "subject",

            "interviewers",

            "interviewersEmail",

            "JobApplicationId"
        ],

        "system_parameters": [

            "triggerType"
        ],

        "body": {
            "parameters": {

                "candidateName":
                    None,

                "email":
                    None,

                "startDateTime":
                    None,

                "endDateTime":
                    None,

                "subject":
                    "Java Interview",

                "interviewers":
                    [],

                "interviewersEmail":
                    [],

                "JobApplicationId":
                    None,

                "triggerType":
                    "REST"
            }
        }
    },


    # ========================================================
    # 5. INTERVIEWER DATA
    # ========================================================

    "INTERVIEWERDATA": {

        "description": (
            "Gets interviewer information including "
            "interviewer names and interviewer email "
            "addresses."
        ),

        "parameters": {

            "RequisitionNumber": "string",

            "triggerType": "string"
        },

        "user_parameters": [
            "RequisitionNumber"
        ],

        "system_parameters": [
            "triggerType"
        ],

        "body": {
            "parameters": {

                "RequisitionNumber":
                    None,

                "triggerType":
                    "REST"
            }
        }
    },


    # ========================================================
    # 6. INTERVIEWER AVAILABILITY
    # ========================================================

    # ========================================================
# 6. INTERVIEWER AVAILABILITY
# ========================================================

"INTERVIEWER_AVAILABILITY": {

    "description": (
        "Checks the common availability of one or "
        "more interviewers for a requested date "
        "and meeting duration."
    ),

    "parameters": {

        "interviewer_emails": "array",

        "date": "string",

        "meeting_duration_minutes": "integer",

        "triggerType": "string"
    },

    "user_parameters": [

        "date",
        "meeting_duration_minutes"
    ],

    "system_parameters": [

        "interviewer_emails",

        "triggerType"
    ],

    "body": {
        "parameters": {

            "interviewer_emails":
                [],

            "date":
                None,

            "meeting_duration_minutes":
                30,

            "triggerType":
                "REST"
        }
    }
},


    # ========================================================
    # 7. EMAIL HR
    # ========================================================

    "EMAIL_HR": {

        "description": (
            "Creates email content based on the email "
            "type, tone, recipient email, subject, "
            "body and note."
        ),

        "parameters": {

            "AgentName":
                "string",

            "Type":
                "string",

            "Tone":
                "string",

            "Email":
                "string",

            "subject":
                "string",

            "body":
                "string",

            "Note":
                "string",

            "triggerType":
                "string"
        },

        "user_parameters": [

            "Type",

            "Tone",

            "Email",

            "subject",

            "body",

            "Note"
        ],

        "system_parameters": [

            "AgentName",

            "triggerType"
        ],

        "body": {
            "parameters": {

                "AgentName":
                    "hr_email",

                "Type":
                    "professional",

                "Tone":
                    None,

                "Email":
                    None,

                "subject":
                    None,

                "body":
                    None,

                "Note":
                    " ",

                "triggerType":
                    "REST"
            }
        }
    },

    # ============================================================
# LINKEDIN JOB DESCRIPTION
# ============================================================

    "LINKEDIN_JOB_DESC": {

        "description": (
            "Posts a provided job description to LinkedIn."),

        "parameters": {
            "jobDescription": "string"
            },

        "user_parameters": [
            "jobDescription"
            ],

        "system_parameters": [],

        "body": {

            "parameters": {
                "jobDescription":
                None,
                "triggerType":
                "REST"
            }
        }
    },


    # ========================================================
    # 8. HR EMAIL SEND
    # ========================================================

    "HREMAILSEND": {

        "description": (
            "Sends an email to a candidate using the "
            "provided recipient email address, subject, "
            "and email body."
        ),

        "parameters": {

            "AgentName":
                "string",

            "body":
                "string",

            "subject":
                "string",

            "email":
                "string",

            "triggerType":
                "string"
        },

        "user_parameters": [

            "Email",

            "subject",

            "body"
        ],

        "system_parameters": [

            "AgentName",

            "triggerType"
        ],

        "body": {

            "parameters": {

                "header_id":
                    11,

                "AgentName":
                    "hr_email_send",

                "cc":
                    "[]",

                "body":
                    None,

                "subject":
                    None,

                "email":
                    None,

                "triggerType":
                    "REST"
            }
        }
    }
}