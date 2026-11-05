# Branching and merging

Back to [contributing](./README.md). Decisions: [ADR 2026-10-23-aa4dba](../architecture/decisions/2026-10-23-aa4dba-public-repo-pr-only-merge-commits.md),
[ADR 2026-11-05-a5657a](../architecture/decisions/2026-11-05-a5657a-owner-only-merge-no-required-review.md).

- **`main` changes only through a pull request.** Direct pushes, force-pushes and deleting `main` are blocked for
  everyone, the admin included.
- **Required before merge:** checks `bridge`, `server`, `plugin`, `docs` green and up to date with `main`; all
  review threads resolved. No approving review is required.
- **Only the owner merges:** only the owner has write access; anyone else gets read or triage and contributes by
  fork and PR. Giving someone write access needs an ADR first.
- **Merge commits only.** Squash and rebase merges are disabled; the branch's commits stay in history. Branches are
  deleted after merge.
- **Branch names:** `<type>/<slug>`, type one of `feat`, `fix`, `docs`, `ci`, `chore`, `refactor`.
- **Worktrees.** Work in a linked worktree (`git worktree add ../claude-comms-wt -b <branch> origin/main`), keep
  the main checkout clean, remove the worktree after merge.
- **Release tags** `v<plugin version>` are created by the admin only.
- **Outside contributors** fork and open a PR; their CI runs wait for the owner's approval.
