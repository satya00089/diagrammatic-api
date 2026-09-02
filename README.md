# System Design Assessor API

A Python FastAPI application that provides AI-powered assessment for system design solutions.

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Create `.env` file with your OpenAI API key: `OPENAI_API_KEY=your_key_here`
3. Run: `uvicorn app.main:app --reload` or `docker-compose up --build`

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
