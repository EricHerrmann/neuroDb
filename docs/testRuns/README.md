# Test Run Logs

This directory holds in-progress and completed test run logs.

A test run log captures pass/fail results as testing happens. It is a real-time record, not a post-fix analysis. Root cause and fix details belong in `docs/manualTestIssues.md` after a failure is resolved.

---

## Naming Convention

```
YYYY-MM-DD-{phase}-run{n}.md
```

Examples:
- `2026-05-04-p5-run1.md`
- `2026-05-04-p6-run1.md`

Use `run2`, `run3` etc. if a phase requires multiple test sessions.

---

## How to Log a Failure During a Test Run

Type `LOG:` followed by the failure description. The agent will append a structured entry to the active test run log and respond with only a confirmation. No diagnosis or fix will be proposed.

**Example input:**
```
LOG: T3 import queue — clicking Import shows spinner then suggestion remains, no success or error visible. Non-blocker, other tests can proceed.
```

**Agent response:**
```
Logged: T3 import queue
```

The agent will not investigate, diagnose, or fix anything until you explicitly ask.

## How to End a Test Run and Begin Fix Pass

When all tests are complete (or all non-blocked tests are done), say:

```
Review test run docs/testRuns/YYYY-MM-DD-{phase}-run{n}.md
```

The agent will read the log, group related failures, and propose a prioritized fix order before touching any code.

---

## Log File Format

See `_template.md` in this directory for the standard format.
