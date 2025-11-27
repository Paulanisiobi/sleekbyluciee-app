jira_post.py — Create Jira issues from `jira_import.json`

Pre-reqs
- Python 3.8+
- Install: `pip install requests`

Environment variables (export in bash):

```bash
export JIRA_URL="https://your-domain.atlassian.net"
export JIRA_USER="your-email@example.com"
export JIRA_API_TOKEN="your_api_token_here"
```

Run

```bash
python scripts/jira_post.py
```

Notes
- The script posts each object from `jira_import.json` to the Jira issue create endpoint. The JSON entries should contain the `fields` object as shown in the provided file.
- You may need to adjust the `project.key` and any custom field IDs (for Epics) to match your Jira instance.
- For safety: run against a test project first.
 
Dry-run and batching
- Preview only without sending requests:

```bash
python scripts/jira_post.py --dry-run
```

- Use batching with pauses to avoid rate limits:

```bash
python scripts/jira_post.py --batch-size 5 --sleep-between 2.0
```

When using real posts, ensure `JIRA_URL`, `JIRA_USER` and `JIRA_API_TOKEN` are exported in your shell.

Dry-run file output

To save the exact payloads to disk for audit, run:

```bash
python scripts/jira_post.py --dry-run --dry-run-file ./jira_dryrun_payloads.json
```

This writes the `jira_import.json` payloads to the given file (no network calls are made in this mode).
