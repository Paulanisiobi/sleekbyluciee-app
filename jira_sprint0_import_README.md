Jira Sprint 0 Import

File: `jira_sprint0_import.csv`

Purpose
- Import the Sprint 0 tickets into Jira using the CSV importer.

Recommended Jira import column mapping
- Summary -> Summary
- Issue Type -> Issue Type
- Description -> Description
- Priority -> Priority
- Story Points -> Story Points (Jira Software custom field)
- Labels -> Labels
- Epic Name -> Epic Name (map to Epic rows)
- Epic Link -> Epic Link (for child issues referencing the Epic Name)
- Components -> Components
- Original Estimate -> Original Estimate (human readable; Jira will convert if configured)

Import steps
1. In Jira: Settings → System → External System Import → CSV.
2. Upload `jira_sprint0_import.csv`.
3. Field mapping: map the CSV columns to Jira fields as above. IMPORTANT:
   - Map `Epic Name` to `Epic Name` for Epic rows.
   - Map `Epic Link` to `Epic Link` for non-Epic rows so they link to the correct Epic.
4. If Jira asks for value mapping (e.g., Issue Type or Priority), map the values in the CSV (Epic, Task, Story, Spike, Highest/High/Medium) to your project's values.
5. Run import to a test project first. Verify Epics and linked issues.

Notes
- Ensure the `Epic Name` strings match exactly between Epic rows and `Epic Link` values.
- If your Jira instance uses a custom field ID for Epic Name (e.g., `customfield_10011`), the CSV importer UI will present mapping options — choose `Epic Name`.
- After import, adjust `Assignee` and sprint assignment as needed in Jira.
