# 2026-10-23-aa4dba — Public repo; `main` changes only by reviewed PR with merge commits

- **Status:** amended by a5657a
- **Date:** 2026-10-23
- **Deciders:** Utkarsh Upadhyay
- **Scope:** repo
- **Supersedes / Amends:** —

## Context
The repo is installed on several of the owner's machines and by teammates, and the code it ships has full access
to each installer's WhatsApp account. Changes must therefore be reviewed, tested and traceable. GitHub enforces
branch rules on private repos only on paid plans; the owner's account is on the free plan.

## Decision
- The repo is **public** under the owner's personal account, so readers and installers need no invitation or
  token and GitHub rulesets are enforceable for free.
- Ruleset on `main`: changes only through a pull request; one approving **code-owner** review; stale approvals
  dismissed on push; review threads resolved; required checks `bridge`, `server`, `plugin`, `docs` up to date
  with `main`; no deletion or force-push. The repository admin may merge their own PR once checks pass
  (bypass mode `pull_request`), but can't push to `main` directly.
- **Merge commits only** (squash and rebase disabled) so branch history is kept; branches deleted after merge.
- Release tags `v*`: created, moved or deleted only by the admin.
- Teammates get read access by default and contribute by fork and PR; CI for outside contributors waits for
  approval.
- Secret scanning with push protection, Dependabot alerts and updates, private vulnerability reporting.

## Assumptions
- 1. The repo contains no secrets, personal data or employer-identifying material (history scanned 2026-10-23).
- 2. The owner's GitHub account is on the free plan.
- 3. The owner is the only maintainer.

## Reversal triggers
- Revisit if anything sensitive must live in the repo (Assumption #1): move to private with a paid plan.
- Revisit when a second maintainer joins (Assumption #3): drop the admin self-merge bypass and require their review.

## Consequences
- The owner's GitHub handle is publicly linked to an unofficial WhatsApp client.
- Every change, including the owner's, goes through a PR and green CI ([branching and merging](../../contributing/branching-and-merging.md)).

## Alternatives considered
- **Private, free plan:** rejected; rules can't be enforced (Assumption #2).
- **Private with GitHub Pro:** viable; rejected by the owner in favour of public.
- **Squash merges:** rejected by the owner; branch history is wanted on `main`.
