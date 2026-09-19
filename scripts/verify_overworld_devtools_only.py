#!/usr/bin/env python3
"""Read-only retirement check for old overworld paths and DeSmuME execution.

The shared devtools may use an emulator. Host/model/ABI tests and battle tests
may still launch processes. This check bans retired overworld entry points and
DeSmuME imports, loads and dependencies, not those valid mechanisms. Historical
evidence and DSV save-format text are not active emulator execution.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re


REPO = Path(__file__).resolve().parents[1]
RETIRED_FILES = (
    "scripts/verify_overworld_walk_runtime.py",
    "scripts/headless-overworld-test.py",
    "scripts/headless-headbutt-effect-trace.py",
    "scripts/headless-test-ready.sh",
    "tools/overworld/runtime_normal_play.py",
    "tools/overworld/runtime_actor_binding.py",
    "tools/overworld/runtime_normal_healing.py",
)
RETIRED_MODULES = tuple(path.removesuffix(".py").replace("/", ".")
                        for path in RETIRED_FILES if path.endswith(".py"))
_IDENTITIES = sorted({*RETIRED_FILES, *RETIRED_MODULES,
                      *(Path(path).name for path in RETIRED_FILES),
                      *(Path(path).stem for path in RETIRED_FILES)}, key=len, reverse=True)
RETIRED = re.compile(r"(?<![\w])(?:" + "|".join(map(re.escape, _IDENTITIES)) + r")(?![\w])")
HISTORY_PATH = "documentation/overworld-system/roadmap-progress.md"
HISTORY_START = "<!-- overworld-retirement-history:start -->"
HISTORY_END = "<!-- overworld-retirement-history:end -->"
SKILLS = ("overworld-devtools", "author-overworld-scenario", "verify-overworld")
_LOAD_CALLS = {"__import__", "import_module", "spec_from_file_location", "run_path", "run_module", "exec", "compile"}
_PROCESS_PREFIXES = ("subprocess.", "asyncio.create_subprocess_", "os.exec", "os.spawn")
_PROCESS_CALLS = {"os.system", "os.popen"}
_DESMUME = re.compile(r"(?<![\w])(?:py[-_]?desmume|libdesmume|desmume)(?![\w])", re.IGNORECASE)
_NATIVE_LOAD_CALLS = {"ctypes.CDLL", "ctypes.PyDLL", "ctypes.WinDLL", "ctypes.OleDLL",
                      "ctypes.cdll.LoadLibrary", "ctypes.pydll.LoadLibrary"}
_RETAINED_BACKEND = re.compile(
    r"\b(?:raw|direct|old|older|legacy|headless)\b[^.!?;]{0,100}"
    r"\b(?:runners?|scripts?|helpers?|bootstrap)\b[^.!?;]{0,100}"
    r"\b(?:internal|backends?|dependencies|remain|retain)\b|"
    r"\bretain backend dependencies\b", re.IGNORECASE)
_KEYWORD_GATE = re.compile(
    r"\b(?:run|build|test).{0,35}\bonly when\b.{0,100}"
    r"\b(?:standalone sentence|standalone keyword|test keyword|build keyword)\b", re.IGNORECASE)


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    line: int
    code: str
    message: str


def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _name(node.value) + "." + node.attr
    return ""


def audit_python(source: str, path: str) -> list[Finding]:
    """Inspect executable imports and loader/process arguments, never execute them.

    Literal bindings are followed in the current lexical scopes. Comments and
    host mutation-fixture strings alone do not create execution routes.
    """
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as error:
        return [Finding(path, error.lineno or 1, "invalid-python", str(error.msg))]
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    scopes = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
    bindings = {}
    aliases = {}

    def scope_of(node):
        while node not in (None, tree) and not isinstance(node, scopes):
            node = parents.get(node)
        return node or tree

    for node in ast.walk(tree):
        scope = scope_of(parents.get(node, tree))
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for item in ast.walk(target):
                    if isinstance(item, ast.Name) and node.value is not None:
                        bindings.setdefault(scope, {}).setdefault(item.id, []).append(node.value)
        elif isinstance(node, ast.Import):
            for item in node.names:
                aliases.setdefault(scope, {})[item.asname or item.name.split(".")[0]] = item.name if item.asname else item.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            for item in node.names:
                aliases.setdefault(scope, {})[item.asname or item.name] = (node.module or "") + "." + item.name

    def lookup(node, name, table):
        scope = scope_of(node)
        while scope is not None:
            if name in table.get(scope, {}):
                return table[scope][name]
            scope = scope_of(parents[scope]) if scope in parents else None
        return None

    def reaches_retired(node, seen, pattern=RETIRED):
        if node in seen:
            return False
        seen.add(node)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return bool(pattern.search(node.value))
        if isinstance(node, ast.Name):
            return any(reaches_retired(value, seen, pattern) for value in lookup(node, node.id, bindings) or [])
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Div)):
            parts = [item.value for item in ast.walk(node) if isinstance(item, ast.Constant) and isinstance(item.value, str)]
            if pattern.search("".join(parts)) or pattern.search("/".join(parts)):
                return True
        return any(reaches_retired(child, seen, pattern) for child in ast.iter_child_nodes(node))

    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [item.name for item in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                package = path.removesuffix(".py").split("/")[:-1]
                module = ".".join(package[:len(package) - node.level + 1] + ([module] if module else []))
            names = [module, *(module + "." + item.name for item in node.names)]
        else:
            names = []
        if any(RETIRED.search(name) for name in names):
            found.add(Finding(path, node.lineno, "retired-import", "Import uses a retired overworld module."))
        if any(_DESMUME.search(name) for name in names):
            found.add(Finding(path, node.lineno, "retired-emulator-import", "Use the shared melonDS backend, not DeSmuME."))
        if not isinstance(node, ast.Call):
            continue
        name = _name(node.func)
        first, _, rest = name.partition(".")
        alias = lookup(node, first, aliases)
        if alias:
            name = alias + ("." + rest if rest else "")
        if not rest:
            assigned = lookup(node, first, bindings) or []
            for value in assigned:
                target = _name(value)
                prefix, _, suffix = target.partition(".")
                imported = lookup(value, prefix, aliases)
                target = imported + ("." + suffix if suffix else "") if imported else target
                if target.startswith(_PROCESS_PREFIXES) or target in _PROCESS_CALLS or target in _NATIVE_LOAD_CALLS or target.rsplit(".", 1)[-1] in _LOAD_CALLS:
                    name = target
                    break
        loader = name in {"exec", "compile", "__import__"} or (
            name.rsplit(".", 1)[-1] in _LOAD_CALLS - {"exec", "compile", "__import__"})
        if _DESMUME.search(name):
            found.add(Finding(path, node.lineno, "retired-emulator-execution", "Call uses the retired DeSmuME backend."))
        if not loader and not name.startswith(_PROCESS_PREFIXES) and name not in _PROCESS_CALLS and name not in _NATIVE_LOAD_CALLS:
            continue
        values = [*node.args, *(item.value for item in node.keywords)]
        if any(reaches_retired(value, set()) for value in values):
            found.add(Finding(path, node.lineno, "retired-execution", "Loader/process call reaches a retired overworld entry point."))
        if any(reaches_retired(value, set(), _DESMUME) for value in values):
            found.add(Finding(path, node.lineno, "retired-emulator-execution", "Loader/process call reaches the retired DeSmuME backend."))
    return sorted(found)


def audit_data(source: str, path: str) -> list[Finding]:
    # The active YAML feature manifest is JSON-compatible. Historical receipts
    # live elsewhere and are intentionally not selected by audit_repository.
    try:
        json.loads(source)
    except ValueError as error:
        return [Finding(path, 1, "invalid-registry", str(error))]
    return [Finding(path, line, "retired-runner", "Active scenario/registry names a retired execution route.")
            for line, text in enumerate(source.splitlines(), 1) if RETIRED.search(text)]


def audit_dependencies(source: str, path: str) -> list[Finding]:
    return [Finding(path, line, "retired-emulator-dependency", "Remove the retired DeSmuME package dependency.")
            for line, text in enumerate(source.splitlines(), 1)
            if not text.lstrip().startswith(("#", "//")) and _DESMUME.search(text)]


def audit_instructions(source: str, path: str) -> list[Finding]:
    found = []
    history = False
    history_heading = None
    paragraph = []

    def check_paragraph():
        if not paragraph:
            return
        text = " ".join(value for _, value in paragraph)
        # Negation applies only to the adjacent retirement instruction, not an
        # unrelated sentence elsewhere in this paragraph.
        def prohibited(match):
            prefix = re.split(r"[.!?;]\s+", text[:match.start()])[-1].replace("`", "")
            return not re.search(
                r"\b(?:do not|never|must not|cannot|no longer)\s+"
                r"(?:(?:use|run|call|load|import|launch|invoke|execute|retain|keep|restore|recommend)\s+)?"
                r"(?:(?:the|old|retired|legacy|script|module|entry|point|at)\s+)*$",
                prefix, re.IGNORECASE)
        matches = (match for rule in (RETIRED, _RETAINED_BACKEND, _KEYWORD_GATE) for match in rule.finditer(text))
        if any(prohibited(match) for match in matches):
            found.append(Finding(path, paragraph[0][0], "retired-instruction", "Active instructions recommend a retired overworld route or keyword gate."))
        paragraph.clear()

    for line, text in enumerate(source.splitlines(), 1):
        heading = re.match(r"^(#{1,6})\s+(.+)", text)
        if text.strip() in (HISTORY_START, HISTORY_END):
            check_paragraph()
            start = text.strip() == HISTORY_START
            if path != HISTORY_PATH or history == start:
                found.append(Finding(path, line, "invalid-history-boundary", "History markers are only valid, paired ledger sections."))
            history = start
            continue
        if heading:
            check_paragraph()
            level, title = len(heading[1]), heading[2]
            if history_heading is not None and level <= history_heading:
                history_heading = None
            if path == HISTORY_PATH and title.startswith("Historical "):
                history_heading = level
        if history or history_heading is not None:
            continue
        if not text.strip() or heading:
            check_paragraph()
        elif not text.lstrip().startswith("<!--"):
            paragraph.append((line, text.strip()))
    check_paragraph()
    if history:
        found.append(Finding(path, len(source.splitlines()), "invalid-history-boundary", "Unclosed history section could hide current instructions."))
    return found


def audit_repository(root: Path) -> dict:
    root = root.resolve()
    required = ("AGENTS.md", "scripts", "tools/overworld", "tests/overworld/scenarios")
    missing = [path for path in required if not (root / path).exists()]
    if missing:
        return {"passed": False, "checkedFiles": 0, "findings": [asdict(Finding(".", 1, "unexpected-target", "Missing repository inputs: " + ", ".join(missing)))]}
    found = [Finding(path, 1, "retired-file", "Retired executable/module still exists; remove it, not an alias.")
             for path in RETIRED_FILES if (root / path).exists() or (root / path).is_symlink()]
    checked = set()
    for folder in ("scripts", "tools"):
        files = []
        for directory, children, names in os.walk(root / folder):
            children[:] = sorted(name for name in children if name not in
                                 {".git", ".venv", "node_modules", "__pycache__", "build", "dist"})
            files.extend(Path(directory) / name for name in names)
        for file in sorted(files):
            if not file.is_file() or file.suffix not in (".py", ".sh", ".cmd", ".js", ".ts"):
                continue
            path = file.relative_to(root).as_posix()
            checked.add(path)
            if path in RETIRED_FILES:
                continue  # Existence already fails, regardless of its contents.
            source = file.read_text()
            if file.suffix == ".py":
                found.extend(audit_python(source, path))
            else:
                found.extend(Finding(path, line, "retired-execution", "Active shell/client source names a retired overworld route.")
                             for line, text in enumerate(source.splitlines(), 1)
                             if not text.lstrip().startswith(("#", "//")) and RETIRED.search(text))
                found.extend(Finding(path, line, "retired-emulator-execution", "Active shell/client source names the retired DeSmuME backend.")
                             for line, text in enumerate(source.splitlines(), 1)
                             if not text.lstrip().startswith(("#", "//")) and _DESMUME.search(text))
    dependencies = [*root.glob("requirements*.txt"), *root.glob("requirements/*.txt"),
                    *(root / name for name in ("pyproject.toml", "Pipfile", "Pipfile.lock", "poetry.lock", "uv.lock"))]
    for file in dependencies:
        if file.is_file():
            path = file.relative_to(root).as_posix()
            checked.add(path)
            found.extend(audit_dependencies(file.read_text(), path))
    records = [root / "tools/overworld/runtime_proof_registry.json", root / "tools/overworld/system_features.yaml",
               *sorted((root / "tests/overworld/scenarios").glob("*.json"))]
    for file in records:
        if file.is_file():
            path = file.relative_to(root).as_posix()
            checked.add(path)
            found.extend(audit_data(file.read_text(), path))
    docs = [root / "AGENTS.md", root / "README.md", *sorted((root / "documentation/overworld-system").rglob("*.md"))]
    for skill in SKILLS:
        docs.extend(sorted((root / ".agents/skills" / skill).rglob("*.md")))
    for file in docs:
        if file.is_file():
            path = file.relative_to(root).as_posix()
            checked.add(path)
            found.extend(audit_instructions(file.read_text(), path))
    return {"passed": not found, "checkedFiles": len(checked), "findings": [asdict(item) for item in sorted(set(found))]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = audit_repository(args.root)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for finding in report["findings"]:
            print(f'{finding["path"]}:{finding["line"]}: {finding["code"]}: {finding["message"]}')
        print(f'{"PASS" if report["passed"] else "FAIL"}: devtools-only retirement ({report["checkedFiles"]} files checked).')
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
