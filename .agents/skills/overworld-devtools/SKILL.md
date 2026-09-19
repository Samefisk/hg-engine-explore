---
name: overworld-devtools
description: Diagnose and reproduce hg-engine overworld behavior through shared live tools. Use for session control, input, party/spawn setup, and memory data; use verify-overworld for accepted tests.
---

# Drive the overworld tools

Work from the current hg-engine checkout. For an existing registered test, use
[verify-overworld](../verify-overworld/SKILL.md) instead of a manual session.
Battle tests have their own skill.

## Enter the session

Read [session ownership](../../../documentation/overworld-system/devtools.md#session-ownership)
before starting, reusing, resetting or stopping a session. It owns the status,
owner, source-save and cleanup rules. Check
[service readiness](../../../documentation/overworld-system/devtools.md#service-readiness)
before live control. Use `scripts/owctl dev help --json` for current fields and
bounds. If the native bridge needs setup, read
[first use](../../../documentation/overworld-system/devtools.md#first-use).
Use melonDS through the shared tools; a missing backend is a tool gap.
To create the private session, follow
[start an owned session](../../../documentation/overworld-system/devtools.md#start-an-owned-session).

## Choose the needed operation

Read the linked section for the action being performed, not the whole guide:

- Observe or reproduce: [bounded reproduction](../../../documentation/overworld-system/devtools.md#collect-a-bounded-reproduction).
  For a runtime fix, also read [reproduction and acceptance](../../../documentation/overworld-system/verification.md#reproduction-before-editing-acceptance-before-closure)
  before the product edit.
- Inspect a value or apply input: [drive and inspect](../../../documentation/overworld-system/devtools.md#drive-and-inspect).
- Teleport, edit the party, or spawn an actor: [scenario setup](../../../documentation/overworld-system/devtools.md#set-up-a-scenario).
- Save or replay setup: [repeat a setup](../../../documentation/overworld-system/devtools.md#repeat-a-setup).
- Export memory data or a test draft: [recording](../../../documentation/overworld-system/devtools.md#record-then-make-a-test).
- CPU or queue fault: [automatic fault detection](../../../documentation/overworld-system/devtools.md#automatic-runtime-fault-detection)
  before another run. For uncertain requests or other failures, use
  [control and recovery](../../../documentation/overworld-system/devtools.md#agent-control-and-recovery).

Images are optional user-requested artifacts, never an agent test step.
A prepared setup or exported draft is not accepted proof.

If a missing observation needs tool changes, first use the
[outcome-first loop](../../../documentation/overworld-system/devtools-tests.md#outcome-first-tool-work).
Follow [tool checks](../../../documentation/overworld-system/devtools.md#check-the-tools-after-a-change)
for the changed tool. Return to the game question when its missing fact is known.

## Finish or hand off

Apply the ownership guide's cleanup rules. Report the observed subject, result,
memory-data path and exact remaining gap. For a permanent test, pass these to
[author-overworld-scenario](../author-overworld-scenario/SKILL.md); for accepted
proof, use [verify-overworld](../verify-overworld/SKILL.md). When work continues,
update the existing task record under [handoff rules](../../../documentation/overworld-system/verification.md#progress-and-handoffs).
