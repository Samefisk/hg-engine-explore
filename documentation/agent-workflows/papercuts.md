# Papercut queue

Use this guide when the user explicitly requests review, triage, or fixes for the root [`PAPERCUTS.md`](../../PAPERCUTS.md) queue. Read the root [`AGENTS.md`](../../AGENTS.md#papercut-log) for the rule for adding incidents. Do not mine private transcripts.

Read the whole queue, including every section. Triage every bullet and preserve its original observation, timestamp, actor, and branch. Keep one bullet per incident; append status details to that bullet when needed. Do not delete, clear, or omit entries unless the user explicitly requests queue cleanup.

Classify each entry as follows:

- `## Open`: A repository issue remains without a complete fix or usable workaround.
- `## Mitigated`: A workaround or partial fix exists. State the remaining limitation. Do not call a workaround resolved.
- `## Resolved`: The fix is complete. Add the UTC resolution date, changed files, and actual verification evidence. Do not claim runtime behavior from source inspection alone when runtime behavior is the issue.
- `## External / Environment`: The cause is outside the repository or agent control. State the owner, workaround, and next action.

Deduplicate only by cross-reference or by merging text that preserves every original observation. Fix repository defects that are in scope; changing a label or adding a note is not a fix. Follow the [build and test gate](../../AGENTS.md#build-and-test-requests). A review-only request reports findings and does not authorize queue or product edits.

Done means every entry is under the correct heading, every `Resolved` entry has its date, changed files, and evidence, every `Mitigated` entry names its limitation, and every external entry has an owner, workaround, and next action. Report any exact proof gap.
