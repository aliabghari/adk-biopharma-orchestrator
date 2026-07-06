---
name: 00_system_fallback
description: System fallback and automated git rollback subprocesses.
---
# System Fallback

## Review Checklist
- [ ] Verify rollback signals are intercepted.
- [ ] Confirm git checkout commands wipe corrupted edits cleanly.

## Data Contracts
- **Input:** CRITICAL_FAIL validation signals.
- **Output:** Clean git status, exception logs.
