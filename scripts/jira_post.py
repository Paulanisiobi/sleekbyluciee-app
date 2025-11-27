"""
Post issues from `jira_import.json` to a Jira instance using REST API.

Usage:
  - Set environment variables: JIRA_URL, JIRA_USER, JIRA_API_TOKEN
  - Ensure `jira_import.json` exists in the workspace root (created earlier).
  - Run: `python jira_post.py`

Notes:
  - This script uses basic auth with email/API token. For Atlassian Cloud, create an API token and use your account email.
  - Adjust `project.key` and `customfield_10011` (Epic Name field id) if your Jira instance differs.
"""

import os
import json
import time
import argparse
import requests
from requests.auth import HTTPBasicAuth

JIRA_JSON_PATH = os.path.join(os.path.dirname(__file__), '..', 'jira_import.json')


def load_payloads(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def post_issues(jira_url, user, token, payloads, dry_run=False, batch_size=10, sleep_between=1.0):
    api_create = jira_url.rstrip('/') + '/rest/api/2/issue'
    auth = HTTPBasicAuth(user, token)
    headers = {'Content-Type': 'application/json'}

    total = len(payloads)
    created = 0
    for start in range(0, total, batch_size):
        batch = payloads[start:start + batch_size]
        for idx, item in enumerate(batch, start=start + 1):
            fields_obj = item if 'fields' in item else {'fields': item}
            summary = fields_obj.get('fields', {}).get('summary', '<no summary>')
            if dry_run:
                print(f"DRY-RUN [{idx}/{total}]: would create issue: {summary}")
                continue

            attempt = 0
            max_attempts = 4
            backoff_base = 1.5
            while attempt < max_attempts:
                try:
                    resp = requests.post(api_create, auth=auth, headers=headers, json=fields_obj, timeout=30)
                    if resp.status_code in (200, 201):
                        data = resp.json()
                        print(f"[{idx}/{total}] Created: {data.get('key')} - {data.get('self')}")
                        created += 1
                        break
                    # Recoverable server errors
                    if resp.status_code >= 500 or resp.status_code == 429:
                        attempt += 1
                        wait = backoff_base ** attempt
                        print(f"[{idx}/{total}] Server/rate error {resp.status_code}. Retrying in {wait:.1f}s (attempt {attempt}/{max_attempts})")
                        time.sleep(wait)
                        continue
                    # Client error: do not retry
                    print(f"[{idx}/{total}] Failed ({resp.status_code}): {resp.text}")
                    break
                except requests.exceptions.RequestException as e:
                    attempt += 1
                    wait = backoff_base ** attempt
                    print(f"[{idx}/{total}] Network exception: {e}. Retrying in {wait:.1f}s (attempt {attempt}/{max_attempts})")
                    time.sleep(wait)
                    continue

        if start + batch_size < total:
            time.sleep(sleep_between)

    print(f'Done. Created {created}/{total} issues (dry_run={dry_run}).')


def main():
    parser = argparse.ArgumentParser(description='Post issues from jira_import.json to Jira')
    parser.add_argument('--dry-run', action='store_true', help='Do not call Jira; print actions only')
    parser.add_argument('--batch-size', type=int, default=10, help='Number of issues to send per batch')
    parser.add_argument('--sleep-between', type=float, default=1.0, help='Seconds to sleep between batches')
    parser.add_argument('--dry-run-file', type=str, default=None, help='Write dry-run payloads to JSON file for audit')
    args = parser.parse_args()

    jira_url = os.environ.get('JIRA_URL')
    jira_user = os.environ.get('JIRA_USER')
    jira_token = os.environ.get('JIRA_API_TOKEN')

    if not (jira_url and jira_user and jira_token) and not args.dry_run:
        print('ERROR: Please set JIRA_URL, JIRA_USER, and JIRA_API_TOKEN environment variables or use --dry-run')
        return

    if not os.path.exists(JIRA_JSON_PATH):
        print('ERROR: jira_import.json not found at', JIRA_JSON_PATH)
        return

    payloads = load_payloads(JIRA_JSON_PATH)
    if args.dry_run and args.dry_run_file:
        # write payloads to disk for audit
        try:
            with open(args.dry_run_file, 'w', encoding='utf-8') as f:
                json.dump(payloads, f, indent=2)
            print('Wrote dry-run payloads to', args.dry_run_file)
        except Exception as e:
            print('Failed to write dry-run file:', e)

    post_issues(jira_url, jira_user, jira_token, payloads, dry_run=args.dry_run, batch_size=args.batch_size, sleep_between=args.sleep_between)


if __name__ == '__main__':
    main()
