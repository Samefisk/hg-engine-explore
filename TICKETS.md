# Agent bug and task tickets

This is the local worklist that you can give to a Codex agent. It does not replace the project's public GitHub issue tracker.

Say “add this as a bug ticket” or “add this as a task ticket.” The agent adds the chat details and any supplied screenshots here. Later, say “fix the open bugs in `TICKETS.md`” or “complete the open tasks in `TICKETS.md`.”

Allowed states are `open`, `in-progress`, `blocked`, and `done`. A ticket is done only when its acceptance checks have evidence. Creating a ticket records work. It does not authorize implementation or publication.

Screenshots are stored in `documentation/ticket-attachments/<ticket-id>/`. Do not add private data, credentials, or ROM-derived files because ticket files can enter Git history.

<!-- tickets:append-below -->

<!-- ticket:TKT-0005:start -->
## TKT-0005 — Change runner profile to use obstacle-clearing forward jumps

- Type: task
- Status: open
- Priority: normal
- Created: 2026-09-18T08:59:25Z
- Updated: 2026-09-18T08:59:25Z
- Area: Not provided

### Report

Update the runner profile: replace the current forward jump chain pause action with a forward jump that jumps over obstacles. Keep the jump at 2 tiles forward. The runner profile should no longer have a chain movement action.

### Expected result

Runner uses a 2-tile forward jump to jump over obstacles, and the runner profile has no chain movement action.

### Actual result

Not applicable.

### Reproduction steps

- Not applicable.

### Acceptance checks

- [ ] Runner profile uses the obstacle-clearing 2-tile forward jump; the forward jump chain pause action is removed; no chain movement action remains on runner.

### Screenshots

No screenshots supplied.

### Work notes

- 2026-09-18T08:59:25Z — Created from Codex chat.

### Completion evidence

Not complete.

<!-- ticket:TKT-0005:end -->

<!-- ticket:TKT-0006:start -->
## TKT-0006 — Allow active and tired states to select profiles by Pokémon pool

- Type: task
- Status: open
- Priority: normal
- Created: 2026-09-18T09:26:27Z
- Updated: 2026-09-18T09:26:27Z
- Area: Not provided

### Report

Add the ability for an active state and/or tired state to have multiple profiles with different Pokémon pools. For example, when Rattata is active, apply override profile A; when Sentret is active, apply override profile B.

### Expected result

Active and/or tired states can select different profiles based on the active Pokémon pool, such as applying override profile A for Rattata and override profile B for Sentret.

### Actual result

Not applicable.

### Reproduction steps

- Not applicable.

### Acceptance checks

- [ ] Active and/or tired state supports multiple profiles with different Pokémon pools; Rattata selects override profile A; Sentret selects override profile B.

### Screenshots

No screenshots supplied.

### Work notes

- 2026-09-18T09:26:27Z — Created from Codex chat.

### Completion evidence

Not complete.

<!-- ticket:TKT-0006:end -->
