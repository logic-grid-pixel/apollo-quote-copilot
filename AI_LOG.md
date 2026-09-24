# AI log

Running record of where AI tooling helped and where I overrode it. Written as I
build, not reconstructed afterward. Feeds the write-up section of the same name.

## How to use this

One entry per override. Keep it short and concrete — the point is that each line
is something that actually happened and that I can talk through in detail.

---

### Template

**Date:**
**Tool:** (Claude Code / other)
**Task:**
**What it produced:**
**What was wrong:**
**How I caught it:** (test, running it, reading the docs, checking the org)
**What I changed:**

---

## Entries

### 2026-09-23 — Apollo enrichment request shape

**Tool:**
**Task:** First call to Apollo organization enrichment.
**What it produced:**
**What was wrong:** Request sent with no `domain` parameter; API returned 422
`ORGANIZATION_IDENTIFIER_REQUIRED`.
**How I caught it:** Ran it and read the error.
**What I changed:** Required-parameter validation before the request is sent —
the same pattern I then applied to every write into Salesforce.
