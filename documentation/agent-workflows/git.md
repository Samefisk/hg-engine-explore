# Git and GitHub workflow

Read this for a new feature branch, commit/push/PR task, or branch cleanup. Scoped documentation or instruction edits, reviews, and status questions stay on the current branch and do not require this startup flow. Preserve existing edits; use a separate clean checkout when new work needs isolation. Do not stash, reset, or discard unrelated work just to make the flow pass.

## New feature, fix, or chore

Use `origin/main` as the stable base. From the intended clean checkout:

```bash
git checkout main
git fetch origin
git pull --ff-only origin main
git status --short
```

Confirm the working tree is clean. If work depends on a prior feature, prove it is present in local main with an ancestor check, a path-specific log, or its unique source symbol. A GitHub merge alone does not establish local reachability. If the dependency is missing, report it and resolve that base before creating the feature branch.

Create one branch for the task after these checks. Follow an explicit branch name or the host's branch-prefix convention; existing repo branches use `feature/`, `fix/`, and `chore/`. Keep features off main. Make small, logical commits with imperative messages when committing is within the request.

## Authorized push and PR

Push to `origin`; target the PR at `origin/main`:

```bash
git push -u origin <branch-name>
gh pr create --repo Samefisk/hg-engine-explore --base main --head <branch-name>
```

Save the PR number returned by `gh pr create` and pass it explicitly to later `gh pr view` and `gh pr checks` commands. Do not rely on branch discovery when the command has no PR argument.

Describe the final behavior, why it changed, and actual verification results. Follow the repository build/test policy. For a full merge and wrap-up request, use the available `hg-engine-feature-complete` skill. A status statement does not request publication.

## After merge and before cleanup

Update local main with the startup commands above before new work or cleanup. Verify the finished branch's work is reachable before deleting it:

```bash
git merge-base --is-ancestor <branch-name> main
```

An ancestor check of the final feature commit is also valid. When a user-requested squash/rebase changes commit identity, inspect the merged PR and final code to establish that all intended work is present; a failed ancestor check alone never authorizes deletion. Keep the branch if that evidence is missing.

When cleanup is authorized and reachability is proved:

```bash
git branch -d <branch-name>
git push origin --delete <branch-name>
```

Respect branches checked out in other worktrees; do not remove those worktrees or force branch deletion to finish cleanup.

## Explicit upstream import

`upstream` is a read-only reference in normal work. Interact with it only for a separately requested import. Fetch and inspect first. If history diverges or cannot fast-forward, report the exact divergence; rewriting main requires an explicit request. Normal feature, PR, merge, and cleanup work uses origin only.

## Report

For branch, commit, push, PR, cleanup, or substantial code changes, state the branch, created commit hashes, push destination, actual build/test result, and whether local main was checked for prerequisites. Report only actions actually taken. Small scoped uncommitted edits need only the changed behavior and verification status; do not run extra Git commands for a report template.
