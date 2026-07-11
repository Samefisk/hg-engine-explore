#!/usr/bin/env python3
"""Serve the standalone V2 frontend on the proven overworld data backend."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from urllib.parse import parse_qs, urlparse

import reliability


ROOT = Path(__file__).resolve().parents[2]
LEGACY_VIEWER_SOURCE = ROOT / "scripts/overworld_behavior_profile_viewer.py"
STATIC_DIR = Path(__file__).resolve().with_name("static")

V2_ASSETS = {
    "/v2-assets/v2.css": (STATIC_DIR / "v2.css", "text/css; charset=utf-8"),
    "/v2-assets/v2.js": (STATIC_DIR / "v2.js", "application/javascript; charset=utf-8"),
    "/v2-assets/profiles.js": (STATIC_DIR / "profiles.js", "application/javascript; charset=utf-8"),
    "/v2-assets/routes.js": (STATIC_DIR / "routes.js", "application/javascript; charset=utf-8"),
    "/v2-assets/routes-sounds.js": (STATIC_DIR / "routes-sounds.js", "application/javascript; charset=utf-8"),
}


def load_legacy_viewer() -> ModuleType:
    """Load the existing viewer as a backend module without changing it."""

    module_name = "_hg_engine_overworld_behavior_profile_viewer"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing

    spec = importlib.util.spec_from_file_location(module_name, LEGACY_VIEWER_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load legacy viewer: {LEGACY_VIEWER_SOURCE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


legacy = load_legacy_viewer()


class V2ViewerHandler(legacy.ViewerHandler):
    """Serve the new frontend while preserving every legacy backend endpoint."""

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path in ("/", "/index.html"):
                self.send_bytes(
                    (STATIC_DIR / "index.html").read_bytes(),
                    "text/html; charset=utf-8",
                    cache_control="no-store",
                )
                return
            if path in V2_ASSETS:
                asset_path, content_type = V2_ASSETS[path]
                try:
                    body = asset_path.read_bytes()
                except FileNotFoundError:
                    self.send_bytes(
                        b"V2 asset not found\n",
                        "text/plain; charset=utf-8",
                        status=404,
                        cache_control="no-store",
                    )
                    return
                self.send_bytes(body, content_type, cache_control="no-store")
                return
            if path == "/data.json":
                with reliability.workspace_guard(ROOT):
                    cached, source_revision = reliability.stable_source_read(
                        legacy,
                        ROOT,
                        legacy.cached_data_json,
                        cache_key="data-json",
                        refresh_legacy_cache=True,
                    )
                    payload = json.loads(cached["body"])
                    payload["sourceRevision"] = source_revision
                    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                    etag = f'"{hashlib.sha1(body).hexdigest()}"'
                if self.headers.get("If-None-Match") == etag:
                    self.send_not_modified(etag)
                    return
                accepts_gzip = "gzip" in self.headers.get("Accept-Encoding", "")
                self.send_bytes(
                    gzip.compress(body, compresslevel=6) if accepts_gzip else body,
                    "application/json; charset=utf-8",
                    cache_control="no-cache",
                    content_encoding="gzip" if accepts_gzip else None,
                    etag=etag,
                    vary="Accept-Encoding",
                )
                return
            if path == "/api/v2/health":
                self.send_json(
                    {
                        "ok": True,
                        "service": "overworld-viewer-v2",
                        "apiVersion": 2,
                        "legacyBackend": str(LEGACY_VIEWER_SOURCE.relative_to(ROOT)),
                    }
                )
                return
            if path == "/api/v2/workspace-meta":
                with reliability.workspace_guard(ROOT):
                    payload = reliability.workspace_metadata(legacy, ROOT)
                self.send_json(payload)
                return
            if path == "/api/v2/resolve":
                query = parse_qs(urlparse(self.path).query)
                with reliability.workspace_guard(ROOT):
                    payload, source_revision = reliability.stable_source_read(
                        legacy,
                        ROOT,
                        lambda: reliability.resolve_context(
                            legacy,
                            (query.get("species") or [""])[0],
                            (query.get("level") or [None])[0],
                            (query.get("terrain") or [None])[0],
                            (query.get("shiny") or [None])[0],
                        ),
                    )
                    payload["sourceRevision"] = source_revision
                self.send_json(payload)
                return
        except reliability.SourceReadConflict as exc:
            self.send_json({"error": str(exc), "code": "source_read_conflict"}, status=409)
            return
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=400)
            return
        except Exception as exc:  # pragma: no cover - surfaced to the local browser
            self.send_json({"error": str(exc)}, status=500)
            return

        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/restart-server":
            with reliability.workspace_guard(ROOT):
                reliability.begin_restart()
                result = legacy.restart_server_soon()
            self.send_json(result)
            return
        if path not in reliability.MUTATION_HANDLERS and path not in {"/api/v2/commit", "/build"}:
            super().do_POST()
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)
            if path == "/build":
                payload = json.loads(body.decode("utf-8") or "{}")
                result = reliability.start_build_job(
                    legacy, ROOT, bool(payload.get("runAfter"))
                )
            elif path == "/api/v2/commit":
                result = reliability.transactional_commit(legacy, ROOT, body)
            else:
                expected_revision = self.headers.get("If-Match")
                result = reliability.transactional_mutation(
                    legacy, ROOT, path, body, expected_revision
                )
            self.send_json(result)
        except reliability.RevisionConflict as exc:
            self.send_json(
                {
                    "error": str(exc),
                    "code": "revision_conflict",
                    "expectedRevision": exc.expected,
                    "sourceRevision": exc.current,
                },
                status=409,
            )
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=400)
        except FileNotFoundError as exc:
            self.send_json({"error": str(exc)}, status=404)
        except Exception as exc:  # pragma: no cover - surfaced to the local browser
            self.send_json({"error": str(exc)}, status=500)


def serve(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), V2ViewerHandler)
    actual_host, actual_port = server.server_address
    print(f"Overworld viewer V2: http://{actual_host}:{actual_port}")
    server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind")
    parser.add_argument("--port", type=int, default=8766, help="port to bind; use 0 for any free port")
    args = parser.parse_args(argv)
    serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
