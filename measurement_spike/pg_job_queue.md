Postgres-backed Job Queue (optional)

This file describes a lightweight replacement for RQ that uses a persisted `jobs` table in Postgres and a simple polling worker.

Schema (example):

CREATE TABLE measurement_jobs (
  id UUID PRIMARY KEY,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  status TEXT NOT NULL DEFAULT 'queued',
  payload JSONB,
  result JSONB,
  attempts INT DEFAULT 0,
  last_error TEXT
);

Simple worker behavior:
- Poll for rows WHERE status = 'queued' ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED
- Mark status = 'processing'
- Execute processing (call measurement_service.estimate_from_images)
- Write result JSON and status = 'completed' (or 'failed' on exception)

Benefits:
- No Redis dependency
- Job history persisted and queryable

Drawbacks:
- Slightly less efficient than Redis pub/sub for high throughput

See `pg_worker.py` for a minimal implementation.
