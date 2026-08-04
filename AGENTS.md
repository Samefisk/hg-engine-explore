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

## Build and Test Requests

Builds and tests are opt-in unless the agent needs a build to validate its own work.

- Only run a build when the user's message includes `build` as a standalone sentence, or when the agent needs a build to verify something it changed itself.
- Only run tests when the user's message includes `test` as a standalone sentence.
- Treat `build`, `build.`, `test`, and `test.` as keyword sentences, case-insensitively.
- Do not treat casual mentions of the words "build" or "test" inside longer sentences as requests to run those workflows.
- When a build is requested or needed for self-validation, use the relevant build skill for this repo.
- When tests are requested, use the relevant test skill for this repo.
- If a coding task finishes without an authorized build or test run, report that no build or tests were run because the keyword gate was not opened.

## Local HeartGold Decompilation Reference

When it is present, use `.codex-reference/pokeheartgold/` as the read-only vanilla HeartGold source reference for reverse-engineering and implementation work. It is a local, Git-excluded checkout of `pret/pokeheartgold`, and the local USA HeartGold ROM matches that project's expected SHA-1.

- Prefer the named C/assembly source in `.codex-reference/pokeheartgold/` over raw Ghidra pseudocode.
- Do not edit, stage, commit, or copy ROM-derived/generated artifacts from `.codex-reference/` into the project.
- Read `.codex-reference/README.local.md` for the validated revision, pinned reference commit, important paths, and optional Ghidra workflow.
- Search the reference for the relevant application, field, battle, save, overlay, or system code before inferring vanilla behavior from the hg-engine implementation alone.
- Use Ghidra only for unresolved assembly, exact address matching, or behavior absent from the source reference. If Ghidra is needed, use an NDS-aware loader such as NTRGhidra so ARM9 overlays are included; importing only `arm9.bin` is insufficient for systems implemented in overlays.
- For stock ARM9 binary analysis, prefer `build/arm9.bin`; `base/arm9.bin` may already contain hg-engine patches.
- Do not run `make dumprom` merely to create a Ghidra reference. It begins with a clean and performs broad extraction/migration work.

## Agent Pool Usage

Actively use agents and push them to the max. Default to helper-agent parallelism, and treat solo work as the exception for tiny, single-file, obvious edits.

- At the start of every non-trivial task, immediately look for independent workstreams and spawn helper agents before doing extended solo investigation.
- Do not ask the user for permission before spawning helper agents. Agent use is part of the default workflow unless the user explicitly says not to use them.
- Use helper agents for codebase searches, implementation options, risky-file review, regression hunting, test-log analysis, build-log analysis, documentation sweeps, and final sanity checks.
- For substantial coding tasks, keep the agent pool busy with at least one investigator and one reviewer/verification helper while the main agent implements.
- When there are multiple plausible angles, split them across helpers instead of serializing the work in the main thread.
- Use the available agent pool to the maximum practical extent; do not leave agent capacity idle when there is any useful parallel work to do.
- Keep each spawned agent focused on a clear, bounded assignment with an expected output.
- Reconcile helper-agent results before changing shared files or reporting completion.
- If the agent pool is full, clear inactive, completed, stale, or abandoned helper agents, then spawn new helpers for current work.
- Never clear an active helper agent that is still producing needed results.
- If no helper agents were used for a non-trivial task, explicitly explain why in the final response; silence means the agent missed this instruction.

## Review Language and Scope

Treat routine code reviews as software-quality reviews. Keep findings focused on correctness, reliability, maintainability, compatibility, data integrity, and concrete user impact.

- Use neutral, project-specific language such as “unexpected input,” “invalid state,” “boundary condition,” “unintended behavior,” or “missing validation” when those terms accurately describe the issue.
- Do not introduce offensive-security framing, speculate about malicious use, or provide abuse scenarios, bypass instructions, weaponization details, or step-by-step misuse guidance during an ordinary code review.
- When a finding touches security, describe the concrete defect, affected behavior, severity, and recommended remediation concisely. Include only the technical detail needed to understand and fix it.
- Reserve terms such as “exploit,” “attack vector,” “payload,” “privilege escalation,” and similar security terminology for cases where they are technically necessary and the user has explicitly requested an authorized security assessment.
- Never disguise or omit a genuine security issue merely to avoid security terminology. Report it accurately, but keep the explanation defensive, remediation-oriented, and non-operational.
- Do not broaden a normal review into penetration testing, threat modeling, adversarial analysis, or vulnerability research unless the user explicitly requests that scope.

## Git Overhead Control

Keep git hygiene targeted instead of ritualized.

- Do not run `git fetch`, `git pull`, branch switching, branch listings, or broad `git status` checks after every request by default.
- Run the full `origin/main` startup flow only when starting a new feature/fix/chore branch, preparing branch cleanup, or doing work that depends on the current state of `main`.
- For scoped edits on the current branch, especially docs, notes, config text, or agent-instruction updates, inspect and edit only the files needed.
- A quick `git status --short <path>` is fine when it changes the next action, but do not run git commands solely to fill out a completion template.
- Preserve the dirty working tree. Do not spend time auditing unrelated modified files unless they affect the request.
- For small uncommitted edits, keep the final report short: changed file, what changed, and whether build/tests ran under the keyword gate.

## Start New Work

Run this flow before implementing a new task that needs a fresh feature/fix/chore branch from `main`:

```bash
git checkout main
git fetch origin
git pull --ff-only origin main
git status --short
```

Do not replace any of the commands above with `upstream`.

Do not run this startup flow for tiny follow-ups, docs-only edits, instruction-only edits, reviews, status checks, or scoped edits that intentionally stay on the current branch.

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

For branch, commit, push, PR, branch-cleanup, or substantial coding tasks, include:

- branch name
- commit hashes created
- push destination
- test or build result
- whether local `main` was checked for prerequisite work

For small scoped edits with no commit or push, do not run extra git commands just to report these fields. Give a concise completion note instead.

If tests could not run, say so explicitly.
