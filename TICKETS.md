# Agent bug and task tickets

This is the local worklist that you can give to a Codex agent. It does not replace the project's public GitHub issue tracker.

Say “add this as a bug ticket” or “add this as a task ticket.” The agent adds the chat details and any supplied screenshots here. Later, say “fix the open bugs in `TICKETS.md`” or “complete the open tasks in `TICKETS.md`.”

Allowed states are `open`, `in-progress`, `blocked`, and `done`. A ticket is done only when its acceptance checks have evidence. Creating a ticket records work. It does not authorize implementation or publication.

Screenshots are stored in `documentation/ticket-attachments/<ticket-id>/`. Do not add private data, credentials, or ROM-derived files because ticket files can enter Git history.

<!-- tickets:append-below -->

<!-- ticket:TKT-0007:start -->
## TKT-0007 — Consider linear Walk speed with fractional tile timing

- Type: task
- Status: open
- Priority: normal
- Created: 2026-09-25T22:33:04Z
- Updated: 2026-09-25T22:33:04Z
- Area: Not provided

### Report

Maybe for later; benched for now. Current Walk acceleration reduces travel time by whole frames per tile, so each one-frame reduction gives a larger speed gain near one frame per tile. Consider storing speed as fractional tiles per frame and carrying fractional tile time across accepted Walk tiles. For example, a target of 6.4 frames per tile could use whole-frame tile times that total 32 frames across five tiles. Keep the existing whole-frame motion and tile commit model. This ticket records the idea only; no implementation is requested now.

### Expected result

If pursued, equal acceleration increments produce equal changes in average tiles per frame across Wild, Follower, and Mounted Walk.

### Actual result

Not applicable.

### Reproduction steps

- Not applicable.

### Acceptance checks

- [ ] The requested outcome is complete, and the relevant checks pass.

### Screenshots

No screenshots supplied.

### Work notes

- 2026-09-25T22:33:04Z — Created from Codex chat.

### Completion evidence

Not complete.

<!-- ticket:TKT-0007:end -->

<!-- ticket:TKT-0008:start -->
## TKT-0008 — Stantler always faces north when it stops as a follower

- Type: bug
- Status: open
- Priority: normal
- Created: 2026-09-26T05:03:19Z
- Updated: 2026-09-26T05:03:19Z
- Area: Not provided

### Report

Stantler always looks north when it stops as a follower.

### Expected result

Not provided.

### Actual result

Stantler looks north whenever it stops as a follower.

### Reproduction steps

- Not provided.

### Acceptance checks

- [ ] The reported behavior no longer occurs in the stated case, and the relevant checks pass.

### Screenshots

No screenshots supplied.

### Work notes

- 2026-09-26T05:03:19Z — Created from Codex chat.

### Completion evidence

Not complete.

<!-- ticket:TKT-0008:end -->

<!-- ticket:TKT-0009:start -->
## TKT-0009 — Overworld Pokémon turns every frame when it cannot move

- Type: bug
- Status: open
- Priority: normal
- Created: 2026-09-26T05:05:24Z
- Updated: 2026-09-26T05:05:24Z
- Area: Not provided

### Report

When an overworld Pokémon cannot move, it tends to turn around every frame. One example is Flabébé after it notices the player while it has nowhere to move.

### Expected result

Not provided.

### Actual result

The Pokémon repeatedly turns instead of staying facing one direction while it cannot move.

### Reproduction steps

- Place Flabébé where it has nowhere to move, then let it notice the player. Watch its facing while it remains unable to move.

### Acceptance checks

- [ ] The reported behavior no longer occurs in the stated case, and the relevant checks pass.

### Screenshots

No screenshots supplied.

### Work notes

- 2026-09-26T05:05:24Z — Created from Codex chat.

### Completion evidence

Not complete.

<!-- ticket:TKT-0009:end -->
