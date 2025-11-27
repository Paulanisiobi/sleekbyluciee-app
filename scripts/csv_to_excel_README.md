csv_to_excel.py — Convert backlog CSV to Excel workbook

Pre-reqs
- Python 3.8+
- Install: `pip install pandas openpyxl`

Run

```bash
python scripts/csv_to_excel.py
```

Output
- `backlog_workbook.xlsx` will contain two sheets:
  - `Epics`: rows where `Issue Type` == `Epic`
  - `Issues`: all other rows

Mapping guide (quick):
- `Summary` -> Title of issue/card
- `Issue Type` -> Epic/Story/Task/Spike
- `Description` -> Detailed description
- `Priority`, `Story Points`, `Assignee`, `Components` -> Jira fields (map during import)

If you want, I can also split issues into separate sheet per Epic.
