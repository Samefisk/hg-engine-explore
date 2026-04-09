# AGENTS.md

## Git and GitHub workflow for this repo

This repository is maintained from `origin/main`.

- `origin` is the real project repo and the default push target.
- `upstream` is only a reference repo.
- Never run `git pull --ff-only upstream main` as part of normal feature work.
- Do not automatically sync this repo to `upstream/main`.

If you are an agent working here, treat `origin/main` as the stable base branch unless the user explicitly asks for a separate upstream import task.

## Golden Rules

- Never start feature work from a stale local branch.
- Always branch from local `main` after updating it from `origin/main`.
- If new work depends on an older merged feature, verify that feature is already on `main` before creating the next branch.
- Never assume “merged on GitHub” means “present in local main.”
- Never delete a finished branch until you verify its work is reachable from `main`.
- Never push directly to `upstream`.

## Start New Work

Run this flow before implementing a new task:

```bash
git checkout main
git fetch origin
git pull --ff-only origin main
git status --short
```

Do not replace any of the commands above with `upstream`.

Then:

1. Confirm the working tree is clean before branching.
2. If the new task depends on a previous feature, verify that feature is on `main`.
3. Only after that, create a new branch from local `main`.

Example:

```bash
git checkout -b feature/magma-armor-rework
```

## Dependency Check Before Branching

If the new task builds on earlier work, you must confirm the earlier work is already on `main` before branching.

Use one of these checks:

```bash
git branch --contains <commit>
git log --oneline main -- <path>
git grep "<unique symbol or ability name>"
```

If the required commit or code is not reachable from `main`:

- stop immediately
- report the missing dependency clearly
- do not start the new feature branch from that stale base

## Commit and Branch Rules

- Never implement features directly on `main`.
- Create one branch per task.
- Use branch names like:
  - `feature/<topic>`
  - `fix/<topic>`
  - `chore/<topic>`
- Make small, logical commits with clear imperative messages.

Examples:

- `Add Rising Star ability for Ledian`
- `Rework Magma Armor battle behavior`

## PR and Merge Flow

Push branches to `origin` and open PRs against `origin/main`.

Example:

```bash
git push -u origin <branch-name>
gh pr create --repo Samefisk/hg-engine-explore --base main --head <branch-name>
```

PR notes should include:

- what changed
- why it changed
- how it was tested

After a PR is merged, update local `main` from `origin/main` before starting anything new:

```bash
git checkout main
git fetch origin
git pull --ff-only origin main
```

## Before Deleting a Branch

Before deleting a finished branch, verify that its work is on `main`.

Use one of these checks:

```bash
git merge-base --is-ancestor <branch-name> main
git branch --contains <feature-commit>
git log --oneline main -- <relevant path>
```

Only delete the branch if the feature is confirmed to be present on `main`.

Safe cleanup flow:

```bash
git checkout main
git fetch origin
git pull --ff-only origin main
git branch -d <branch-name>
git push origin --delete <branch-name>
```

If the feature is not on `main` yet:

- do not delete the branch
- report the problem
- keep the branch until the missing work is recovered or merged

## Optional Upstream Import

`upstream` is not part of the routine workflow.

Only interact with `upstream` if the user explicitly asks to import changes from the original repo.

When that happens:

1. Treat it as a separate maintenance task.
2. Fetch and inspect first.
3. If histories diverge or a fast-forward is impossible, stop and report the situation.
4. Do not force local `main` to match `upstream/main` unless the user explicitly asks for that rewrite.

If the user asks for a normal new feature, bug fix, branch, commit, push, PR, or post-merge cleanup, stay on the `origin/main` workflow and do not touch `upstream`.

## Never Do This Automatically

- Do not run `git pull --ff-only upstream main` as a default startup step.
- Do not run `git fetch upstream && git pull --ff-only upstream main` for routine work.
- Do not assume a merged PR already exists in local `main`.
- Do not branch from stale `main`.
- Do not delete a branch before verifying its work is on `main`.
- Do not rewrite `main` to match `upstream` unless the user explicitly asks for it.

## Reporting Requirements

When reporting completion of a coding task, include:

- branch name
- commit hashes created
- push destination
- test or build result
- whether local `main` was checked for prerequisite work

If tests could not run, say so explicitly.
