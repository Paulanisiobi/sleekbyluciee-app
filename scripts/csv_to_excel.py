"""
Convert `jira_backlog_expanded.csv` into an Excel workbook with two sheets: Epics and Issues.
Usage:
  - Install deps: `pip install pandas openpyxl`
  - Run: `python scripts/csv_to_excel.py`

Output:
  - `backlog_workbook.xlsx` in the workspace root
"""
import os
import pandas as pd

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'jira_backlog_expanded.csv')
OUT_XLSX = os.path.join(os.path.dirname(__file__), '..', 'backlog_workbook.xlsx')

if not os.path.exists(CSV_PATH):
    print('ERROR: csv file not found:', CSV_PATH)
    exit(1)

df = pd.read_csv(CSV_PATH)

# Identify Epics vs other issues by Issue Type == 'Epic'
if 'Issue Type' not in df.columns:
    print('ERROR: CSV missing "Issue Type" column')
    exit(1)

epics = df[df['Issue Type'].str.lower() == 'epic'].copy()
issues = df[df['Issue Type'].str.lower() != 'epic'].copy()

with pd.ExcelWriter(OUT_XLSX, engine='openpyxl') as writer:
    epics.to_excel(writer, sheet_name='Epics', index=False)
    issues.to_excel(writer, sheet_name='Issues', index=False)

print('Wrote', OUT_XLSX)
