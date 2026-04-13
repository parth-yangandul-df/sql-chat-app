---
name: session-summary
description: "Generate 4 short bullet points summarizing the work done in the current session. Use simple language, no technical jargon. Compact summaries only."
---

# Session Summary Generator

This skill generates 4 bullet points summarizing what was accomplished during the session.

## How to Use

When you complete a work session, ask:
- "Give me session summary points"
- "Generate timesheet points"
- "What did we do today"

The summary will cover:
- Bug fixes or issues resolved
- New features or improvements
- Infrastructure or configuration changes
- Any other significant work

## Format

Use simple language that anyone can understand:
- ✓ "Fixed app not starting in Docker"
- ✓ "Improved how the system understands user queries"
- ✓ "Made the query system more reliable"
- ✗ "Refactored LangGraph node dependencies"

## Examples

Previous sessions might cover:
- Docker container startup issues
- Query extraction improvements
- Code cleanup and refactoring
- Adding examples to improve AI accuracy

The skill will generate context-aware points based on what was actually discussed and worked on in the session.