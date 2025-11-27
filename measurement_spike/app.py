from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
from model_stub import estimate_measurements as stub_estimate
from measurement_service import estimate_from_images
import json
from uuid import uuid4
from db import ensure_table, create_job, get_job, wait_for_completion
import time

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

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
        result = estimate_from_images(saved_paths, height_cm=height_val)
    else:
        result = stub_estimate(saved_paths)

    # store synchronous result as a DB job record so clients can query it for consistency
    try:
        payload = {'engine': engine, 'images': saved_paths, 'height_cm': height_val}
        job_id = create_job(payload, status='processing')
        # mark completed
        # reuse DB helper to update completed
        from db import update_job_completed
        update_job_completed(job_id, result)
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
