#!/usr/bin/env python3
"""HTTP routing coverage for the retired flattened-profile surface."""

from __future__ import annotations

import http.client
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools/overworld-viewer-v2"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import server  # noqa: E402


class RetiredProfileHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.V2ViewerHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.host, cls.port = cls.httpd.server_address

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)

    def request(self, method: str, path: str, body: bytes | None = None):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=10)
        try:
            connection.request(
                method,
                path,
                body=body,
                headers={"Content-Type": "application/json"} if body is not None else {},
            )
            response = connection.getresponse()
            return response.status, response.read(), response.getheader("Content-Type")
        finally:
            connection.close()

    def test_v40_behavior_model_endpoint_succeeds(self):
        status, body, content_type = self.request("GET", "/api/v2/behavior-model")
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type or "")
        self.assertEqual(json.loads(body)["modelVersion"], 40)

    def test_flattened_resolver_endpoint_is_absent(self):
        status, _, _ = self.request("GET", "/api/v2/resolve?species=PIDGEY")
        self.assertEqual(status, 404)

    def test_flattened_profile_mutation_endpoints_are_absent(self):
        for path in (
            "/save-profiles",
            "/save-profile-memberships",
            "/manage-profiles",
            "/save-profile-overrides",
        ):
            with self.subTest(path=path):
                status, _, _ = self.request("POST", path, b"{}")
                self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
