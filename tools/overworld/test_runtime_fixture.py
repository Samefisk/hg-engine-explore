from __future__ import annotations

import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts import verify_overworld_runtime_fixture as runtime_fixture
from scripts.verify_overworld_runtime_fixture import (
    LINKED_OUTPUTS,
    PRODUCT_OUTPUTS,
    linked_output_check,
    product_output_check,
    runtime_runner_startup_check,
    stock_main_queue_probe_check,
)


def fixture_rom(payloads: dict[int, bytes]) -> bytes:
    overlay_count = max(payloads) + 1
    y9_offset = 0x200
    y9_size = overlay_count * 0x20
    fat_offset = y9_offset + y9_size
    fat_size = overlay_count * 8
    payload_offset = fat_offset + fat_size
    rom = bytearray(payload_offset + sum(len(data) for data in payloads.values()))
    struct.pack_into("<2I", rom, 0x48, fat_offset, fat_size)
    struct.pack_into("<2I", rom, 0x50, y9_offset, y9_size)
    cursor = payload_offset
    for overlay_id, data in payloads.items():
        struct.pack_into(
            "<8I",
            rom,
            y9_offset + overlay_id * 0x20,
            overlay_id,
            0x02000000,
            len(data),
            0,
            0,
            0,
            overlay_id,
            0,
        )
        struct.pack_into(
            "<2I",
            rom,
            fat_offset + overlay_id * 8,
            cursor,
            cursor + len(data),
        )
        rom[cursor:cursor + len(data)] = data
        cursor += len(data)
    return bytes(rom)


class StockMainQueueProbeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "fixture.nds"
        self.image = bytearray(0x1200)
        struct.pack_into("<4I", self.image, 0x20, 0x200, 0x02000800, 0x02000000, 0x1000)
        self.start = 0x200 + 0xDE8
        self.image[self.start:self.start + 8] = bytes.fromhex("a0 69 1e f0 49 fd 60 6a")

    def check(self, image):
        self.path.write_bytes(image)
        return stock_main_queue_probe_check(self.path)

    def test_exact_main_queue_return_is_authenticated(self):
        result = self.check(self.image)
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["returnAddress"], 0x02000DEE)

    def test_wrong_queue_call_or_return_instruction_is_rejected(self):
        for offset in (0, 2, 4, 6):
            with self.subTest(offset=offset):
                image = self.image.copy()
                image[self.start + offset] ^= 1
                self.assertFalse(self.check(image)["passed"])

    def test_truncated_header_or_arm9_extent_is_rejected(self):
        for length in (0x30, self.start + 4, len(self.image) - 1):
            with self.subTest(length=length):
                self.assertFalse(self.check(self.image[:length])["passed"])
        image = self.image.copy()
        struct.pack_into("<I", image, 0x28, 0x02000004)
        self.assertFalse(self.check(image)["passed"])


class ProductOutputIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        self.payloads = {
            output.overlay_id: f"{output.key}-current".encode("ascii")
            for output in PRODUCT_OUTPUTS
        }
        for output in PRODUCT_OUTPUTS:
            path = self.repo / output.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.payloads[output.overlay_id])
        self.rom = self.repo / "test.nds"
        self.rom.write_bytes(fixture_rom(self.payloads))
        sealed_outputs = {}
        for key, role, relative in LINKED_OUTPUTS:
            payload = f"{key}-current".encode("ascii")
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            sealed_outputs[role] = {
                "path": relative,
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        manifest = self.repo / "build/pokemon_move_history_capture_build.json"
        manifest.write_text(json.dumps({"outputs": sealed_outputs}))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_all_required_outputs_match_the_packaged_rom(self) -> None:
        result = product_output_check(self.rom, repo=self.repo)

        self.assertTrue(result["passed"])
        self.assertEqual(
            set(result["outputs"]),
            {output.key for output in PRODUCT_OUTPUTS},
        )
        self.assertTrue(
            all(record["matched"] for record in result["outputs"].values())
        )

    def test_one_stale_component_fails_closed(self) -> None:
        helper = next(output for output in PRODUCT_OUTPUTS if output.key == "helper")
        (self.repo / helper.path).write_bytes(b"stale-helper")

        result = product_output_check(self.rom, repo=self.repo)

        self.assertFalse(result["passed"])
        self.assertFalse(result["outputs"]["helper"]["matched"])
        self.assertIn(
            "helper: packaged overlay differs from built output",
            result["error"],
        )

    def test_all_runtime_linked_inputs_match_the_sealed_build(self) -> None:
        result = linked_output_check(repo=self.repo)

        self.assertTrue(result["passed"])
        self.assertEqual(
            set(result["outputs"]),
            {key for key, _role, _path in LINKED_OUTPUTS},
        )

    def test_one_stale_runtime_linked_input_fails_closed(self) -> None:
        key, _role, relative = next(
            item for item in LINKED_OUTPUTS if item[0] == "selectorLinked"
        )
        linked = self.repo / relative
        original = linked.read_bytes()
        linked.write_bytes(bytes([original[0] ^ 0xFF]) + original[1:])

        result = linked_output_check(repo=self.repo)

        self.assertFalse(result["passed"])
        self.assertFalse(result["outputs"][key]["matched"])

    def test_same_size_stale_descriptor_enum_swap_fails_closed(self) -> None:
        actor = b"actor-overlay-current"
        actor_path = self.repo / "build/output_overworld_actor_system_overlay.bin"
        actor_path.write_bytes(actor)
        descriptor_path = self.repo / "build/overworld-system.debug.json"
        stale = {
            "overlay": {
                "fileSize": len(actor),
                "sha256": hashlib.sha256(actor).hexdigest(),
            },
            "enums": {
                "OverworldActorRole": {
                    "OVERWORLD_ACTOR_ROLE_WILD": 3,
                    "OVERWORLD_ACTOR_ROLE_MOUNTED": 1,
                },
            },
        }
        current = {
            **stale,
            "enums": {
                "OverworldActorRole": {
                    "OVERWORLD_ACTOR_ROLE_WILD": 1,
                    "OVERWORLD_ACTOR_ROLE_MOUNTED": 3,
                },
            },
        }
        descriptor_path.write_text(json.dumps(stale))
        rom = self.repo / "descriptor.nds"
        rom.write_bytes(fixture_rom({158: actor}))

        def regenerate(command, **_kwargs):
            output = Path(command[command.index("--output") + 1])
            output.write_text(json.dumps(current))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with mock.patch.object(runtime_fixture, "REPO", self.repo), \
                mock.patch.object(runtime_fixture, "DEBUG_DESCRIPTOR", descriptor_path), \
                mock.patch.object(runtime_fixture, "ACTOR_OVERLAY", actor_path), \
                mock.patch.object(runtime_fixture.subprocess, "run", side_effect=regenerate):
            result = runtime_fixture.descriptor_check(rom)

        self.assertFalse(result["passed"])
        self.assertIn("product truth", result["error"])

    def test_complete_runner_startup_uses_isolated_live_import(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        with mock.patch.object(
            runtime_fixture.subprocess, "run", return_value=completed
        ) as run:
            result = runtime_runner_startup_check(repo=self.repo)

        self.assertTrue(result["passed"])
        command = run.call_args.args[0]
        self.assertEqual(command[0], str(self.repo / ".venv/bin/python3"))
        self.assertIn("-I", command)
        self.assertIn("devtools_engine.initialize(native)", command[-1])
        self.assertNotIn("verify_overworld_walk_runtime", command[-1])
        self.assertNotIn("runpy", command[-1])
        self.assertEqual(run.call_args.kwargs["cwd"], self.repo)

    def test_complete_runner_startup_fails_on_import_error(self) -> None:
        completed = SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="KeyError: missing linked symbol",
        )
        with mock.patch.object(
            runtime_fixture.subprocess, "run", return_value=completed
        ):
            result = runtime_runner_startup_check(repo=self.repo)

        self.assertFalse(result["passed"])
        self.assertIn("missing linked symbol", result["stderr"])


if __name__ == "__main__":
    unittest.main()
