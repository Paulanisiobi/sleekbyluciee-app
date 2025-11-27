"""
Local dry-run preview: parse `jira_backlog_expanded.csv` and print a summary
and sample payloads for Jira and GitHub without making any network calls.

Run:
  python scripts/dry_run_preview.py

This helps validate CSV parsing and shows what would be sent to each system.
"""
import os
import pandas as pd
import json

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'jira_backlog_expanded.csv')

if not os.path.exists(CSV_PATH):
    print('ERROR: CSV not found at', CSV_PATH)
    exit(1)

print('Parsing:', CSV_PATH)
df = pd.read_csv(CSV_PATH)
print('Rows:', len(df))

# Summarize epics and issues
epics = df[df['Issue Type'].str.lower() == 'epic'] if 'Issue Type' in df.columns else pd.DataFrame()
issues = df[df['Issue Type'].str.lower() != 'epic'] if 'Issue Type' in df.columns else df

print('Epics:', len(epics))
print('Issues:', len(issues))

# Show first 3 issue previews
print('\n--- Sample GitHub issue previews (first 3 issues) ---')
for idx, row in issues.head(3).iterrows():
    title = str(row.get('Summary', 'No summary'))
    body = str(row.get('Description', ''))
    labels = str(row.get('Labels', ''))
    print(f'Title: {title}')
    print('Labels:', labels)
    print('Body (first 200 chars):')
    print(body[:200].replace('\n', ' '))
    print('---')

# Show first 3 Jira payload previews
print('\n--- Sample Jira payload previews (first 3 issues) ---')
for idx, row in df.head(3).iterrows():
    summary = str(row.get('Summary', 'No summary'))
    issuetype = str(row.get('Issue Type', 'Task'))
    desc = str(row.get('Description', ''))
    epic_link = row.get('Epic Link', '') if 'Epic Link' in row else ''
    jira_payload = {
        'fields': {
            'project': {'key': 'SBY'},
            'summary': summary,
            'description': desc,
            'issuetype': {'name': issuetype}
        }
    }
    if epic_link and issuetype.lower() != 'epic':
        jira_payload['fields']['customfield_epic_link'] = epic_link
    print(json.dumps(jira_payload, indent=2)[:1000])
    print('---')

print('\nPreview complete. No network calls were made.')
