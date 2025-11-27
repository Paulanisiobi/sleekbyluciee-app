dry_run_preview.py — Local CSV parsing preview

Purpose
- Validate CSV parsing and preview sample payloads that would be sent to Jira or GitHub.

Run

```bash
python scripts/dry_run_preview.py
```

Notes
- This script does not make any network calls. It prints summaries and small example payloads for inspection.
- Modify the script if your Jira `project.key` is different from `SBY` to preview real payload shapes.
