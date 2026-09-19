#!/usr/bin/env python3
"""Create and maintain the Markdown ticket queue in TICKETS.md."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TICKET_FILE = ROOT / "TICKETS.md"
ATTACHMENT_ROOT = ROOT / "documentation" / "ticket-attachments"
APPEND_MARKER = "<!-- tickets:append-below -->"
STATUSES = ("open", "in-progress", "blocked", "done")
PRIORITIES = ("low", "normal", "high", "critical")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
REQUIRED_SECTIONS = (
    "Report",
    "Expected result",
    "Actual result",
    "Reproduction steps",
    "Acceptance checks",
    "Screenshots",
    "Work notes",
    "Completion evidence",
)
BLOCK_RE = re.compile(
    r"<!-- ticket:(TKT-\d{4}):start -->\n(.*?)<!-- ticket:\1:end -->",
    re.DOTALL,
)


class TicketError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def atomic_write(path: Path, text: str) -> None:
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.chmod(mode)
    os.replace(temporary, path)


def git_directory() -> Path:
    dot_git = ROOT / ".git"
    if dot_git.is_dir():
        return dot_git
    if dot_git.is_file():
        content = dot_git.read_text(encoding="utf-8").strip()
        if content.startswith("gitdir:"):
            path = Path(content.removeprefix("gitdir:").strip())
            return path if path.is_absolute() else (ROOT / path).resolve()
    return ROOT


@contextlib.contextmanager
def queue_lock(timeout_seconds: float = 10.0):
    lock_path = git_directory() / "codex-ticket.lock"
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(descriptor, f"{os.getpid()} {utc_now()}\n".encode())
            break
        except FileExistsError:
            try:
                owner_text = lock_path.read_text(encoding="utf-8")
                owner_pid = int(owner_text.split(maxsplit=1)[0])
                try:
                    os.kill(owner_pid, 0)
                    owner_is_alive = True
                except ProcessLookupError:
                    owner_is_alive = False
                except PermissionError:
                    owner_is_alive = True
                if not owner_is_alive and lock_path.read_text(encoding="utf-8") == owner_text:
                    lock_path.unlink()
                    continue
            except (FileNotFoundError, IndexError, ValueError, OSError):
                pass
            if time.monotonic() >= deadline:
                raise TicketError(f"ticket queue is busy; lock remains at {lock_path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "screenshot"


def safe_markdown(value: str, *, single_line: bool = False) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("<!-- ticket:", "&lt;!-- ticket:")
    text = re.sub(r"(?m)^( {0,3})(#{1,6})(?=\s)", r"\1\\\2", text)
    if single_line:
        text = " ".join(text.splitlines())
    return text.strip()


def read_queue() -> str:
    if not TICKET_FILE.is_file():
        raise TicketError("TICKETS.md is missing")
    text = TICKET_FILE.read_text(encoding="utf-8")
    if APPEND_MARKER not in text:
        raise TicketError(f"TICKETS.md is missing {APPEND_MARKER}")
    return text


def next_id(text: str) -> str:
    numbers = [int(value) for value in re.findall(r"<!-- ticket:TKT-(\d{4}):start -->", text)]
    return f"TKT-{max(numbers, default=0) + 1:04d}"


def bullet_lines(values: list[str], fallback: str, checkbox: bool = False) -> str:
    entries = values or [fallback]
    prefix = "- [ ]" if checkbox else "-"
    return "\n".join(f"{prefix} {value}" for value in entries)


def checked_image_sources(paths: list[str]) -> list[Path]:
    sources = []
    for raw_path in paths:
        source = Path(raw_path).expanduser().resolve()
        if not source.is_file():
            raise TicketError(f"screenshot does not exist: {raw_path}")
        if source.suffix.lower() not in IMAGE_SUFFIXES:
            raise TicketError(f"unsupported screenshot type: {source.suffix or '(none)'}")
        image_format = detect_image_format(source)
        allowed_suffixes = {
            "png": {".png"},
            "jpeg": {".jpg", ".jpeg"},
            "gif": {".gif"},
            "webp": {".webp"},
        }
        if image_format is None or source.suffix.lower() not in allowed_suffixes[image_format]:
            raise TicketError(f"screenshot content does not match its file type: {raw_path}")
        sources.append(source)
    return sources


def detect_image_format(path: Path) -> str | None:
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and data.endswith(b"\x00\x00\x00\x00IEND\xaeB\x60\x82"):
        return "png"
    if data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        return "jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")) and data.endswith(b";"):
        return "gif"
    if (
        len(data) >= 20
        and data.startswith(b"RIFF")
        and data[8:12] == b"WEBP"
        and int.from_bytes(data[4:8], "little") + 8 == len(data)
        and data[12:16] in (b"VP8 ", b"VP8L", b"VP8X")
    ):
        return "webp"
    return None


def copy_images(ticket_id: str, sources: list[Path]) -> list[Path]:
    destinations = []
    if not sources:
        return destinations
    directory = ATTACHMENT_ROOT / ticket_id
    directory.mkdir(parents=True, exist_ok=True)
    for index, source in enumerate(sources, start=1):
        name = f"{index:02d}-{slugify(source.stem)[:48]}{source.suffix.lower()}"
        destination = directory / name
        shutil.copy2(source, destination)
        destinations.append(destination)
    return destinations


def command_add(args: argparse.Namespace) -> None:
    title = safe_markdown(args.title, single_line=True)
    report = safe_markdown(args.report)
    if not title or not report:
        raise TicketError("title and report must not be empty")
    sources = checked_image_sources(args.screenshot)
    with queue_lock():
        text = read_queue()
        ticket_id = next_id(text)
        now = utc_now()
        asset_directory = ATTACHMENT_ROOT / ticket_id
        if asset_directory.exists():
            raise TicketError(f"attachment directory already exists for {ticket_id}")
        try:
            images = copy_images(ticket_id, sources)
            screenshot_lines = []
            for image in images:
                link = image.relative_to(ROOT).as_posix()
                screenshot_lines.append(f"![{ticket_id} screenshot]({link})")
            screenshots = (
                "\n\n".join(screenshot_lines)
                if screenshot_lines
                else safe_markdown(args.attachment_gap or "No screenshots supplied.")
            )
            default_check = (
                "The reported behavior no longer occurs in the stated case, and the relevant checks pass."
                if args.type == "bug"
                else "The requested outcome is complete, and the relevant checks pass."
            )
            block = f"""

<!-- ticket:{ticket_id}:start -->
## {ticket_id} — {title}

- Type: {args.type}
- Status: open
- Priority: {args.priority}
- Created: {now}
- Updated: {now}
- Area: {safe_markdown(args.area or 'Not provided', single_line=True)}

### Report

{report}

### Expected result

{safe_markdown(args.expected or 'Not provided.')}

### Actual result

{safe_markdown(args.actual or ('See the report above.' if args.type == 'bug' else 'Not applicable.'))}

### Reproduction steps

{bullet_lines([safe_markdown(value, single_line=True) for value in args.reproduce], 'Not provided.' if args.type == 'bug' else 'Not applicable.')}

### Acceptance checks

{bullet_lines([safe_markdown(value, single_line=True) for value in args.acceptance], default_check, checkbox=True)}

### Screenshots

{screenshots}

### Work notes

- {now} — Created from {safe_markdown(args.source, single_line=True)}.

### Completion evidence

Not complete.

<!-- ticket:{ticket_id}:end -->
"""
            atomic_write(TICKET_FILE, text.rstrip() + block + "\n")
        except Exception:
            if asset_directory.is_dir():
                shutil.rmtree(asset_directory)
            raise
    print(ticket_id)


def find_block(text: str, ticket_id: str) -> re.Match[str]:
    normalized = ticket_id.upper()
    matches = [match for match in BLOCK_RE.finditer(text) if match.group(1) == normalized]
    if len(matches) != 1:
        raise TicketError(f"expected one ticket for {normalized}, found {len(matches)}")
    return matches[0]


def command_set_status(args: argparse.Namespace) -> None:
    if args.status in ("blocked", "done") and not (args.note and args.note.strip()):
        raise TicketError(f"a {args.status} ticket needs a concrete --note")
    with queue_lock():
        text = read_queue()
        match = find_block(text, args.ticket_id)
        ticket_id = match.group(1)
        body = match.group(2)
        require_ticket_structure(body, ticket_id)
        now = utc_now()
        status_pattern = re.compile(r"(?m)^- Status: .+$")
        updated_pattern = re.compile(r"(?m)^- Updated: .+$")
        previous_status = metadata_value(body, "Status")
        if not status_pattern.search(body) or not updated_pattern.search(body):
            raise TicketError(f"{ticket_id} is missing status metadata")
        if args.status == "done":
            acceptance_start, acceptance_end = section_bounds(body, "Acceptance checks", "Screenshots")
            acceptance = body[acceptance_start:acceptance_end]
            if "- [ ]" in acceptance or "- [x]" not in acceptance:
                raise TicketError(f"{ticket_id} has incomplete acceptance checks")
        body = status_pattern.sub(f"- Status: {args.status}", body, count=1)
        body = updated_pattern.sub(f"- Updated: {now}", body, count=1)
        note = safe_markdown(args.note or f"Status changed to {args.status}.", single_line=True)
        notes_marker = "\n### Completion evidence\n"
        if notes_marker not in body:
            raise TicketError(f"{ticket_id} is missing its completion section")
        body = body.replace(notes_marker, f"- {now} — {note.strip()}\n{notes_marker}", 1)
        if args.status == "done":
            evidence = safe_markdown(args.note) + "\n\n"
            body = re.sub(
                r"(\n### Completion evidence\n\n).*?(?=\n<!--|\Z)",
                lambda evidence_match: evidence_match.group(1) + evidence,
                body,
                count=1,
                flags=re.DOTALL,
            )
        elif previous_status == "done":
            acceptance_start, acceptance_end = section_bounds(body, "Acceptance checks", "Screenshots")
            acceptance = body[acceptance_start:acceptance_end].replace("- [x]", "- [ ]")
            body = body[:acceptance_start] + acceptance + body[acceptance_end:]
            reopening_text = f"Not complete. Previous completion evidence was invalidated when this ticket reopened on {now}.\n\n"
            body = re.sub(
                r"(\n### Completion evidence\n\n).*?(?=\n<!--|\Z)",
                lambda evidence_match: evidence_match.group(1) + reopening_text,
                body,
                count=1,
                flags=re.DOTALL,
            )
        replacement = f"<!-- ticket:{ticket_id}:start -->\n{body}<!-- ticket:{ticket_id}:end -->"
        atomic_write(TICKET_FILE, text[: match.start()] + replacement + text[match.end() :])
    print(ticket_id)


def metadata_value(block: str, key: str) -> str | None:
    match = re.search(rf"(?m)^- {re.escape(key)}: (.+)$", block)
    return match.group(1).strip() if match else None


def require_ticket_structure(body: str, ticket_id: str) -> None:
    positions = []
    for section in REQUIRED_SECTIONS:
        marker = f"### {section}"
        matches = list(re.finditer(rf"(?m)^{re.escape(marker)}$", body))
        if len(matches) != 1:
            raise TicketError(f"{ticket_id} must contain {marker} exactly once")
        positions.append(matches[0].start())
    if positions != sorted(positions):
        raise TicketError(f"{ticket_id} ticket sections are out of order")


def section_bounds(body: str, heading: str, next_heading: str | None = None) -> tuple[int, int]:
    start_marker = f"\n### {heading}\n"
    start = body.find(start_marker)
    if start < 0:
        raise TicketError(f"missing {heading} section")
    content_start = start + len(start_marker)
    if next_heading:
        end = body.find(f"\n### {next_heading}\n", content_start)
    else:
        end = len(body)
    if end < 0:
        raise TicketError(f"missing section after {heading}")
    return content_start, end


def command_check(args: argparse.Namespace) -> None:
    if not (args.note and args.note.strip()):
        raise TicketError("checking acceptance needs --note with the proof")
    with queue_lock():
        text = read_queue()
        match = find_block(text, args.ticket_id)
        ticket_id = match.group(1)
        body = match.group(2)
        require_ticket_structure(body, ticket_id)
        start, end = section_bounds(body, "Acceptance checks", "Screenshots")
        acceptance = body[start:end]
        if "- [ ]" not in acceptance:
            raise TicketError(f"{ticket_id} has no unchecked acceptance checks")
        acceptance = acceptance.replace("- [ ]", "- [x]")
        body = body[:start] + acceptance + body[end:]
        now = utc_now()
        body = re.sub(r"(?m)^- Updated: .+$", f"- Updated: {now}", body, count=1)
        notes_marker = "\n### Completion evidence\n"
        note = safe_markdown(args.note, single_line=True)
        body = body.replace(notes_marker, f"- {now} — {note}\n{notes_marker}", 1)
        replacement = f"<!-- ticket:{ticket_id}:start -->\n{body}<!-- ticket:{ticket_id}:end -->"
        atomic_write(TICKET_FILE, text[: match.start()] + replacement + text[match.end() :])
    print(ticket_id)


def validation_errors() -> list[str]:
    text = read_queue()
    errors = []
    starts = re.findall(r"<!-- ticket:(TKT-\d{4}):start -->", text)
    ends = re.findall(r"<!-- ticket:(TKT-\d{4}):end -->", text)
    matches = list(BLOCK_RE.finditer(text))
    if starts != ends:
        errors.append("ticket start and end markers do not match in order")
    if len(starts) != len(set(starts)):
        errors.append("ticket IDs are not unique")
    if [match.group(1) for match in matches] != starts:
        errors.append("one or more ticket blocks could not be parsed")
    for match in matches:
        ticket_id, block = match.groups()
        for key in ("Type", "Status", "Priority", "Created", "Updated", "Area"):
            if metadata_value(block, key) is None:
                errors.append(f"{ticket_id}: missing {key}")
        if metadata_value(block, "Type") not in ("bug", "task"):
            errors.append(f"{ticket_id}: invalid type")
        if metadata_value(block, "Status") not in STATUSES:
            errors.append(f"{ticket_id}: invalid status")
        if metadata_value(block, "Priority") not in PRIORITIES:
            errors.append(f"{ticket_id}: invalid priority")
        try:
            require_ticket_structure(block, ticket_id)
        except TicketError as error:
            errors.append(str(error))
        if metadata_value(block, "Status") == "done":
            try:
                acceptance_start, acceptance_end = section_bounds(block, "Acceptance checks", "Screenshots")
                acceptance = block[acceptance_start:acceptance_end]
                if "- [ ]" in acceptance or "- [x]" not in acceptance:
                    errors.append(f"{ticket_id}: done ticket has incomplete acceptance checks")
                completion_start, completion_end = section_bounds(block, "Completion evidence")
                completion = block[completion_start:completion_end].strip()
                if not completion or completion.startswith("Not complete."):
                    errors.append(f"{ticket_id}: done ticket has no completion evidence")
            except TicketError as error:
                errors.append(f"{ticket_id}: {error}")
        for link in re.findall(r"!\[[^]]*\]\(([^)]+)\)", block):
            linked_path = (ROOT / link).resolve()
            expected_root = (ATTACHMENT_ROOT / ticket_id).resolve()
            if expected_root not in linked_path.parents:
                errors.append(f"{ticket_id}: screenshot is outside its attachment folder: {link}")
            elif not linked_path.is_file():
                errors.append(f"{ticket_id}: missing screenshot {link}")
            elif detect_image_format(linked_path) is None:
                errors.append(f"{ticket_id}: invalid screenshot data {link}")
    return errors


def command_validate(_: argparse.Namespace) -> None:
    errors = validation_errors()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Ticket queue valid: {len(BLOCK_RE.findall(read_queue()))} ticket(s).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add", help="create a ticket from chat context")
    add.add_argument("--type", choices=("bug", "task"), required=True)
    add.add_argument("--title", required=True)
    add.add_argument("--report", required=True)
    add.add_argument("--priority", choices=PRIORITIES, default="normal")
    add.add_argument("--area")
    add.add_argument("--expected")
    add.add_argument("--actual")
    add.add_argument("--reproduce", action="append", default=[])
    add.add_argument("--acceptance", action="append", default=[])
    add.add_argument("--screenshot", action="append", default=[])
    add.add_argument("--attachment-gap", help="why a supplied image could not be stored")
    add.add_argument("--source", default="Codex chat")
    add.set_defaults(func=command_add)

    set_status = subparsers.add_parser("set-status", help="change ticket state and add a work note")
    set_status.add_argument("ticket_id")
    set_status.add_argument("status", choices=STATUSES)
    set_status.add_argument("--note")
    set_status.set_defaults(func=command_set_status)

    check = subparsers.add_parser("check", help="mark all acceptance checks as proved")
    check.add_argument("ticket_id")
    check.add_argument("--all", action="store_true", required=True)
    check.add_argument("--note", required=True)
    check.set_defaults(func=command_check)

    validate = subparsers.add_parser("validate", help="check ticket structure and screenshot links")
    validate.set_defaults(func=command_validate)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except TicketError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
