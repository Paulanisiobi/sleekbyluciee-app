"""Container-friendly E2E test.

This script expects the Flask app to be reachable at http://app:5000 (Docker Compose
service name). It posts a stub async job and polls until completion.
"""
import os
import time
import sys
import requests

API_URL = os.environ.get('E2E_API_URL', 'http://app:5000')


def wait_for_app(timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(API_URL + '/')
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def enqueue_job():
    r = requests.post(API_URL + '/measure', data={'engine': 'stub', 'async': 'true'})
    if r.status_code not in (200, 202):
        print('Failed to enqueue job, status', r.status_code, r.text)
        return None
    return r.json().get('job_id')


def poll_status(job_id, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(API_URL + f'/measure/status/{job_id}')
        if r.status_code == 200:
            j = r.json()
            print('Status:', j.get('status'))
            if j.get('status') == 'completed' and j.get('result'):
                print('Result:', j.get('result'))
                return True
            if j.get('status') == 'failed':
                print('Job failed:', j.get('error') or j.get('last_error'))
                return False
        time.sleep(0.5)
    print('Timed out waiting for job completion')
    return False


def main():
    print('Waiting for app to become ready...')
    if not wait_for_app(60):
        print('App did not become ready in time')
        return 2

    job_id = enqueue_job()
    if not job_id:
        return 3
    print('Enqueued job', job_id)

    ok = poll_status(job_id, timeout=60)
    return 0 if ok else 4


if __name__ == '__main__':
    sys.exit(main())
