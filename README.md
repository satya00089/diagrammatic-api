# System Design Assessor API

A Python FastAPI application that provides AI-powered assessment for system design solutions.

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Create `.env` file with your OpenAI API key: `OPENAI_API_KEY=your_key_here`
3. Run: `uvicorn app.main:app --reload` or `docker-compose up --build`

### Optional Langfuse observability

The API uses Langfuse's OpenAI integration only when both
`LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are configured. Without those
values, or when `LANGFUSE_ENABLED=false`, the service uses the normal OpenAI
client and emits no Langfuse telemetry. Set `LANGFUSE_BASE_URL` to a
self-hosted Langfuse URL later without changing application code.

Tracing is named by product capability (`assessment.evaluate-design`,
`interview.generate-questions`, `interview.critique-answer`,
`recommendations.generate`, and `share.generate-article`) and includes only
safe request dimensions such as counts and feature tags. Prompt and completion
content is excluded by default; enable `LANGFUSE_CAPTURE_CONTENT=true` only
after reviewing the data policy for the environment. Langfuse failures never
fail an AI request.

## API Usage

- **POST** `/api/v1/assess` - Assess a system design
- **POST** `/api/v1/feedback` - Accept anonymous or authenticated product feedback
- **GET** `/health` - Health check  
- **GET** `/docs` - API documentation

### Product feedback storage

Set `DYNAMODB_FEEDBACK_TABLE` (defaults to `diagrammatic_feedback`) and create
the table before enabling feedback in a deployed environment:

```powershell
python scripts/create_feedback_table.py
```

The table uses an `id` partition key and a `status-createdAt-index` GSI for a
future internal triage queue. Feedback records intentionally contain only
whitelisted product context, not canvas contents.

## Testing

Run tests: `pytest`
