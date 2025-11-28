from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
try:
    from measurement_spike.model_stub import estimate_measurements as stub_estimate
except Exception:
    try:
        from model_stub import estimate_measurements as stub_estimate
    except Exception:
        # fallback stub
        def stub_estimate(paths):
            return {'bust_cm': 88.0, 'waist_cm': 70.0, 'hips_cm': 96.0, 'inseam_cm': 74.0, 'confidence': 0.5}
import json
from uuid import uuid4
# lazy import db/measurement service to avoid heavy deps at import time
estimate_from_images = None
ensure_table = None
create_job = None
get_job = None
wait_for_completion = None
try:
    from db import ensure_table as _ensure_table, create_job as _create_job, get_job as _get_job, wait_for_completion as _wait_for_completion
    ensure_table = _ensure_table
    create_job = _create_job
    get_job = _get_job
    wait_for_completion = _wait_for_completion
except Exception:
    # DB not available at import time (tests may monkeypatch), defer import
    ensure_table = None
    create_job = None
    get_job = None
    wait_for_completion = None
import time
import os

# Initialize Sentry if provided
try:
    from sentry_sdk import init as sentry_init
    from sentry_sdk.integrations.flask import FlaskIntegration
except Exception:
    sentry_init = None

SENTRY_DSN = os.environ.get('SENTRY_DSN')
if SENTRY_DSN and sentry_init:
    sentry_init(dsn=SENTRY_DSN, integrations=[FlaskIntegration()], traces_sample_rate=0.1)

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

# Register admin blueprint (tiny web UI for dead-letter jobs).
# Prefer the packaged `measurement_spike.admin` (so tests can monkeypatch it),
# fall back to `admin_clean` if needed.
try:
    # Import the package-local admin module so tests can monkeypatch it later.
    from measurement_spike.admin import admin_bp as _admin_bp
    app.register_blueprint(_admin_bp, url_prefix='/admin')
except Exception:
    try:
        from measurement_spike.admin_clean import admin_bp as _admin_bp
        app.register_blueprint(_admin_bp, url_prefix='/admin')
    except Exception:
        pass

# Sync patched get_conn from `measurement_spike.admin` into `admin_clean` at
# request-time so tests that monkeypatch `measurement_spike.admin.get_conn`
# affect the handlers implemented in `admin_clean` (which reference their
# own module-level `get_conn`). This keeps tests simple without modifying
# `admin_clean` internals.
try:
    import measurement_spike.admin as _pkg_admin
    import measurement_spike.admin_clean as _admin_clean

    @app.before_request
    def _sync_admin_get_conn():
        if request.path.startswith('/admin'):
            # if test or runtime replaced get_conn on measurement_spike.admin,
            # propagate it into admin_clean so its handlers call the patched
            # connection factory.
            if hasattr(_pkg_admin, 'get_conn'):
                _admin_clean.get_conn = getattr(_pkg_admin, 'get_conn')
            # Also propagate ADMIN_TOKEN so tests that monkeypatch the token on
            # `measurement_spike.admin` affect the behavior of `admin_clean`.
            if hasattr(_pkg_admin, 'ADMIN_TOKEN'):
                _admin_clean.ADMIN_TOKEN = getattr(_pkg_admin, 'ADMIN_TOKEN')
except Exception:
    pass

@app.route('/', methods=['GET'])
def index():
    return "SleekByLuciee Measurement Spike API\nPOST images to /measure"

@app.route('/measure', methods=['POST'])
def measure():
    # Accepts multipart form with one or more image files under 'images'
    files = request.files.getlist('images')
    saved_paths = []
    for f in files:
        filename = secure_filename(f.filename)
        path = os.path.join(UPLOAD_DIR, filename)
        f.save(path)
        saved_paths.append(path)
    # engine param: 'stub' (default) or 'mediapipe'
    engine = request.form.get('engine', 'stub')
    height = request.form.get('height')
    height_val = float(height) if height else None

    async_flag = request.form.get('async', 'false').lower() == 'true'
    webhook_url = request.form.get('webhook_url')

    # ensure DB table exists when using Postgres-backed jobs
    try:
        ensure_table()
    except Exception:
        pass

    # If async requested, insert a Postgres job and return job_id
    if async_flag:
        payload = {
            'engine': engine,
            'images': saved_paths,
            'height_cm': height_val,
        }
        if webhook_url:
            payload['webhook_url'] = webhook_url
        job_id = create_job(payload)
        return jsonify({'status': 'enqueued', 'job_id': job_id}), 202

    # synchronous processing
    if engine == 'mediapipe':
        # lazy import to avoid importing cv2/mediapipe at module import time
        try:
            from measurement_service import estimate_from_images as _estimate
            result = _estimate(saved_paths, height_cm=height_val)
        except Exception:
            # fallback to stub if measurement_service not available
            result = stub_estimate(saved_paths)
    else:
        result = stub_estimate(saved_paths)

    # store synchronous result as a DB job record so clients can query it for consistency
    try:
        payload = {'engine': engine, 'images': saved_paths, 'height_cm': height_val}
        if create_job:
            job_id = create_job(payload, status='processing')
            # mark completed
            # reuse DB helper to update completed
            try:
                from db import update_job_completed
                update_job_completed(job_id, result)
            except Exception:
                pass
        else:
            job_id = None
    except Exception:
        job_id = None

    resp = {'status': 'completed', 'result': result}
    if job_id:
        resp['job_id'] = job_id
    return jsonify(resp)

    # Fallback to stub
    result = stub_estimate(saved_paths)
    response = {
        "measurements": {
            "bust_cm": result.get('bust_cm'),
            "waist_cm": result.get('waist_cm'),
            "hips_cm": result.get('hips_cm'),
            "inseam_cm": result.get('inseam_cm')
        },
        "confidence": result.get('confidence'),
        "notes": result.get('notes', '')
    }

    return jsonify(response)


@app.route('/measure/status/<job_id>', methods=['GET'])
def measure_status(job_id):
    """Return job status and result (if available)."""
    # Support long-polling: ?wait=seconds
    wait = int(request.args.get('wait', 0))
    start = time.time()
    while True:
        job = None
        try:
            job = get_job(job_id)
        except Exception:
            job = None
        if job:
            resp = {'job_id': job_id, 'status': job['status']}
            if job.get('result'):
                resp['result'] = job['result']
            if job.get('last_error'):
                resp['error'] = job['last_error']
            return jsonify(resp)
        if wait <= 0 or (time.time() - start) > wait:
            return jsonify({'job_id': job_id, 'status': 'unknown'}), 404
        time.sleep(0.5)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
