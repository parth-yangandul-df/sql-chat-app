# QueryWise Test Suite

This file contains test questions to validate QueryWise's functionality across intents, context awareness, and LLM fallback handling.

> **Note:** Timesheet domain intents are excluded from testing as per requirements.

---

## 1. Intent Coverage Tests

Test each intent to verify correct SQL generation and data retrieval.

### Resource Domain

| Intent | Test Question | Expected Behavior |
|--------|---------------|-------------------|
| active_resources | "Show me active resources" | Returns employees where IsActive=1 AND statusid=8 |
| benched_resources | "Show me benched resources" | Returns resources in bench project (ProjectId=119) |
| resource_by_skill | "List all Python developers" | Filters by skill keyword using 4-column OR search |
| resource_availability | "Which resources are currently available" | Returns unassigned active resources |
| resource_project_assignments | "Show me John's project assignments" | Returns projects for specific resource |
| resource_skills_list | "What skills does John have" | Returns all skills for specific resource |
| my_allocation | "What's my current allocation" | Returns current project assignment for logged-in user |
| my_skills | "Show my skills" | Returns skills for logged-in user |

### Client Domain

| Intent | Test Question | Expected Behavior |
|--------|---------------|-------------------|
| active_clients | "Show active clients" | Returns clients where IsActive=1 AND StatusId=2 |
| client_projects | "Show projects for ABC Corp" | Returns projects for specific client |
| client_status | "What's the status of XYZ client" | Returns status info for specific client |

### Project Domain

| Intent | Test Question | Expected Behavior |
|--------|---------------|-------------------|
| active_projects | "List active projects" | Returns projects where IsActive=1 AND ProjectStatusId=4 |
| project_by_client | "Show projects for client ABC" | Filters projects by client name |
| project_budget | "What's the budget for Project X" | Returns budget details for specific project |
| project_resources | "Who is working on Project Y" | Returns resources assigned to specific project |
| project_timeline | "Show timeline for Project Z" | Returns start/end dates for specific project |
| overdue_projects | "Which projects are overdue" | Returns projects with EndDate < today |

### User Self Domain

| Intent | Test Question | Expected Behavior |
|--------|---------------|-------------------|
| my_projects | "Show my projects" | Returns projects for logged-in user |
| my_timesheets | "Show my timesheets" | Returns timesheet entries for logged-in user |
| my_utilization | "What's my utilization" | Returns utilization metrics for logged-in user |

---

## 2. Context Awareness Tests

Test the system's ability to handle multi-turn conversations with refinement, filtering, and context switching.

### Refine Tests (Adding constraints to previous query)

1. **Initial:** "Show me active projects"
   **Follow-up:** "Now filter by budget over 50000"
   **Expected:** Applies budget filter to previous results

2. **Initial:** "List all Python developers"
   **Follow-up:** "Only show senior developers"
   **Expected:** Adds experience level filter

3. **Initial:** "Show active clients"
   **Follow-up:** "Filter to those in Bangalore"
   **Expected:** Adds city/location filter

### Clear/Reset Tests (Abandoning previous context)

4. **Initial:** "Show me benched resources"
   **Follow-up:** "Actually, show all resources instead"
   **Expected:** Clears benched filter, shows all active resources

5. **Initial:** "Projects for client ABC"
   **Follow-up:** "Forget that, list all active clients"
   **Expected:** Completely new intent, discards previous context

### Filter on Previous Results

6. **Initial:** "Show all resources"
   **Follow-up:** "From those, who has Java skill"
   **Expected:** Filters previous results by skill

7. **Initial:** "Active projects"
   **Follow-up:** "Which ones have Python developers"
   **Expected:** Filters by resource skill

### Chaining Multiple Refinements

8. **Initial:** "Active clients"
   **Follow-up 1:** "In Bangalore"
   **Follow-up 2:** "With more than 10 employees"
   **Expected:** Stacks multiple filters correctly

---

## 3. LLM Fallback Tests

Test complex and out-of-scope queries that should trigger the LLM fallback path.

### Complex Analytical Queries

1. "Which project has the highest utilization rate?"
   - Expected: LLM fallback with analytical reasoning

2. "What's the trend in resource allocation over the last 6 months?"
   - Expected: LLM fallback with time-series reasoning

3. "Which client contributes the most revenue?"
   - Expected: LLM fallback with aggregation

### Comparative Queries

4. "Compare the budget vs actual spending for all projects"
   - Expected: LLM fallback handling comparison

5. "Who is more utilized: Java developers or Python developers?"
   - Expected: LLM fallback with group comparison

### Edge Cases

6. "Show me everything"
   - Expected: Graceful handling, returns most relevant data or clarification request

7. "What data do you have?"
   - Expected: Describe available data domains

8. "Can you help me with reporting?"
   - Expected: Clarification or fallback to general assistance

### Out-of-Domain Requests

9. "Write a SQL query to get all active users"
   - Expected: LLM provides guidance (not execution)

10. "Explain what each table in the database contains"
   - Expected: Schema description from semantic layer

---

## 4. Edge Case Tests

Test error handling and edge cases.

1. **Empty results:** "Show me projects with budget of -1000" - Should handle gracefully
2. **Special characters:** "Search for client named 'Test & Co'" - Handle escaping
3. **Very long input:** Query with 500+ characters - Should handle without breaking
4. **Mixed case:** "SHOW ME ACTIVE RESOURCES" - Should handle case-insensitively
5. **Typos:** "Shwo me acitve resoruces" - Should still match intent

---

## Test Execution Notes

- All tests should be run against a populated test database
- Timesheet domain (approved_timesheets, unapproved_timesheets, timesheet_by_period, timesheet_by_project) excluded per requirements
- Verify SQL logs show correct intent classification
- Check that params array is empty for NO_FILTER_INTENTS queries