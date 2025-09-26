# System Design Assessor API

A Python FastAPI application that provides AI-powered assessment for system design solutions.

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Create `.env` file with your OpenAI API key: `OPENAI_API_KEY=your_key_here`
3. Run: `uvicorn app.main:app --reload` or `docker-compose up --build`

## API Usage

- **POST** `/api/v1/assess` - Assess a system design
- **GET** `/health` - Health check  
- **GET** `/docs` - API documentation

## Testing

Run tests: `pytest`
