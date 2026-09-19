# AGENTS.md

## Work scope and Git

Use `origin/main` as the stable base; `origin` is the real repo and push target. `upstream` is a reference for a separately requested import. Preserve the dirty working tree and unrelated staged work.

- Scoped edits, especially docs, notes, configuration, and instructions, stay on the current branch. Inspect only the files needed; avoid routine fetch, branch changes, or broad status checks.
- Before new feature/fix/chore branches, authorized GitHub work, or branch cleanup, read [the Git workflow](documentation/agent-workflows/git.md). Update local main from origin, prove dependencies, and branch only from the current clean base. Keep features off main.
- Prove finished work is reachable from main before deleting a branch. A remote merge alone does not prove that local main contains it.
- Use existing task authorization for external actions. A review, question, or status statement alone does not authorize publication.

## Build and Test Requests

- No special wording is required. A request to implement, fix, diagnose, or verify includes the relevant local builds, host checks, and disposable game runs needed for that task. Respect an explicit request not to build or test.
- Questions and read-only reviews do not authorize product edits. Use inspection and relevant non-mutating checks; do not start a broad game run for a wording-only change.
- Choose the smallest useful check, then expand at a stable integration point. Use `hg-engine-delta-build` for ROM builds and the project skills below for overworld work. Preserve the saved open-after-build preference and the user's ROM/save files.
- Select tests for a current requirement or regression risk. Reuse sufficient evidence; do not add coverage or repeat a suite by default. Keep relevant regressions, and record why obsolete or duplicate tests are retired. A failure alone is not a reason to remove a test.
- State the build/tests that actually ran, their scope, and any exact remaining proof gap. Source inspection and documentation checks do not prove game behavior.
- Screenshot/video capture requires an explicit user request or manual Capture click. Never capture or inspect images as an agent test step. Use [memory-backed proof](documentation/overworld-system/verification.md#memory-backed-proof) for game observations.

## Papercut Log

Append a small, directly observed repository tool/workflow friction to root `PAPERCUTS.md`: one Markdown bullet with UTC timestamp, `codex`, current branch, and one or two sentences. Preserve existing entries. It is a local, git-ignored queue; continue the task after logging.

Record only new concrete incidents. Exclude secrets, private data, ROM-derived content, full command output, personal absolute paths, ordinary feature bugs, expected failures, speculation, duplicates, and issues already tracked elsewhere. Logging does not authorize builds/tests or replace an in-scope fix. Review or fix the queue only when requested, using [the triage procedure](documentation/agent-workflows/papercuts.md). Use available task context for task-specific review; do not mine private transcripts automatically.

## Bug and Task Tickets

Use [TICKETS.md](TICKETS.md) when the user asks to add a bug or task from chat, attach supplied screenshots, list tickets, or work through the queue. Follow the [project ticket skill](.agents/skills/manage-project-tickets/SKILL.md) for capture, state changes, and validation. Ticket creation records work but does not authorize implementation or publication.

## Source edits and shell commands

Read exact surrounding source before a targeted patch. Use macOS/BSD-portable shell forms; avoid GNU-only flags such as `od -w` and `dd status=none`, zsh special variable names such as `path` and `status`, unquoted optional glob-like operands, and unquoted URLs containing query strings. Put literal shell search patterns in single quotes so backticks and `$()` are not executed. Keep `XXXXXX` at the end of a `mktemp` template, call shell `unlink` once per path, and use `python3 -B -m py_compile` without `-X pycache_prefix=/dev/null`. For SHA-256 shell checks on macOS, use `LC_ALL=C /usr/bin/openssl dgst -sha256`.

## Local HeartGold Decompilation Reference

When it is present, use `.codex-reference/pokeheartgold/` as the read-only vanilla HeartGold source reference for reverse-engineering and implementation work. It is a local, Git-excluded checkout of `pret/pokeheartgold`, and the local USA HeartGold ROM matches that project's expected SHA-1.

- Prefer the named C/assembly source in `.codex-reference/pokeheartgold/` over raw Ghidra pseudocode.
- Do not edit, stage, commit, or copy ROM-derived/generated artifacts from `.codex-reference/` into the project.
- Read `.codex-reference/README.local.md` for the validated revision, pinned reference commit, important paths, and optional Ghidra workflow.
- Search the reference for the relevant application, field, battle, save, overlay, or system code before inferring vanilla behavior from the hg-engine implementation alone.
- Use Ghidra only for unresolved assembly, exact address matching, or behavior absent from the source reference. If Ghidra is needed, use an NDS-aware loader such as NTRGhidra so ARM9 overlays are included; importing only `arm9.bin` is insufficient for systems implemented in overlays.
- For stock ARM9 binary analysis, prefer `build/arm9.bin`; `base/arm9.bin` may already contain hg-engine patches.
- Do not run `make dumprom` merely to create a Ghidra reference. It begins with a clean and performs broad extraction/migration work.

## Overworld Pokémon System

For overworld changes, use [CONTEXT.md](CONTEXT.md) for terms and the
[system README](documentation/overworld-system/README.md#read-order) to find
the affected contract, actor roles, and task-specific guide. That directory is
current design truth; old movement documents and `*_attempts.md` are history.

- Live diagnosis and setup: [overworld-devtools](.agents/skills/overworld-devtools/SKILL.md).
- Design a Pokémon's layered movement and prepare a user-test iteration: [design-overworld-behavior](.agents/skills/design-overworld-behavior/SKILL.md).
- Create or edit a profile, selector, or application: [author-overworld-profile](.agents/skills/author-overworld-profile/SKILL.md).
- Create or change a permanent test: [author-overworld-scenario](.agents/skills/author-overworld-scenario/SKILL.md).
- Run an existing test or accept a runtime fix: [verify-overworld](.agents/skills/verify-overworld/SKILL.md).

Use melonDS and the shared tools only; do not restore standalone drivers or
fall back to DeSmuME. Missing backend support must be finished before live
tests; old DeSmuME results are not melonDS proof. Preserve user ROMs, saves and
sessions. Read [session ownership](documentation/overworld-system/devtools.md#session-ownership)
before live control, and [storage rules](documentation/overworld-system/devtools-tests.md#storage-rules)
when retaining or cleaning test artifacts.

For a runtime fix, preserve a measured reproduction before the edit and repeat
the same trigger and measurement afterward. Complete durable regression
coverage and required acceptance before closure. The full rule is
[reproduction and acceptance](documentation/overworld-system/verification.md#reproduction-before-editing-acceptance-before-closure).

For roadmap work, use the [finite slices](documentation/overworld-system/roadmap.md#finite-delivery-slices)
and [current work table](documentation/overworld-system/roadmap-progress.md#current-work-table).
Follow [goal progress rules](documentation/overworld-system/roadmap.md#goal-progress-rules)
when tools displace product work, the [outcome-first loop](documentation/overworld-system/devtools-tests.md#outcome-first-tool-work)
before tool edits, and [handoff rules](documentation/overworld-system/verification.md#progress-and-handoffs)
when updating task state. Update the canonical system document when a contract,
owner, interface, invariant, failure reason or proof requirement changes.

Spawn-work pacing is a cross-slice gate. Changes to spawn search, population
refill, behavior profiles, destination masks, generated profile data, follower
Hop planning, or Hop landing validation make the D1 stutter proof stale. Run
the extracted-C scan-budget checks first, then prove the current ROM with the
short spawn-work scenario. Never carry an older ROM's D1 pass forward. A
candidate-query cap is necessary but not sufficient:
one automatic spawn attempt must also resolve its profile and prepare its spawn
metadata/class at most once, then reuse that prepared result across resumed
scan updates. It must also bound resumed finalizer guest work. The short
scenario must reject repeated preparation and an over-budget resumed call. A D5
population-count pass cannot close pacing by itself. Tool evidence does not
close a still-reported player-visible hitch. Run
`world.unmounted.spawn-zero-stutter` on the same current `test.nds` and its
unchanged Continue save with the existing Mankey. Do not prepare party,
follower, spawn, or population state. Zero late loops is the only pass. Keep D1
open if this test is red or the user still reports a hitch on the same ROM.

## Helper agents

Use helpers for independent investigation, implementation, or review when that work can shorten the task or improve its result. This is authorized unless the user says otherwise. Give each helper a bounded assignment, owned files where relevant, and an expected result. Reconcile results before reporting completion or changing shared files.

For substantial coding work, prefer an independent reviewer and a separate investigator when each has useful work. Avoid overlapping edits. Stop delegation when the requested work and required evidence are complete; do not create work to fill the pool. Reuse or retire idle helpers as needed, and preserve helpers still producing required results. Small or tightly coupled work can stay with one agent without a special justification.

When giving new work to an idle or completed helper, use `followup_task`, not only `send_message`: a message does not start a new turn. Check helper status before waiting for a delivery. Do not describe a queued message as active work. Freeze shared proof inputs before the final test; review and integrate changes before running that test again.

## Review Language and Scope

Treat routine code reviews as software-quality reviews. Keep findings focused on correctness, reliability, maintainability, compatibility, data integrity, and concrete user impact.

- Use neutral, project-specific language such as “unexpected input,” “invalid state,” “boundary condition,” “unintended behavior,” or “missing validation” when those terms accurately describe the issue.
- Do not introduce offensive-security framing, speculate about malicious use, or provide abuse scenarios, bypass instructions, weaponization details, or step-by-step misuse guidance during an ordinary code review.
- When a finding touches security, describe the concrete defect, affected behavior, severity, and recommended remediation concisely. Include only the technical detail needed to understand and fix it.
- Reserve terms such as “exploit,” “attack vector,” “payload,” “privilege escalation,” and similar security terminology for cases where they are technically necessary and the user has explicitly requested an authorized security assessment.
- Never disguise or omit a genuine security issue merely to avoid security terminology. Report it accurately, but keep the explanation defensive, remediation-oriented, and non-operational.
- Do not broaden a normal review into penetration testing, threat modeling, adversarial analysis, or vulnerability research unless the user explicitly requests that scope.

## Reporting

For small uncommitted edits, report the change and whether authorized build/tests ran. For Git operations or substantial coding work, use the reporting fields in [the Git workflow](documentation/agent-workflows/git.md). State any exact blocker and which independent work is complete.
