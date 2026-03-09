# AGENTS.md

## GitHub workflow for coding agents

Follow these rules for every code change in this repository.

### 1) Remotes and base branch
- Treat `origin` as the user fork.
- Treat `upstream` as the source repository.
- Never push directly to `upstream`.
- Use `main` as the stable base branch.

### 2) Always sync before new work
Run:
```bash
git checkout main
git fetch upstream
git pull --ff-only upstream main
git push origin main
```
If `--ff-only` fails, stop and report the conflict state.

### 3) Branch strategy
- Never implement features directly on `main`.
- Create a new branch per task from updated `main`.
- Branch name format: `feature/<short-topic>`, `fix/<short-topic>`, `chore/<short-topic>`.

Example:
```bash
git checkout -b feature/exp-balance
```

### 4) Commit quality
- Make small, logical commits.
- Commit only files related to the task.
- Commit message format: imperative mood, one clear purpose.

Examples:
- `Add exp contribution split for allied KOs`
- `Fix follow-up message when partner faints`

### 5) Push and PR flow
- Push branch to `origin` and set upstream:
```bash
git push -u origin <branch-name>
```
- Open a Pull Request from branch -> target branch.
- When using GitHub CLI, always create the PR against `origin`, not `upstream`.
- Preferred command:
```bash
gh pr create --repo <origin-owner>/<origin-repo> --base main --head <branch-name>
```
- If a fork-qualified head is needed, it must still target the `origin` repository, never `upstream`.
- PR description must include:
  - What changed
  - Why it changed
  - How it was tested

### 6) Keep branch current during review
Prefer rebase on latest `upstream/main`:
```bash
git fetch upstream
git rebase upstream/main
git push --force-with-lease
```
Only rebase branches owned by the agent/user. Never rewrite shared protected branches.

### 7) Safety rules
- Never run destructive commands like `git reset --hard` or `git checkout -- .` unless explicitly requested.
- Never delete or revert unrelated local changes.
- If the working tree contains unexpected modifications, stop and ask before proceeding.
- Before pushing, run `git status` and report exactly what will be pushed.

### 8) Post-merge cleanup
After PR merge:
```bash
git checkout main
git fetch upstream
git pull --ff-only upstream main
git push origin main
git branch -d <branch-name>
git push origin --delete <branch-name>
```

### 9) Minimum verification before push
At minimum, run relevant build/tests for touched codepaths.
If tests cannot run, state that explicitly in PR notes and handoff message.

### 10) Communication expectations
When reporting completion, include:
- Branch name
- Commit hashes created
- Push destination
- Test/build result
- Any known risks or follow-ups
