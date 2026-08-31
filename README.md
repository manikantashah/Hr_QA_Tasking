# HR_AGENT - Unified HR Q&A + HR Tasking

This project combines the two existing POCs into one application.

## Modes

### HR Q&A
Answers questions from the HR recruitment data using `handler.py`, `main.py`, and `hr_data.py`.

### HR Tasking
Performs operations through Oracle AI Agents using `task_router.py`, `orchestrator.py`, `agents.py`, `state.py`, and the related helper modules.

Supported tasking flows currently include:

- Screening
- Interviewer availability
- Interview scheduling
- Candidate email generation/sending
- LinkedIn job-description posting

## Entry point

Run:

```bash
uvicorn api:app --reload
```

Then use:

```text
POST http://127.0.0.1:8000/execute
```

Body:

```json
{
  "question": "What are the skills of Jithu Daniel?"
}
```

or:

```json
{
  "question": "Schedule an interview for Jithu Daniel in requisition 44 with Charles Wood Devadoss Wood Fread on August 28 from 2:30 PM to 3:00 PM."
}
```

## Configuration

Do not commit credentials. Copy `.env.example` to `.env` and create `config_cred.txt` from `config_cred.txt.example` with your own OCI configuration.

The tasking Oracle-agent client also requires the external `oci_generate_token.py` utility. Configure its location with `TOKEN_SCRIPT` or `INTERMASS_OCI_PATH` in `.env`.

## Conversation memory

The POC uses in-memory conversation state. The client does not need to send a conversation ID. Restarting the server clears the memory.
