"""Ticket CLI checks in disposable queues; no project queue or screenshot edits."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SOURCE = Path(__file__).with_name("ticket.py")


def ticket_block(number: int, *, state: str = "open", kind: str = "bug", report: str = "The report.",
                 note: str = "Next: repeat the saved trigger.", checks: int = 2) -> str:
    ticket_id = f"TKT-{number:04d}"
    acceptance = "\n".join(f"- [{'x' if state == 'done' else ' '}] Check {index}." for index in range(checks))
    return f"""<!-- ticket:{ticket_id}:start -->
## {ticket_id} — Ticket {number}

- Type: {kind}
- Status: {state}
- Priority: normal
- Created: 2026-10-03T12:00:00Z
- Updated: 2026-10-03T13:00:00Z
- Area: Test area

### Report

{report}

### Expected result

The expected result.

### Actual result

The actual result.

### Reproduction steps

- Repeat the trigger.

### Acceptance checks

{acceptance}

### Screenshots

No screenshots supplied.

### Work notes

- 2026-10-03T12:00:00Z — Earlier note.
- 2026-10-03T13:00:00Z — {note}

### Completion evidence

{'The required checks passed.' if state == 'done' else 'Not complete.'}

<!-- ticket:{ticket_id}:end -->
"""


class TicketCliTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="hg-ticket-cli-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        scripts = self.root / "scripts"
        scripts.mkdir()
        self.cli = scripts / "ticket.py"
        shutil.copy2(SOURCE, self.cli)
        self.queue = self.root / "TICKETS.md"
        self.write_queue(
            ticket_block(1),
            ticket_block(2, state="in-progress", kind="task"),
            ticket_block(3, state="blocked"),
            ticket_block(4, state="done", kind="task"),
        )

    def write_queue(self, *blocks: str) -> None:
        self.queue.write_text("# Test queue\n\n<!-- tickets:append-below -->\n\n" + "\n".join(blocks), encoding="utf-8")

    def run_cli(self, *words: str, code: int = 0) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, "-B", str(self.cli), *words],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def listed_ids(self, *options: str) -> list[str]:
        result = json.loads(self.run_cli("list", *options, "--json").stdout)
        return [item["id"] for item in result["tickets"]]

    def test_unfinished_default_and_all_status_type_filters(self) -> None:
        cases = [
            ((), ["TKT-0001", "TKT-0002", "TKT-0003"]),
            (("--all",), ["TKT-0001", "TKT-0002", "TKT-0003", "TKT-0004"]),
            (("--status", "done"), ["TKT-0004"]),
            (("--status", "open", "--status", "blocked"), ["TKT-0001", "TKT-0003"]),
            (("--type", "task"), ["TKT-0002"]),
            (("--all", "--type", "task"), ["TKT-0002", "TKT-0004"]),
            (("--status", "blocked", "--type", "task"), []),
        ]
        for options, expected in cases:
            with self.subTest(options=options):
                self.assertEqual(self.listed_ids(*options), expected)

    def test_show_uses_stored_report_checks_and_latest_note(self) -> None:
        result = json.loads(self.run_cli("show", "tkt-0002", "--json").stdout)["ticket"]
        self.assertEqual(result["id"], "TKT-0002")
        self.assertEqual(result["status"], "in-progress")
        self.assertEqual(result["report"], "The report.")
        self.assertEqual(result["latestNote"], "2026-10-03T13:00:00Z — Next: repeat the saved trigger.")
        self.assertEqual(result["acceptanceChecks"], [
            {"done": False, "text": "Check 0."}, {"done": False, "text": "Check 1."},
        ])
        self.assertEqual(result["truncatedFields"], [])
        self.assertNotIn("nextAction", result)
        text = self.run_cli("show", "TKT-0002").stdout
        self.assertIn("Status: in-progress", text)
        self.assertNotIn("Earlier note.", text)

    def test_full_show_returns_only_exact_stored_block_without_edits(self) -> None:
        selected = ticket_block(2, state="in-progress", kind="task", report="Full report. " * 1000, note="Full note. " * 1000, checks=30)
        self.write_queue(ticket_block(1), selected, ticket_block(3))
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(self.run_cli("show", "tkt-0002", "--full").stdout, selected.removesuffix("\n"))
        self.assertIn("found 0", self.run_cli("show", "TKT-9999", "--full", code=2).stderr)
        self.run_cli("show", "TKT-0002", "--full", "--json", code=2)
        after = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(after, before)

    def test_views_do_not_change_queue_attachments_or_existing_lock(self) -> None:
        attachment = self.root / "documentation/ticket-attachments/TKT-0001/supplied.png"
        attachment.parent.mkdir(parents=True)
        attachment.write_bytes(b"A supplied attachment that reads must not inspect.")
        self.queue.write_text(self.queue.read_text().replace(
            "No screenshots supplied.",
            "![supplied](documentation/ticket-attachments/TKT-0001/supplied.png)",
            1,
        ))
        git = self.root / ".git"
        git.mkdir()
        (git / "codex-ticket.lock").write_text("Existing owner lock.\n")
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        for words in [("list",), ("list", "--all", "--json"), ("show", "TKT-0001"), ("show", "TKT-0001", "--json"), ("show", "TKT-0001", "--full")]:
            self.run_cli(*words)
        after = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(after, before)

    def test_limits_and_long_fields_are_marked_and_bounded(self) -> None:
        self.write_queue(*(ticket_block(number, report="R" * 9000, note="N" * 9000, checks=30) for number in range(1, 26)))
        result = json.loads(self.run_cli("list", "--limit", "3", "--json").stdout)
        self.assertEqual((result["total"], result["omitted"], len(result["tickets"])), (25, 22, 3))
        self.assertLess(len(result["tickets"][0]["latestNote"]), 241)
        self.assertIn("latestNote", result["tickets"][0]["truncatedFields"])
        listed = self.run_cli("list", "--limit", "3").stdout
        self.assertIn("22 more ticket(s)", listed)
        self.assertIn("show TKT-0001 --full", listed)
        shown = json.loads(self.run_cli("show", "TKT-0001", "--json").stdout)["ticket"]
        self.assertEqual((shown["acceptanceTotal"], shown["acceptanceOmitted"]), (30, 18))
        self.assertEqual(len(shown["acceptanceChecks"]), 12)
        self.assertEqual(set(shown["truncatedFields"]), {"report", "latestNote"})
        compact = self.run_cli("show", "TKT-0001").stdout
        self.assertLess(len(compact), 4000)
        self.assertIn("show TKT-0001 --full", compact)
        for limit in ("0", "-1", "101", "many"):
            self.run_cli("list", "--limit", limit, code=2)
        self.run_cli("list", "--all", "--status", "done", code=2)

    def test_missing_id_and_malformed_queue_fail_without_edits(self) -> None:
        self.assertIn("found 0", self.run_cli("show", "TKT-9999", code=2).stderr)
        good = self.queue.read_text()
        malformed = [
            good.replace("<!-- tickets:append-below -->", ""),
            good.replace("<!-- ticket:TKT-0003:end -->", ""),
            good + ticket_block(1),
            good.replace("- Status: blocked", "- Status: unknown"),
            good.replace("### Report", "### Missing report", 1),
        ]
        for text in malformed:
            self.queue.write_text(text)
            before = self.queue.read_bytes()
            for words in (("list",), ("show", "TKT-0001")):
                with self.subTest(words=words, text=text[-80:]):
                    self.run_cli(*words, code=2)
                    self.assertEqual(self.queue.read_bytes(), before)

    def test_empty_queue_is_a_valid_empty_read(self) -> None:
        self.write_queue()
        self.assertEqual(json.loads(self.run_cli("list", "--json").stdout), {"tickets": [], "total": 0, "omitted": 0})
        self.run_cli("show", "TKT-0001", code=2)

    def test_legacy_add_status_check_validate_and_reopen_still_work(self) -> None:
        result = self.run_cli("add", "--type", "bug", "--title", "New bug", "--report", "New report.")
        self.assertEqual(result.stdout.strip(), "TKT-0005")
        self.run_cli("set-status", "TKT-0005", "in-progress", "--note", "Working on the report.")
        self.run_cli("set-status", "TKT-0005", "done", "--note", "No proof yet.", code=2)
        self.run_cli("check", "TKT-0005", "--all", "--note", "The required check passed.")
        self.run_cli("set-status", "TKT-0005", "done", "--note", "The requested fix has proof.")
        self.run_cli("validate")
        done = json.loads(self.run_cli("show", "TKT-0005", "--json").stdout)["ticket"]
        self.assertEqual(done["status"], "done")
        self.assertTrue(all(check["done"] for check in done["acceptanceChecks"]))
        self.run_cli("set-status", "TKT-0005", "open", "--note", "The same trigger failed again.")
        self.run_cli("validate")
        reopened = json.loads(self.run_cli("show", "TKT-0005", "--json").stdout)["ticket"]
        self.assertEqual(reopened["status"], "open")
        self.assertTrue(all(not check["done"] for check in reopened["acceptanceChecks"]))


if __name__ == "__main__":
    unittest.main()
