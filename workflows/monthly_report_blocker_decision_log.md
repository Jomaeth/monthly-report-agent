# Monthly Report Blocker Decision Log

Last updated: 2026-05-18

## Purpose

This log documents the four known blockers in the April 2026 monthly report package for demo readiness. The automation is working as intended: it detects the blockers, keeps the report status as `Draft with blockers`, and locks email sending until human review clears or overrides the issues.

## Current Decision

For the AI2C classroom and controlled client demo, the blockers remain intentionally visible because they teach the WAT governance pattern:

- Workflow defines stop conditions.
- Agent explains the implications and prepares review wording.
- Tools recompute facts, validate links, and package outputs.
- Human reviewers decide whether to fix source data or approve a controlled override.

No final report issue, real email sending, claim-sensitive statement, or client-facing approval is authorized from the current data pack.

## Blocker Register

| ID | Section | Record | Finding | Reviewer | Demo Decision |
| --- | --- | --- | --- | --- | --- |
| FORMULA_MISMATCH | Progress | PRG-005 | Cached RAG is `Yellow`; Python recomputation is `Green`. | PM / Project Controls | Keep as blocker until workbook formula/cache is corrected or PM accepts recomputation. |
| FORMULA_MISMATCH | Submission/RFI | RFI-041 | Cached escalation is `Yes`; Python recomputation is `No`. | PM / Project Controls | Keep as blocker until workbook formula/cache is corrected or PM accepts recomputation. |
| MISSING_LINK | Cross-Link Integrity | PRG-005 | `Linked_RFI` references missing ID `MAT-021`. | PM / Project Controls | Keep as blocker until source register link is corrected. |
| MISSING_LINK | Cross-Link Integrity | M-012 | `Linked_RFI_Submission` references missing ID `MAT-021`. | PM / Project Controls | Keep as blocker until source register link is corrected. |

## Demo Talk Track

"The report is not failing silently. The toolchain has found two formula integrity issues and two cross-link integrity issues. The agent can write the issue pack and management narrative, but the workflow keeps the output gated until PM / Project Controls reviews the source workbook and linked registers."

## Release Rule

The demo MP4 and teaching material can be used. The monthly report itself remains draft-only until the four blockers are corrected or formally overridden by the named human reviewers.
