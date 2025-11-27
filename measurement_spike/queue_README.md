Postgres-backed Queueing (pg_worker)

Overview
- The `/measure` endpoint supports `engine` and an optional `async=true` form field. When `async=true`, the request inserts a job row into a Postgres `measurement_jobs` table and returns HTTP 202 with a `job_id`.
- Use the `pg_worker.py` script to run a polling worker that will process queued jobs and call the estimator.

Setup
1. Ensure Postgres is running and set `DATABASE_URL` in your environment:

```bash
export DATABASE_URL=postgresql://user:pass@localhost/dbname
cd measurement_spike
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

2. Start the Flask API (app.py):

```bash
python app.py
```

3. Start the Postgres worker (in a separate terminal):

```bash
python pg_worker.py
```

Usage
- Enqueue an async job:

```bash
curl -X POST -F "engine=stub" -F "async=true" http://127.0.0.1:5000/measure
```

- The API returns `job_id`. Poll the status endpoint:

```bash
curl http://127.0.0.1:5000/measure/status/<job_id>?wait=10
```

Notes
- The worker updates `measurement_jobs.status`, `result`, and `last_error` fields. If you include `webhook_url` in the job payload, the worker will attempt to POST the job result to that URL.
- This approach avoids a Redis dependency and keeps job history persisted in Postgres.
