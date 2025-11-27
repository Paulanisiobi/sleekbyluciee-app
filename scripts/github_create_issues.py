"""
Create GitHub issues from `jira_backlog_expanded.csv`.

Usage:
  - Set env var: GITHUB_TOKEN (personal access token with repo scope)
  - Set env var: GITHUB_REPO (owner/repo), e.g. `sleekbyluciee/sleek-repo`
  - Install deps: `pip install pandas requests`
  - Run: `python scripts/github_create_issues.py`

Notes:
  - The script creates issues with the CSV `Summary` as title and `Description` as body.
  - Labels column is used to apply labels (comma/semicolon-separated).
"""
import os
import time
import argparse
import pandas as pd
import requests

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'jira_backlog_expanded.csv')


def prepare_labels(labels_field):
    labels_list = []
    if isinstance(labels_field, str) and labels_field.strip():
        labels_list = [l.strip() for part in labels_field.split(';') for l in part.split(',') if l.strip()]
    return labels_list


def create_github_issues(repo, token, df, dry_run=False, batch_size=10, sleep_between=1.0):
    api = f'https://api.github.com/repos/{repo}/issues'
    headers = {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'} if token else {}

    total = len(df)
    created = 0
    for start in range(0, total, batch_size):
        batch = df.iloc[start:start + batch_size]
        for idx, row in batch.iterrows():
            title = str(row.get('Summary', 'No summary'))
            body = str(row.get('Description', ''))
            labels_list = prepare_labels(row.get('Labels', ''))

            payload = {'title': title, 'body': body}
            if labels_list:
                payload['labels'] = labels_list

            if dry_run:
                print(f"DRY-RUN: would create issue: {title} (labels: {labels_list})")
                continue

            attempt = 0
            max_attempts = 4
            backoff_base = 2
            while attempt < max_attempts:
                try:
                    resp = requests.post(api, headers=headers, json=payload, timeout=30)
                    if resp.status_code in (200, 201):
                        data = resp.json()
                        print(f"Created GitHub issue #{data['number']}: {data['html_url']}")
                        created += 1
                        break
                    # Handle rate limit or server errors with backoff
                    if resp.status_code in (429, 502, 503, 504) or resp.status_code >= 500:
                        attempt += 1
                        wait = backoff_base ** attempt
                        # If GitHub provides reset header, wait until then
                        if 'X-RateLimit-Reset' in resp.headers:
                            reset = int(resp.headers.get('X-RateLimit-Reset'))
                            wait = max(wait, max(1, reset - int(time.time())))
                        print(f"Rate/server error {resp.status_code}. Retrying in {wait}s (attempt {attempt}/{max_attempts})")
                        time.sleep(wait)
                        continue
                    # Client error: do not retry
                    print(f"Failed to create issue for row {idx+1}: {resp.status_code} {resp.text}")
                    break
                except requests.exceptions.RequestException as e:
                    attempt += 1
                    wait = backoff_base ** attempt
                    print(f"Network exception: {e}. Retrying in {wait}s (attempt {attempt}/{max_attempts})")
                    time.sleep(wait)
                    continue

        if start + batch_size < total:
            time.sleep(sleep_between)

    print(f'Done. Created {created}/{total} issues (dry_run={dry_run}).')


def main():
    parser = argparse.ArgumentParser(description='Create GitHub issues from CSV')
    parser.add_argument('--dry-run', action='store_true', help='Preview only; do not post')
    parser.add_argument('--batch-size', type=int, default=10)
    parser.add_argument('--sleep-between', type=float, default=1.0)
    args = parser.parse_args()

    github_token = os.environ.get('GITHUB_TOKEN')
    github_repo = os.environ.get('GITHUB_REPO')

    if not (github_token and github_repo) and not args.dry_run:
        print('ERROR: set GITHUB_TOKEN and GITHUB_REPO environment variables or use --dry-run')
        return

    if not os.path.exists(CSV_PATH):
        print('ERROR: csv file not found:', CSV_PATH)
        return

    df = pd.read_csv(CSV_PATH)
    create_github_issues(github_repo, github_token, df, dry_run=args.dry_run, batch_size=args.batch_size, sleep_between=args.sleep_between)


if __name__ == '__main__':
    main()
