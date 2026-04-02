---
status: testing
phase: 06-context-aware-domain-tools
source:
  - 06-01-SUMMARY.md
  - 06-02-SUMMARY.md
  - 06-03-SUMMARY.md
  - 06-04-SUMMARY.md
  - 06-05-SUMMARY.md
started: "2026-04-02T10:00:00Z"
updated: "2026-04-02T10:05:00Z"
---

## Current Test

number: 2
name: Context Badge Shows in UI
expected: |
  After any successful query, the chat header shows a context indicator badge displaying the current domain and intent (e.g., "resource · active_resources") with a clear button
awaiting: user response

## Tests

### 1. Follow-Up Query Routes to Domain Tool
expected: After "Show all active resources", follow-up "which one of these know python?" returns filtered results with skill-based subquery refinement
result: pass

### 2. Context Badge Shows in UI
expected: After any successful query, the chat header shows a context indicator badge displaying the current domain and intent (e.g., "resource · active_resources") with a clear button
result: [pending]

### 3. Clear Context Button Works
expected: Clicking the clear context button resets the conversation context. The next query after clearing is treated as a fresh question (no context inheritance). An amber banner appears confirming context was cleared
result: [pending]

### 4. Topic Switch Clears Context Automatically
expected: After "Show all active resources", asking "Show all active clients" (different domain) should NOT inherit the resource context. The result should be a full client list, not a filtered subset
result: [pending]

### 5. Fallback Intent on 0-Row Result
expected: When a parameterized query like "Show resources with skill in Cobol" returns 0 rows, the system should automatically try the broader fallback intent (active_resources) before falling back to LLM. The user should see results from the broader query, not an LLM apology
result: [pending]

### 6. Session Persistence Across Refresh
expected: After sending queries in StandaloneChatPage, refreshing the browser tab should restore the conversation history. Follow-up queries after refresh should still work correctly
result: [pending]

### 7. TurnContext Propagates End-to-End
expected: The backend API response includes a turn_context object with intent, domain, params, columns, and sql fields. The frontend sends this back as last_turn_context on the next request. This can be verified by checking the network tab in browser dev tools
result: [pending]

### 8. Param Inheritance Across Follow-Ups
expected: After "Show resources with skill in Python", asking "which of these are billable?" should carry forward the Python skill param AND add the billable filter, resulting in Python-skilled billable resources
result: [pending]

### 9. Long Fresh Question Does NOT Trigger Follow-Up
expected: After "Show all active resources", asking "List all project managers with more than five years of experience" should NOT inherit the resource context. It should be classified as a fresh query and routed independently
result: [pending]

### 10. SQL Server Concurrent Requests Don't Crash
expected: Opening two browser tabs and sending queries simultaneously to the same connection should NOT produce "Connection is busy with results for another command" errors. Both queries should complete successfully
result: [pending]

## Summary

total: 10
passed: 1
issues: 0
pending: 9
skipped: 0

## Gaps

[none yet]
