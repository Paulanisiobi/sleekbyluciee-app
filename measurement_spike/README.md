SleekByLuciee — Measurement Feasibility Spike

Purpose
- Small prototype service to validate measurement capture flow.
- Accepts images and returns mocked measurements + confidence for POC.

Files
- `app.py` — minimal Flask API with `/measure` endpoint.
- `model_stub.py` — placeholder estimator returning fixed measurements.
- `requirements.txt` — Python dependencies.

Run locally (Windows using bash.exe)

1. Create a Python virtual environment and install deps:

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows bash - use this path in bash.exe
pip install -r requirements.txt
```

2. Start the API:

```bash
python app.py
```

3. Test with `curl` (replace `front.jpg` and `side.jpg` with your files):

```bash
curl -X POST -F "images=@front.jpg" -F "images=@side.jpg" http://127.0.0.1:5000/measure
```

Response example:

```json
{
  "measurements": {"bust_cm": 88.0, "waist_cm": 70.0, "hips_cm": 96.0, "inseam_cm": 74.0},
  "confidence": 0.82,
  "notes": "Stubbed estimates — replace with CV model or SDK"
}
```

Next steps for the spike
- Replace `model_stub.estimate_measurements` with a CV prototype (OpenCV + pretrained pose-estimation) or integrate a 3rd-party body-measurement SDK.
- Capture camera guidance frames (overlay) in the frontend to improve capture consistency.
- Add measurement confidence thresholds and manual fallback flow for low-confidence results.

MediaPipe integration
- The spike now includes an experimental MediaPipe-based estimator. To use it, call the `/measure` endpoint with `engine=mediapipe` and optionally include `height` (cm):

```bash
curl -X POST -F "images=@front.jpg" -F "engine=mediapipe" -F "height=165" http://127.0.0.1:5000/measure
```

The endpoint returns a JSON object containing the measurements for the first image that produced landmarks, a confidence score, and the source filename. If no landmarks are detected, it will return per-image errors.

Notes
- This is an early POC. The heuristics are intentionally simple and intended to validate end-to-end capture and ingestion. For production, add capture guidance, calibration, merging of front+side estimates, and secure storage.

Notes
- This POC intentionally returns mocked values to allow the rest of the pipeline (upload, storage, webhooks) to be exercised quickly.

Additional queue / worker notes
- Postgres-backed jobs: the spike now uses a persisted `measurement_jobs` table in Postgres and a polling worker `pg_worker.py`.
- `/measure`: when called with `async=true`, the API inserts a job row into Postgres and returns `job_id` (HTTP 202).
- `/measure/status/<job_id>`: status endpoint (also supports `?wait=seconds` for long-polling). The worker updates `status`, `result`, and `last_error` fields.
- Webhook callbacks: if you include `webhook_url` in the job payload (form field), the worker attempts to POST the result JSON to that URL after completion.
- `e2e_smoke_test.py`: small script that enqueues a stub job and asserts the worker completes it — useful for CI validation.

Docker Compose (quick local setup)
1. From the project root you can start Postgres, the Flask app and the worker with Docker Compose (detached):

```bash
# from the repository root
docker compose up --build -d db app worker
```

2. Run the E2E smoke test as a one-off container and remove it when finished (recommended for CI):

```bash
docker compose run --rm e2e
```

3. The Flask API will be available at `http://localhost:5000` while services are running. When finished, tear down the environment:

```bash
docker compose down --volumes --remove-orphans
```

Alternative: run the smoke test from the host (after starting compose) by pointing `DATABASE_URL` at the container DB:

```bash
# set DATABASE_URL and run the smoke test (after docker compose up -d)
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sleekdb
python e2e_smoke_test.py
```

The `docker-compose.yml` mounts `measurement_spike/uploads` so images are preserved on the host.

Metrics & Sentry
- To expose worker metrics, set `METRICS_PORT` (default 8000). Prometheus metrics are available at `http://<worker-host>:<METRICS_PORT>/`.
- To enable Sentry error reporting, set `SENTRY_DSN` environment variable for the worker (and app, if desired).

Admin UI (dead-letter inspection)
- A tiny admin web UI is now available at `/admin` on the Flask app. It lists dead-lettered jobs and lets you inspect and requeue them.
- The admin UI is protected by an `ADMIN_TOKEN` environment variable. If `ADMIN_TOKEN` is set, provide it with the `X-Admin-Token` header or `?token=` query parameter when accessing the UI. If `ADMIN_TOKEN` is not set, the UI is open (not recommended in production).
- Example (with Docker Compose):

```bash
# set a short-lived admin token and start services
ADMIN_TOKEN=secret123 docker compose up --build -d db app worker

# open the admin UI at http://localhost:5000/admin (browser) and supply the token
```

CLI deprecation note
- The repository previously included a `dead_letter_admin.py` CLI. The CLI still exists for scripted usage, but the web UI offers a convenient replacement. Use whichever fits your workflow.

Prometheus & local scraping
- Prometheus is included as a compose service and reads `prometheus/prometheus.yml`. When running via `docker compose up`, Prometheus will be available at `http://localhost:9090`.
- The worker metrics endpoint is exposed on host port `8000` (mapped to the container). CI also queries `http://localhost:8000/` to validate that jobs were processed during the E2E run.

