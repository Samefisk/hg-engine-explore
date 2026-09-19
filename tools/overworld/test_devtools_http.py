"""Exercise the actual V2 routes with a fake session service, never a ROM."""

import http.client
from http.server import ThreadingHTTPServer
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from tools.overworld.devtools_contract import OPERATIONS


ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "tools/overworld-viewer-v2"


class FakeService:
    def __init__(self):
        self.calls = []
        self.artifacts = []

    def command(self, request):
        self.calls.append(request)
        return {"ok": True, "session": {"id": "fake-session"}, "result": {"op": request["op"]}}

    def status(self):
        return {"ok": True, "session": {"id": "fake-session"}, "result": {"frame": 14}}

    def artifact(self, path):
        self.artifacts.append(path)
        if path != "session-unit/screen.png":
            raise ValueError("invalid artifact")
        return b"fake-image-bytes", "image/png"


class DevtoolsHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use the real handler; only the native-session boundary is replaced.
        old_path = list(sys.path)
        sys.path.insert(0, str(V2))
        try:
            spec = importlib.util.spec_from_file_location("_devtools_http_test_server", V2 / "server.py")
            cls.module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = cls.module
            spec.loader.exec_module(cls.module)
        finally:
            sys.path[:] = old_path

        class QuietHandler(cls.module.V2ViewerHandler):
            def log_message(self, *args):
                pass

        cls.http = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(timeout=2)
        cls.module._DEVTOOLS_SERVICE = None

    def setUp(self):
        self.service = FakeService()
        self.module._DEVTOOLS_SERVICE = self.service
        self.fresh = mock.patch.object(self.module, "server_restart_required", return_value=False)
        self.fresh.start()
        self.addCleanup(self.fresh.stop)

    def call(self, path, request=None, *, raw=None, headers=None):
        connection = http.client.HTTPConnection(*self.http.server_address, timeout=4)
        try:
            method = "GET" if request is None and raw is None else "POST"
            body = json.dumps(request).encode() if request is not None else raw
            request_headers = {"Content-Type": "application/json"} if method == "POST" else {}
            request_headers.update(headers or {})
            connection.request(method, path, body=body, headers=request_headers)
            result = connection.getresponse()
            return result.status, dict(result.getheaders()), result.read()
        finally:
            connection.close()

    def test_actual_page_and_assets_are_served_without_starting_session(self):
        for path, expected in (("/devtools", b"Observed actors"),
                               ("/devtools/", b"Normal \xc2\xb7 no setup changes yet"),
                               ("/v2-assets/devtools.js", b"const API"),
                               ("/v2-assets/devtools.css", b".screen {")):
            with self.subTest(path=path):
                code, headers, body = self.call(path)
                self.assertEqual(code, 200)
                self.assertIn(expected, body)
                self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(self.service.calls, [])
        self.assertIn('href="/devtools"', (V2 / "static/index.html").read_text())

    def test_status_reads_cached_service_and_preserves_frame(self):
        code, _, body = self.call("/api/v2/devtools/status")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["result"]["frame"], 14)
        self.assertEqual(self.service.calls, [])

    def test_actual_ui_setup_gate_allows_ready_normal_and_prepared_sessions(self):
        source = (V2 / "static/devtools.js").read_text()
        expression = re.search(r"fieldset\.disabled = ([^;]+);", source).group(1)
        # Execute the actual UI binding expression, not a second Python policy.
        script = "const disabled = new Function('state', 'session', 'testActive', 'return ' + " + json.dumps(expression) + ");\n"
        script += """
const cases = [
  [false, {mode:'normal', state:'ready'}, false],
  [false, {mode:'prepared', state:'ready'}, false],
  [true, {mode:'normal', state:'ready'}, true],
  [true, {mode:'prepared', state:'ready'}, true],
  [false, null, true],
  [false, {mode:'normal', state:'starting'}, true],
  [false, {mode:'prepared', state:'stopped'}, true],
];
for (const [busy, session, expected] of cases) {
  if (disabled({busy}, session, () => false) !== expected) throw new Error(JSON.stringify({busy, session, expected}));
}
if (!disabled({busy:false}, {state:'ready'}, () => true)) throw new Error('checked test owns setup');
"""
        result = subprocess.run(["node", "-e", script], text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def run_ui_bindings(self, mode):
        result = subprocess.run([
            "node", str(ROOT / "tools/overworld/fixtures/devtools_ui_harness.js"),
            str(V2 / "static/devtools.js"), str(V2 / "static/devtools.html"), mode,
        ], text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_capture_response_and_cli_cached_status_update_actual_image_binding(self):
        self.run_ui_bindings("capture")

    def test_actions_and_keyboard_only_capture_on_explicit_click(self):
        self.run_ui_bindings("manual-capture-only")

    def test_page_status_play_and_timers_never_request_images(self):
        self.run_ui_bindings("no-timer-capture")

    def test_checked_status_and_cancel_bypass_busy_game_request_and_preserve_exact_run(self):
        self.run_ui_bindings("checked-tests")

    def test_checked_file_forms_and_unknown_start_have_no_automatic_mutation_retries(self):
        self.run_ui_bindings("checked-test-files")

    def test_checked_poll_follows_current_job_and_explicit_history_cannot_cancel_it(self):
        self.run_ui_bindings("checked-current-history")

    def test_read_only_insights_bind_exact_subject_and_keep_snapshot_clocks_separate(self):
        self.run_ui_bindings("insight-controls")

    def test_pause_and_stop_queue_behind_actual_capture_handler_and_keep_unknown_receipts(self):
        self.run_ui_bindings("priority-controls")

    def test_capture_caption_compares_against_last_observed_not_current_frame(self):
        self.run_ui_bindings("caption-order")

    def test_session_change_clears_old_command_context_and_keeps_new_session_errors(self):
        self.run_ui_bindings("session-change")

    def test_default_inspector_is_compact_and_raw_json_is_lazy(self):
        self.run_ui_bindings("compact")

    def test_active_unverified_actor_can_be_inspected_without_changing_identity(self):
        self.run_ui_bindings("invalid-actor")

    def test_draft_sends_exact_fresh_selected_subject_and_rejects_stale_selection(self):
        self.run_ui_bindings("draft-subject")

    def test_player_and_warp_markers_use_only_the_terrain_sample_coordinates(self):
        self.run_ui_bindings("terrain-markers")

    def test_spawn_and_party_numeric_fields_match_the_shared_contract(self):
        class FormFields(HTMLParser):
            def __init__(self):
                super().__init__()
                self.form = None
                self.fields = {}

            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if tag == "form":
                    self.form = values.get("id")
                if tag == "input" and self.form:
                    self.fields[(self.form, values.get("name"))] = values

            def handle_endtag(self, tag):
                if tag == "form":
                    self.form = None

        document = FormFields()
        document.feed((V2 / "static/devtools.html").read_text())
        for form, operation in (("spawnForm", "spawn"), ("partyForm", "party")):
            for field in ("species", "form"):
                with self.subTest(form=form, field=field):
                    actual = document.fields[(form, field)]
                    expected = OPERATIONS[operation][field]
                    self.assertEqual(actual["type"], "number")
                    self.assertEqual(int(actual["min"]), expected["minimum"])
                    self.assertEqual(int(actual["max"]), expected["maximum"])
        source = (V2 / "static/devtools.js").read_text()
        numeric = json.loads(re.search(r"NUMERIC_FIELDS = new Set\((\[[^\]]+\])\)", source).group(1))
        self.assertIn("form", numeric)

    def test_command_forwards_exact_envelope_and_result(self):
        envelope = {"op": "step", "args": {"frames": 8, "keys": ["UP"]}, "requestId": "input-1"}
        code, _, body = self.call("/api/v2/devtools", envelope)
        self.assertEqual(code, 200)
        self.assertEqual(self.service.calls, [envelope])
        self.assertEqual(json.loads(body)["result"], {"op": "step"})

    def test_invalid_envelopes_never_reach_service(self):
        cases = ((b"[]", {}), (b"{", {}), (b"{}", {"Content-Type": "text/plain"}),
                 (b"{}", {"Content-Length": str(1024 * 1024 + 1)}))
        for raw, headers in cases:
            with self.subTest(raw=raw, headers=headers):
                code, _, body = self.call("/api/v2/devtools", raw=raw, headers=headers)
                self.assertEqual(code, 400)
                self.assertFalse(json.loads(body)["ok"])
        self.assertEqual(self.service.calls, [])

    def test_other_origin_is_rejected_and_same_origin_is_allowed(self):
        code, _, _ = self.call("/api/v2/devtools", {"op": "start"}, headers={"Origin": "https://example.invalid"})
        self.assertEqual(code, 403)
        self.assertEqual(self.service.calls, [])
        origin = "http://%s:%s" % self.http.server_address
        code, _, _ = self.call("/api/v2/devtools", {"op": "status"}, headers={"Origin": origin})
        self.assertEqual(code, 200)

    def test_nonlocal_peer_is_rejected_even_without_origin(self):
        fake = mock.Mock(client_address=("192.0.2.5", 32100), headers={})
        self.assertFalse(self.module.V2ViewerHandler.devtools_request_allowed(fake))
        self.assertEqual(fake.send_json.call_args.kwargs["status"], 403)

    def test_changed_server_blocks_new_work_but_keeps_stop_and_status(self):
        with mock.patch.object(self.module, "server_restart_required", return_value=True):
            code, _, body = self.call("/api/v2/devtools", {"op": "step", "args": {"frames": 1}})
            self.assertEqual(code, 409)
            self.assertEqual(json.loads(body)["error"]["code"], "server_restart_required")
            for op in ("status", "stop", "help", "test.status", "test.cancel", "test.export", "compare"):
                self.assertEqual(self.call("/api/v2/devtools", {"op": op})[0], 200)
        self.assertEqual([call["op"] for call in self.service.calls], ["status", "stop", "help", "test.status", "test.cancel", "test.export", "compare"])

    def test_new_devtools_module_changes_real_dynamic_revision_and_blocks_new_work(self):
        # Use real source discovery + hashing + HTTP freshness checks. All
        # source-file mutations stay in a temporary tree; no core is opened.
        self.fresh.stop()
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(self.module, "ROOT", Path(directory)):
            root = Path(directory)
            package = root / "tools/overworld"
            package.mkdir(parents=True)
            module = package / "devtools_new_observation.py"
            baseline = self.module.server_code_revision()
            with mock.patch.object(self.module, "SERVER_CODE_REVISION", baseline):
                self.assertFalse(self.module.server_restart_required())
                module.write_text("OBSERVATION_VERSION = 1\n")
                self.assertIn("tools/overworld/devtools_new_observation.py", self.module.devtools_source_paths(root))
                added = self.module.server_code_revision()
                self.assertNotEqual(added, baseline, "new modules must not be omitted by a fixed import-time input list")
                self.assertTrue(self.module.server_restart_required())
                code, _, body = self.call("/api/v2/devtools", {"op": "step", "args": {"frames": 1}})
                self.assertEqual(code, 409)
                self.assertEqual(json.loads(body)["error"]["code"], "server_restart_required")
                self.assertEqual(self.service.calls, [], "changed code must not dispatch new game work")
                for operation in ("test.status", "test.cancel", "test.export", "stop"):
                    self.assertEqual(self.call("/api/v2/devtools", {"op": operation})[0], 200)
                # Equal-size content changes must alter the digest too.
                module.write_text("OBSERVATION_VERSION = 2\n")
                self.assertNotEqual(self.module.server_code_revision(), added)
                module.unlink()
                self.assertEqual(self.module.server_code_revision(), baseline)
                (package / "test_new_observation.py").write_text("# host fixture, not loaded service code\n")
                self.assertEqual(self.module.server_code_revision(), baseline)

    def test_artifact_lookup_is_delegated_to_containment_guard(self):
        code, headers, body = self.call("/api/v2/devtools/artifacts/session-unit/screen.png")
        self.assertEqual((code, headers["Content-Type"], body), (200, "image/png", b"fake-image-bytes"))
        code, _, _ = self.call("/api/v2/devtools/artifacts/session-unit/%2E%2E/game.sav")
        self.assertEqual(code, 400)
        self.assertEqual(self.service.artifacts[-1], "session-unit/../game.sav")

    def test_restart_stops_only_this_services_session(self):
        with mock.patch.object(self.module.legacy, "restart_server_soon", return_value={"restarting": True}), \
                mock.patch.object(self.module.reliability, "begin_restart"):
            code, _, _ = self.call("/restart-server", {})
        self.assertEqual(code, 200)
        self.assertEqual([call["op"] for call in self.service.calls], ["stop"])


if __name__ == "__main__":
    unittest.main()
