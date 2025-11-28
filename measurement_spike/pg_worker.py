"""Hardened Postgres worker with retries, backoff, metrics and Sentry.

Features:
- Increment attempt count in DB for each try
- Use exponential backoff for processing and webhook delivery (via `backoff`)
- Export Prometheus metrics via `prometheus_client` HTTP server
- Optional Sentry integration via `SENTRY_DSN` env var
"""
import os
import time
import json
import traceback
import requests
import logging
import backoff
from prometheus_client import start_http_server, Counter, Histogram
import sentry_sdk

from measurement_service import estimate_from_images
from model_stub import estimate_measurements as stub_estimate
from db import ensure_table, fetch_and_lock_job, update_job_completed, update_job_failed, increment_attempts, mark_job_dead

LOG = logging.getLogger('pg_worker')
logging.basicConfig(level=logging.INFO)

# Sentry
SENTRY_DSN = os.environ.get('SENTRY_DSN')
if SENTRY_DSN:
    sentry_sdk.init(SENTRY_DSN, traces_sample_rate=0.0)

# Prometheus metrics
METRICS_PORT = int(os.environ.get('METRICS_PORT', '8000'))
jobs_processed = Counter('sbl_jobs_processed_total', 'Total jobs processed')
jobs_failed = Counter('sbl_jobs_failed_total', 'Total jobs failed')
job_duration = Histogram('sbl_job_duration_seconds', 'Job processing duration seconds')
webhook_attempts = Counter('sbl_webhook_attempts_total', 'Webhook delivery attempts')

# worker settings
MAX_ATTEMPTS = int(os.environ.get('MAX_ATTEMPTS', '5'))
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET')


def _process(job):
    job_id = job['id']
    payload = job.get('payload') or {}
    engine = payload.get('engine', 'stub')
    images = payload.get('images', [])
    height = payload.get('height_cm') or payload.get('height')

    if engine == 'stub':
        return stub_estimate(images)
    return estimate_from_images(images, height_cm=height)


@backoff.on_exception(backoff.expo, Exception, max_tries=3)
def deliver_webhook(webhook_url, body):
    webhook_attempts.inc()
    headers = {}
    # attach HMAC signature if secret available
    try:
        import hmac, hashlib
        secret = WEBHOOK_SECRET or (body.get('webhook_secret') if isinstance(body, dict) else None)
        if secret:
            payload = json.dumps(body, separators=(',', ':'), sort_keys=True).encode('utf-8')
            sig = hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()
            headers['X-SBL-Signature'] = f"sha256={sig}"
    except Exception:
        LOG.exception('Failed to compute webhook signature')

    r = requests.post(webhook_url, json=body, headers=headers, timeout=5)
    r.raise_for_status()
    return r


def process_job_with_metrics(job):
    job_id = job['id']
    increment_attempts(job_id)
    start = time.time()
    try:
        # Check attempts -> dead-letter if exceeded
        attempts = job.get('attempts', 0)
        if attempts >= MAX_ATTEMPTS:
            LOG.warning('Job %s exceeded max attempts (%s), marking dead', job_id, attempts)
            mark_job_dead(job_id, reason=f"max_attempts={attempts}")
            return False

        result = _process(job)
        duration = time.time() - start
        job_duration.observe(duration)
        jobs_processed.inc()
        update_job_completed(job_id, result)

        webhook = (job.get('payload') or {}).get('webhook_url')
        if webhook:
            try:
                deliver_webhook(webhook, {'job_id': job_id, 'status': 'completed', 'result': result})
            except Exception:
                LOG.exception('Webhook delivery failed for job %s', job_id)
        return True
    except Exception as e:
        duration = time.time() - start
        job_duration.observe(duration)
        jobs_failed.inc()
        tb = traceback.format_exc()
        update_job_failed(job_id, tb)
        LOG.exception('Job %s failed', job_id)
        webhook = (job.get('payload') or {}).get('webhook_url')
        if webhook:
            try:
                deliver_webhook(webhook, {'job_id': job_id, 'status': 'failed', 'error': str(e)})
            except Exception:
                LOG.exception('Webhook failure after job failure for job %s', job_id)
        # if attempts now exceed MAX_ATTEMPTS, mark dead
        attempts_after = job.get('attempts', 0) + 1
        if attempts_after >= MAX_ATTEMPTS:
            try:
                mark_job_dead(job_id, reason=f"exhausted_attempts: {attempts_after}")
            except Exception:
                LOG.exception('Failed to mark job dead')
        # re-raise so backoff decorator on outer loop can handle delays if desired
        raise


def loop():
    ensure_table()
    # start metrics server
    try:
        start_http_server(METRICS_PORT)
        LOG.info('Prometheus metrics available on port %s', METRICS_PORT)
    except Exception:
        LOG.exception('Failed to start metrics server')

    LOG.info('Starting hardened Postgres job worker...')
    while True:
        try:
            job = fetch_and_lock_job()
            if not job:
                time.sleep(0.8)
                continue
            LOG.info('Processing job %s', job['id'])
            # wrap processing with backoff to handle transient errors
            try:
                backoff.on_exception(backoff.expo, Exception, max_tries=4)(process_job_with_metrics)(job)
            except Exception:
                LOG.exception('Final failure processing job %s', job['id'])
                # already recorded failure in DB by process_job_with_metrics
                time.sleep(1)
        except Exception as e:
            LOG.exception('Worker loop exception')
            time.sleep(1)


if __name__ == '__main__':
    loop()
