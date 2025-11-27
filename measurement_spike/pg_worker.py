"""Postgres-backed worker for measurement jobs with webhook callbacks.

Polling worker that locks queued jobs and processes them. If the job payload
contains `engine: 'stub'` it uses the stub estimator; otherwise it calls
`measurement_service.estimate_from_images`.

If the job payload includes `webhook_url`, the worker POSTs the result JSON
to that URL after completing the job.
"""
import os
import time
import json
import traceback
import requests
from measurement_service import estimate_from_images
from model_stub import estimate_measurements as stub_estimate
from db import get_conn, ensure_table, fetch_and_lock_job, update_job_completed, update_job_failed


def process_job(job):
    job_id = job['id']
    payload = job.get('payload') or {}
    try:
        engine = payload.get('engine', 'stub')
        images = payload.get('images', [])
        height = payload.get('height_cm') or payload.get('height')
        if engine == 'stub':
            result = stub_estimate(images)
        else:
            result = estimate_from_images(images, height_cm=height)

        update_job_completed(job_id, result)

        webhook = (payload or {}).get('webhook_url')
        if webhook:
            try:
                requests.post(webhook, json={'job_id': job_id, 'status': 'completed', 'result': result}, timeout=5)
            except Exception:
                # swallow webhook errors — job already marked completed
                pass
        return True
    except Exception as e:
        tb = traceback.format_exc()
        update_job_failed(job_id, tb)
        webhook = (payload or {}).get('webhook_url')
        if webhook:
            try:
                requests.post(webhook, json={'job_id': job_id, 'status': 'failed', 'error': str(e)}, timeout=5)
            except Exception:
                pass
        return False


def loop():
    ensure_table()
    print('Starting Postgres job worker...')
    while True:
        try:
            job = fetch_and_lock_job()
            if not job:
                time.sleep(0.8)
                continue
            print('Processing job', job['id'])
            process_job(job)
        except Exception as e:
            print('Worker loop exception', e)
            time.sleep(1)


if __name__ == '__main__':
    loop()
