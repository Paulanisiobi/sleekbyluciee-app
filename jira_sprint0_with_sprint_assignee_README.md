Jira Sprint 0 Import — With Sprint & Assignee

File: `jira_sprint0_with_sprint_assignee.csv`

This CSV adds two columns useful when importing into Jira:
- `Sprint`: Put the target sprint name or sprint id (if your Jira uses numeric sprint ids). If your instance uses sprint ids, replace `SPRINT-1` with the numeric id.
- `Assignee`: The account ID or username to assign the ticket to. If the CSV contains emails or usernames that don't exist in Jira, Jira import will leave issues unassigned.

Recommended mapping when importing
- Summary -> Summary
- Issue Type -> Issue Type
- Description -> Description
- Priority -> Priority
- Story Points -> Story Points
- Labels -> Labels
- Epic Name -> Epic Name (for epic rows)
- Epic Link -> Epic Link (for child rows, link to Epic Name)
- Components -> Components
- Original Estimate -> Original Estimate
- Sprint -> Sprint (map to existing sprint names or ids)
- Assignee -> Assignee (map to Jira user)

Steps
1. Create a test project and create the target sprint (e.g., a sprint named `SPRINT-1`) or note the sprint numeric id.
2. Ensure assignees exist in Jira (create test accounts if needed).
3. Import via Settings → System → External System Import → CSV.
4. Map columns as above. When mapping `Sprint` and `Assignee`, Jira may ask to match values to existing sprints and users. Use the mapping dialog to link CSV values to Jira entities.
5. Validate import results and fix any unmapped values.

If you provide exact sprint names/ids and a user mapping table, I can replace the placeholders with your actual values and produce a final CSV ready for import.
