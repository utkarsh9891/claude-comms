# 2026-11-05-a5657a — Only the owner merges to `main`; no approving review required

- **Status:** accepted
- **Date:** 2026-11-05
- **Deciders:** Utkarsh Upadhyay
- **Scope:** repo
- **Supersedes / Amends:** amends [2026-10-23-aa4dba](./2026-10-23-aa4dba-public-repo-pr-only-merge-commits.md)

## Context
ADR aa4dba required one approving code-owner review on every PR to `main`. The owner is the only maintainer, and
GitHub never lets a PR's author approve it, so every merge needed the admin bypass: the required review was a
step that no one could ever satisfy. The owner wants merges to be theirs alone, without that bypass.

## Decision
- **No approving review is required** to merge to `main`. The code-owner review ruleset is disabled (kept, not
  deleted, so it can be switched back on).
- **Only the owner merges**, because only the owner has write access: GitHub lets only collaborators with write
  (or higher) merge a PR. Anyone else helping gets read or triage, contributes by fork and PR, and can't merge.
- Unchanged from aa4dba: `main` changes only through a pull request (no direct push, force-push or deletion), the
  required checks `bridge`, `server`, `plugin`, `docs` up to date with `main`, review threads resolved, merge
  commits only, release tags by the admin only.

## Assumptions
- 1. The owner is the repository's only collaborator with write access (checked 2026-11-05: one collaborator,
     role admin).

## Reversal triggers
- Revisit before giving anyone else write access (Assumption #1): then either re-enable the review ruleset, or add
  a ruleset rule that restricts updates to `main` to the owner.

## Consequences
- The owner merges their own PRs with the normal merge button, no bypass; CI still has to be green.
- Nothing checks a PR with a second pair of eyes. `CODEOWNERS` still names the owner on every file, for review
  requests, not as a gate.

## Alternatives considered
- Keep the review rule and bypass it on every merge: a rule nobody can satisfy, bypassed by habit.
- A ruleset that restricts updates to `main` to the owner: explicit, but GitHub then asks the owner to bypass on
  every merge, the same friction. Unneeded while the owner is the only writer (Assumption #1).
- Add a second maintainer as reviewer: the real fix for a review rule, but there is no second maintainer.
