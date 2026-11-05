# Branching and merging

Back to [contributing](./README.md). Decision: [ADR 2026-10-23-aa4dba](../architecture/decisions/2026-10-23-aa4dba-public-repo-pr-only-merge-commits.md).

- **`main` changes only through a pull request.** Direct pushes, force-pushes and deleting `main` are blocked for
  everyone, the admin included.
- **Required before merge:** checks `bridge`, `server`, `plugin`, `docs` green and up to date with `main`; one
  approving code-owner review (a new push dismisses it); all review threads resolved. The admin may merge their own
  PR once checks pass.
- **Merge commits only.** Squash and rebase merges are disabled; the branch's commits stay in history. Branches are
  deleted after merge.
- **Branch names:** `<type>/<slug>`, type one of `feat`, `fix`, `docs`, `ci`, `chore`, `refactor`.
- **Worktrees.** Work in a linked worktree (`git worktree add ../claude-comms-wt -b <branch> origin/main`), keep
  the main checkout clean, remove the worktree after merge.
- **Release tags** `v<plugin version>` are created by the admin only.
- **Outside contributors** fork and open a PR; their CI runs wait for the owner's approval.
