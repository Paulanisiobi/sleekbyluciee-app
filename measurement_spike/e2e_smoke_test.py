"""End-to-end smoke test for Postgres job flow.

Prereqs: set `DATABASE_URL` environment variable and install requirements.

This script will:
- ensure the jobs table exists
- start the Flask app in a subprocess
- POST to `/measure` with `engine=stub` and `async=true` to enqueue a job
- start the Postgres worker in a subprocess
- poll `/measure/status/<job_id>?wait=...` until completion and assert result
"""
import os
import time
import subprocess
import requests
from db import ensure_table

API_HOST = os.environ.get('API_HOST', 'http://127.0.0.1:5000')


def start_flask():
    # start app.py in a subprocess
    p = subprocess.Popen(['python', 'app.py'], cwd=os.path.dirname(__file__), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p


def start_worker():
    p = subprocess.Popen(['python', 'pg_worker.py'], cwd=os.path.dirname(__file__), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p


def wait_server():
    for _ in range(30):
        try:
            r = requests.get(API_HOST + '/')
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main():
    ensure_table()
    flask_p = start_flask()
    try:
        if not wait_server():
            print('Flask did not start in time')
            flask_p.kill(); return 1

        # enqueue job (engine=stub)
        r = requests.post(API_HOST + '/measure', data={'engine':'stub','async':'true'})
        assert r.status_code == 202
        job_id = r.json().get('job_id')
        print('Enqueued job', job_id)

        worker_p = start_worker()

        # poll status until completed
        for _ in range(40):
            r = requests.get(API_HOST + f'/measure/status/{job_id}')
            if r.status_code == 200:
                j = r.json()
                print('Status', j.get('status'))
                if j.get('status') == 'completed' and j.get('result'):
                    print('E2E smoke test passed')
                    worker_p.kill(); flask_p.kill(); return 0
            time.sleep(0.5)

        print('E2E smoke test timed out')
        worker_p.kill(); flask_p.kill(); return 2
    finally:
        try: flask_p.kill()
        except Exception: pass


if __name__ == '__main__':
    exit(main())
