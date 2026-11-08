<!--
Numo9 pull request — engineering report (AI Coding Agent — Mandatory Engineering Workflow, Rules 10 and 11).
Branch: <type>/<ID>-<short-name> from main (docs/branching.md). One deliverable per branch;
commits prefixed with the atomic task ID, e.g. "S-01-T15: ...".
Fill every section. Write "n/a" with a reason instead of deleting a section.
-->

## Deliverable and tasks

- **Deliverable:** <!-- e.g. S-01 · Repository, CI/CD, environments -->
- **Atomic tasks in this PR:** <!-- e.g. S-01-T15 (closes #123) -->
- **Phase plan card:** <!-- e.g. docs/phase_plans/Phase_0_Foundation_and_SaaS_Core.md §6.1 -->

---

# Before implementation

## 1. Problem understanding

- **Objective:**
- **Existing behavior:**
- **Expected behavior:**

## 2. Task breakdown

- **Components:**
- **Atomic tasks:**
- **Dependencies:**

## 3. Implementation plan

- **Execution order:**
- **Acceptance criteria:**
- **Testing strategy:**

---

# After implementation

## 4. Changes made

- **Completed tasks:**
- **Files or components modified:**
- **Important implementation decisions:**

## 5. Testing results

- **Tests executed:**
- **Passed tests:**
- **Failed tests:**
- **Tests not executed and why:**

## 6. Remaining issues

- **Known limitations:**
- **Unresolved bugs:**
- **Risks or dependencies:**

## 7. Final status

<!-- Tick exactly one. Never "Complete" unless every acceptance criterion was observed. -->

- [ ] Complete
- [ ] Partially complete
- [ ] Blocked

---

# Rule 11 — mandatory execution checklist

### Understand

- [ ] Investigated existing implementation.
- [ ] Identified the user and desired outcome.
- [ ] Defined inputs and outputs.
- [ ] Identified business rules.
- [ ] Considered edge cases.
- [ ] Restated the objective.

### Plan

- [ ] Decomposed work into atomic tasks.
- [ ] Identified dependencies.
- [ ] Ordered tasks logically.
- [ ] Defined acceptance criteria.
- [ ] Defined testing procedures.

### Build

- [ ] Implemented the smallest functional piece.
- [ ] Followed existing architecture.
- [ ] Avoided unnecessary changes.
- [ ] Preserved existing functionality.

### Test

- [ ] Verified the implemented behavior.
- [ ] Tested relevant edge cases.
- [ ] Investigated and resolved failures.
- [ ] Checked for regressions.
- [ ] Recorded unverified conditions.

### Improve

- [ ] Reviewed code quality.
- [ ] Removed temporary development artifacts.
- [ ] Improved readability where needed.
- [ ] Confirmed final behavior remains correct.

### Complete

- [ ] Reviewed the final diff.
- [ ] Updated necessary documentation.
- [ ] Reported changes and test results.
- [ ] Confirmed acceptance criteria.
- [ ] Reported the final task status.

### Numo9 project rules

- [ ] Branch name and commit prefixes follow `docs/branching.md`.
- [ ] No secrets, credentials or personal data in the diff.
- [ ] Every new user-visible string is an i18n message with en-CA and fr-CA keys.
- [ ] Every new endpoint declares its feature key (U-01) and is covered by the tenant-isolation sweep (A-01), or n/a.
- [ ] Every new screen uses the design system (A-10), or n/a.
- [ ] `status.txt` updated (✅ only for tasks whose acceptance was observed).
