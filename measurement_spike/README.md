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
