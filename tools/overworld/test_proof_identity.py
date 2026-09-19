"""Host checks for content identity and immutable proof records, not gameplay."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import pokemon_move_history_build_manifest as build_manifest
from tools.overworld import runs
from tools.overworld.validation import ValidationFailure


class ProofContentIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="ow-proof-identity-")
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.git("init", "-q")
        self.git("config", "user.email", "identity-test@example.invalid")
        self.git("config", "user.name", "Proof identity test")
        self.write(".gitignore", "build/\n__pycache__/\n*.pyc\n")
        self.write("src/movement.c", "int movement = 1;\n")
        self.write("Makefile", "test.nds: src/movement.c\n\t@true\n")
        self.write("tests/overworld/scenarios/walk.json", '{"frames": 8}\n')
        self.write("documentation/overworld-system/roadmap-progress.md", "Open\n")
        self.git("add", ".")
        self.git("commit", "-qm", "initial content")

    def git(self, *arguments: str, repo: Path | None = None) -> str:
        return subprocess.check_output(
            ["git", *arguments], cwd=repo or self.repo, text=True,
            stderr=subprocess.STDOUT,
        ).strip()

    def write(self, relative: str, content: str) -> Path:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_docs_and_work_log_do_not_change_content_identity(self) -> None:
        before = runs.source_record(self.repo)
        self.write("documentation/overworld-system/roadmap-progress.md", "Done\n")
        self.write("AGENTS.md", "Read the work log.\n")
        self.write(".agents/skills/verify-overworld/SKILL.md", "Updated instructions\n")
        self.write("documentation/evidence.png", "documentation-only image\n")
        self.assertEqual(runs.source_record(self.repo), before)
        self.assertTrue(runs.git_provenance(self.repo)["dirty"])

    def test_content_preserving_commit_changes_provenance_not_identity(self) -> None:
        self.write("src/movement.c", "int movement = 2;\n")
        before = runs.source_record(self.repo)
        provenance = runs.git_provenance(self.repo)
        self.git("add", "src/movement.c")
        self.git("commit", "-qm", "record the already tested content")
        self.assertEqual(runs.source_record(self.repo), before)
        self.assertNotEqual(runs.git_provenance(self.repo)["revision"], provenance["revision"])
        self.assertFalse(runs.git_provenance(self.repo)["dirty"])

    def test_docs_commit_does_not_change_content_identity(self) -> None:
        before = runs.source_record(self.repo)
        self.write("documentation/overworld-system/roadmap-progress.md", "Done\n")
        self.git("commit", "-am", "record test result", "-q")
        self.assertEqual(runs.source_record(self.repo), before)

    def test_product_change_invalidates_and_exact_revert_restores(self) -> None:
        before = runs.source_record(self.repo)
        self.write("src/movement.c", "int movement = 3;\n")
        self.assertNotEqual(runs.source_record(self.repo), before)
        self.write("src/movement.c", "int movement = 1;\n")
        self.assertEqual(runs.source_record(self.repo), before)

    def test_untracked_source_counts_before_and_after_commit(self) -> None:
        before = runs.source_record(self.repo)
        self.write("src/new-motion.c", "int motion = 8;\n")
        untracked = runs.source_record(self.repo)
        self.assertNotEqual(untracked, before)
        self.git("add", "src/new-motion.c")
        self.git("commit", "-qm", "record new motion")
        self.assertEqual(runs.source_record(self.repo), untracked)

    def test_deleted_source_invalidates_before_and_after_commit(self) -> None:
        before = runs.source_record(self.repo)
        (self.repo / "src/movement.c").unlink()
        deleted = runs.source_record(self.repo)
        self.assertNotEqual(deleted, before)
        self.git("add", "-u")
        self.git("commit", "-qm", "record deletion")
        self.assertEqual(runs.source_record(self.repo), deleted)

    def test_proof_script_scenario_and_build_settings_are_inputs(self) -> None:
        for relative in (
            "tools/overworld/observer.py", "scripts/verify_overworld_walk_runtime.py",
            "tests/overworld/scenarios/walk.json", "Makefile", "overlays.mk",
            "data/overworld_behavior_profiles.json", "tools/source/generator.c",
        ):
            with self.subTest(path=relative):
                before = runs.source_record(self.repo)
                self.write(relative, "changed input\n")
                self.assertNotEqual(runs.source_record(self.repo), before)

    def test_build_outputs_caches_and_user_save_backup_are_not_inputs(self) -> None:
        before = runs.source_record(self.repo)
        for relative in (
            "build/overworld-runs/result.json", "build/actor.bin",
            "tools/overworld/__pycache__/observer.pyc", "test.nds",
            "test.sav.before-repair.bak", "test.dsv.backup",
        ):
            self.write(relative, "generated or user data\n")
        self.assertEqual(runs.source_record(self.repo), before)

    def test_executable_mode_is_an_input(self) -> None:
        path = self.write("scripts/owctl", "#!/bin/sh\n")
        path.chmod(0o644)
        before = runs.source_record(self.repo)
        path.chmod(0o755)
        self.assertNotEqual(runs.source_record(self.repo), before)

    def test_symlink_target_and_content_are_inputs(self) -> None:
        target = self.write("src/other.c", "int other = 1;\n")
        link = self.repo / "src/linked.c"
        link.symlink_to("movement.c")
        before = runs.source_record(self.repo)
        link.unlink()
        link.symlink_to(target.name)
        self.assertNotEqual(runs.source_record(self.repo), before)
        linked = runs.source_record(self.repo)
        target.write_text("int other = 2;\n")
        self.assertNotEqual(runs.source_record(self.repo), linked)

    def test_outside_repository_symlink_fails_closed(self) -> None:
        (self.repo / "src/external.c").symlink_to("/dev/null")
        with self.assertRaisesRegex(ValidationFailure, "leaves repository"):
            runs.source_record(self.repo)

    def test_submodule_worktree_content_not_commit_is_bound(self) -> None:
        nested = self.repo / "tools/source/example"
        nested.mkdir(parents=True)
        self.git("init", "-q", repo=nested)
        self.git("config", "user.email", "identity-test@example.invalid", repo=nested)
        self.git("config", "user.name", "Proof identity test", repo=nested)
        (nested / "tool.c").write_text("int tool = 1;\n")
        self.git("add", ".", repo=nested)
        self.git("commit", "-qm", "tool", repo=nested)
        revision = self.git("rev-parse", "HEAD", repo=nested)
        self.git("update-index", "--add", "--cacheinfo", "160000", revision, "tools/source/example")
        before = runs.source_record(self.repo)
        (nested / "tool.c").write_text("int tool = 2;\n")
        changed = runs.source_record(self.repo)
        self.assertNotEqual(changed, before)
        self.git("commit", "-qam", "record tool content", repo=nested)
        self.assertEqual(runs.source_record(self.repo), changed)

    def test_failed_scan_is_not_an_empty_clean_record(self) -> None:
        failure = subprocess.CompletedProcess(["git"], 1, b"", b"index unreadable")
        with mock.patch.object(runs.subprocess, "run", return_value=failure):
            with self.assertRaisesRegex(ValidationFailure, "proof input scan failed"):
                runs.source_record(self.repo)

    def test_non_repository_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValidationFailure):
                runs.source_record(Path(directory))

    def test_file_disappearing_after_scan_fails_closed(self) -> None:
        real_record = runs._input_record

        def disappear(repo: Path, relative: Path):
            if relative.as_posix() == "src/movement.c":
                (repo / relative).unlink()
            return real_record(repo, relative)

        with mock.patch.object(runs, "_input_record", side_effect=disappear):
            with self.assertRaisesRegex(ValidationFailure, "could not be read"):
                runs.source_record(self.repo)

    def test_path_added_during_scan_fails_closed(self) -> None:
        real_record = runs._input_record

        def add_input(repo: Path, relative: Path):
            self.write("src/late.c", "int late = 1;\n")
            return real_record(repo, relative)

        with mock.patch.object(runs, "_input_record", side_effect=add_input):
            with self.assertRaisesRegex(ValidationFailure, "path set changed"):
                runs.source_record(self.repo)

    def test_manifest_keeps_git_provenance_outside_reusable_identity(self) -> None:
        with mock.patch.object(runs, "emulator_record", return_value={"present": False}):
            document = runs.make_run_manifest(
                repo=self.repo, kind="scenario", target="walk", proof_level="S1",
                cost_tier=1, scenario=None, commands=[], results=[{"passed": True}],
                started_at="2026-09-05T12:00:00Z",
            )
        self.assertEqual(document["schema"], "overworld-system-run-v4")
        self.assertIn("gitProvenance", document)
        self.assertNotIn("revision", document["identity"]["source"])
        self.assertEqual(document["identity"]["source"]["schema"], runs.SOURCE_SCHEMA)

    def test_sealed_fixture_content_check_survives_docs_and_commits_but_not_product_edits(self) -> None:
        # Exercise the exact content validator called by runtime preflight.
        # These tiny inputs are not a ROM gameplay fixture or package proof.
        inputs = {"src/movement.c", "Makefile"}
        rom = self.write("test.nds", "test package bytes\n")
        document = {
            "schema": build_manifest.SCHEMA,
            "build_context": {}, "tools": {},
            "runtime_environment": build_manifest.unbound_runtime_environment(),
            "inputs": {
                relative: build_manifest.file_record(self.repo / relative)
                for relative in inputs
            },
            "outputs": {"packaged_rom": {
                "path": build_manifest.PACKAGED_ROM_LOGICAL_PATH,
                **build_manifest.file_record(rom),
            }},
        }

        def verify() -> None:
            build_manifest.verify_manifest_document(
                document, self.repo, inputs, {}, rom, set(), set(),
            )

        verify()
        self.write("documentation/overworld-system/roadmap-progress.md", "Test passed.\n")
        verify()
        self.git("add", "documentation")
        self.git("commit", "-qm", "record proof without changing product")
        verify()
        self.write("src/movement.c", "int movement = 4;\n")
        with self.assertRaisesRegex(build_manifest.ManifestError, "content hash differs"):
            verify()

    def test_fixed_build_input_set_has_no_design_or_work_log_files(self) -> None:
        self.assertFalse([
            relative for relative in build_manifest.FIXED_INPUTS
            if Path(relative).suffix == ".md"
            or Path(relative).parts[0] in {"documentation", "docs", "Design Documents"}
        ])

    def test_resident_occupancy_code_and_guard_are_sealed_build_inputs(self) -> None:
        # This code moved out of Wild; hashing only its former owner is stale.
        for relative in (
            "src/pokemon_move_history_overlay/overworld_wild_occupancy.c",
            "include/overworld_wild_occupancy.h",
            "scripts/verify_overworld_wild_occupancy.py",
        ):
            self.assertIn(relative, build_manifest.FIXED_INPUTS)
        self.assertIn(
            "build/pokemon_move_history_overlay/overworld_wild_occupancy.d",
            build_manifest.DEPENDENCY_FILES,
        )
        self.assertEqual(
            build_manifest.OUTPUTS["wild_occupancy_object"],
            "build/pokemon_move_history_overlay/overworld_wild_occupancy.o",
        )


class ImmutableRunManifestTests(unittest.TestCase):
    def test_same_record_is_idempotent_but_different_record_cannot_replace_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            document = {
                "identity": {"target": "walk"}, "runId": "123",
                "startedAtUtc": "2026-09-05T12:00:00Z", "passed": False,
            }
            for output in (None, Path("custom-proof.json")):
                with self.subTest(output=output):
                    path = runs.write_run_manifest(document, repo, output)
                    original = path.read_bytes()
                    self.assertEqual(runs.write_run_manifest(document, repo, output), path)
                    with self.assertRaisesRegex(ValidationFailure, "already exists"):
                        runs.write_run_manifest({**document, "passed": True}, repo, output)
                    self.assertEqual(path.read_bytes(), original)
                    self.assertFalse(json.loads(original)["passed"])


if __name__ == "__main__":
    unittest.main()
