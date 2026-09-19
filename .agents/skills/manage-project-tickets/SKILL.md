---
name: manage-project-tickets
description: Capture bugs or tasks from Codex chat in TICKETS.md, attach supplied screenshots, update ticket state, or complete work from the queue. Use when the user says to add something as a bug or task ticket, asks to list or update project tickets, or asks an agent to fix or complete tickets.
---

# Manage project tickets

Use [`TICKETS.md`](../../../TICKETS.md) as the single queue and handoff document. Use `python3 scripts/ticket.py --help` for the current command interface.

## Capture from chat

1. Use the current chat and supplied files as the source. Do not ask for facts that can stay `Not provided`.
2. Run `python3 scripts/ticket.py add` with `--type bug` or `--type task`, a short title, and a faithful report. Add optional fields when the chat provides them.
3. Pass each supplied local image path with `--screenshot`. The script copies it into `documentation/ticket-attachments/<ticket-id>/` and embeds it in the ticket. A supplied screenshot authorizes that copy. Do not take a new screenshot unless the user asks.
4. Read the new entry. Report its ID and link to `TICKETS.md`.

Preserve uncertainty. Do not invent steps, expected behavior, area, urgency, or checks. Use `normal` priority unless the user states urgency. Keep private data, credentials, ROM-derived content, and unrelated chat out of tickets. If an image is visible but has no readable file path, create the ticket and record that exact attachment gap.

## Work from the queue

When the user asks to fix bugs or complete tasks, read `TICKETS.md` and select the requested entries. If no IDs are given, use all non-`done` tickets of the requested type. Resume `in-progress` work. Recheck whether a `blocked` ticket's blocker still applies. Follow all normal repository implementation and proof rules.

- Set a ticket to `in-progress` when work starts.
- Set it to `blocked` only for a concrete blocker. Add the blocker as a note.
- Before setting it to `done`, run `python3 scripts/ticket.py check <ID> --all --note "<proof>"` after all acceptance checks are proved. Then set the status with a result and proof note.
- Keep it open if the work or proof is incomplete.

Use `python3 scripts/ticket.py set-status <ID> <status> --note "..."` for state changes. Run `python3 scripts/ticket.py validate` after direct edits.

Tickets record work. They do not grant permission to publish, merge, contact people, or make unrelated changes. Ticket screenshots are context, not runtime proof unless the repository verification rules say otherwise.
