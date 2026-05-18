# Distributed Deployment Notes

This repository now separates local app behavior from production-oriented orchestration boundaries.

## Services

- `backend`: FastAPI orchestration API, REST/SSE/websocket endpoints.
- `frontend`: Streamlit UI, unchanged runtime entrypoint.
- `postgres`: Postgres with pgvector image for future workflow and vector persistence.
- `redis`: Pub/sub and queue coordination foundation for websocket fanout and workers.

## Runtime Boundaries

- `backend.config` centralizes environment-driven settings.
- `backend.storage` owns workflow, event, telemetry, and agent metadata repositories.
- `backend.memory` defines vector-memory and embedding interfaces, with pgvector scaffolding.
- `backend.messaging` defines Redis-ready event propagation.
- `backend.workers` defines Redis-ready distributed worker queue abstractions.
- `backend.runtime` remains the orchestration execution boundary.

## Local Production Stack

```bash
cp .env.example .env
docker compose up --build
```

Backend: `http://localhost:8000`  
Streamlit: `http://localhost:8501`

## Future Worker Paths

The current runtime uses FastAPI background tasks. The queue abstractions are intentionally compatible with later Celery/RQ adoption for:

- workflow execution workers
- autonomous monitoring jobs
- investigation workers
- executive briefing generation

Redis pub/sub is scaffolded for websocket scaling across multiple backend instances.
