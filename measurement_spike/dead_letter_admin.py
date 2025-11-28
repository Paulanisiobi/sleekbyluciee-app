"""CLI shim that calls the admin web API for dead-letter inspection/requeue.

This script now calls the admin JSON endpoints rather than talking directly to Postgres.
It uses `ADMIN_API_URL` (default `http://localhost:5000/admin`) and `ADMIN_TOKEN` to authenticate.

Usage:
  python dead_letter_admin.py list
  python dead_letter_admin.py show <job_id>
  python dead_letter_admin.py requeue <job_id>
  python dead_letter_admin.py requeue-all
"""
import sys
import os
import json
import requests


ADMIN_API_URL = os.environ.get('ADMIN_API_URL', 'http://localhost:5000/admin')
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN')


def _auth_headers():
    if ADMIN_TOKEN:
        return {'Authorization': f'Bearer {ADMIN_TOKEN}'}
    return {}


def list_dead_jobs(limit=50):
    url = f"{ADMIN_API_URL}/dead_letters.json?limit={limit}"
    r = requests.get(url, headers=_auth_headers(), timeout=10)
    r.raise_for_status()
    data = r.json()
    return data.get('items', [])


def show_job(job_id):
    url = f"{ADMIN_API_URL}/dead_letters/{job_id}"
    r = requests.get(url, headers=_auth_headers(), timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    # admin page returns HTML; for CLI we want JSON. The API also has JSON listing; fetch via /dead_letters.json and filter
    # So reuse list endpoint to find the job (limit large)
    items = list_dead_jobs(limit=500)
    for it in items:
        if it.get('id') == job_id:
            return it
    return None


def requeue_job(job_id):
    url = f"{ADMIN_API_URL}/dead_letters/{job_id}/requeue"
    r = requests.post(url, headers=_auth_headers(), timeout=10)
    if r.status_code == 404:
        return 0
    r.raise_for_status()
    return r.json().get('updated', 0)


def requeue_all():
    items = list_dead_jobs(limit=1000)
    count = 0
    for it in items:
        updated = requeue_job(it['id'])
        count += updated
    return count


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == 'list':
        rows = list_dead_jobs()
        if not rows:
            print('No dead jobs found')
            sys.exit(0)
        for r in rows:
            print(f"ID: {r['id']}  attempts: {r.get('attempts')} created: {r.get('created_at')}")
            print('  last_error:', r.get('last_error'))
            print('  payload:', json.dumps(r.get('payload'), default=str))
            print('-' * 60)
    elif cmd == 'show' and len(sys.argv) == 3:
        job = show_job(sys.argv[2])
        if not job:
            print('Job not found')
            sys.exit(2)
        print(json.dumps(job, default=str, indent=2))
    elif cmd == 'requeue' and len(sys.argv) == 3:
        nid = requeue_job(sys.argv[2])
        if nid:
            print(f'Requeued job {sys.argv[2]}')
        else:
            print('No job updated (check id?)')
    elif cmd == 'requeue-all':
        confirm = input('Are you sure you want to requeue ALL dead jobs? (yes/no): ')
        if confirm.lower() != 'yes':
            print('Aborted')
            sys.exit(1)
        count = requeue_all()
        print(f'Requeued {count} jobs')
    else:
        print('Unknown command')
        print(__doc__)
        sys.exit(1)
