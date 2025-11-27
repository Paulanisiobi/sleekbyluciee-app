github_create_issues.py — Create GitHub issues from CSV

Pre-reqs
- Python 3.8+
- Install: `pip install pandas requests`

Environment

```bash
export GITHUB_TOKEN="ghp_...yourtoken..."
export GITHUB_REPO="owner/repo"
```

Run

```bash
python scripts/github_create_issues.py
```

Notes
- GitHub token requires `repo` scope to create issues.
- The script uses `Summary` as title, `Description` as body, and `Labels` as labels.
- It will create issues sequentially; consider testing on a small private repo first.
 
Dry-run and batching

```bash
python scripts/github_create_issues.py --dry-run
```

Batching and pause between batches to avoid rate limits:

```bash
python scripts/github_create_issues.py --batch-size 5 --sleep-between 2.0
```

If you see rate-limiting, the script will attempt one retry after sleeping until reset if the GitHub headers provide `X-RateLimit-Reset`.

Dry-run file output

The script supports `--dry-run` to preview actions. Use `--dry-run` and redirect output if you want to capture it, or run the `dry_run_preview.py` script to write explicit JSON payloads.
