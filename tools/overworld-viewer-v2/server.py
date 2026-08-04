#!/usr/bin/env python3
"""Serve the standalone V2 frontend on the proven overworld data backend."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import re
import sys
from email import policy
from email.parser import BytesParser
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from urllib.parse import urlparse

from PIL import Image

import reliability
import pokemon_data
import pokemon_asset_writer


ROOT = Path(__file__).resolve().parents[2]
LEGACY_VIEWER_SOURCE = ROOT / "scripts/overworld_behavior_profile_viewer.py"
STATIC_DIR = Path(__file__).resolve().with_name("static")
BEHAVIOR_MODEL_SOURCE = ROOT / "data/OverworldWildBehaviorModelV40.json"

V2_ASSETS = {
    "/v2-assets/v2.css": (STATIC_DIR / "v2.css", "text/css; charset=utf-8"),
    "/v2-assets/v2.js": (STATIC_DIR / "v2.js", "application/javascript; charset=utf-8"),
    "/v2-assets/profiles.js": (STATIC_DIR / "profiles.js", "application/javascript; charset=utf-8"),
    "/v2-assets/model-validation.js": (STATIC_DIR / "model-validation.js", "application/javascript; charset=utf-8"),
    "/v2-assets/stack-preview.js": (STATIC_DIR / "stack-preview.js", "application/javascript; charset=utf-8"),
    "/v2-assets/routes.js": (STATIC_DIR / "routes.js", "application/javascript; charset=utf-8"),
    "/v2-assets/routes-sounds.js": (STATIC_DIR / "routes-sounds.js", "application/javascript; charset=utf-8"),
    "/v2-assets/pokemon.js": (STATIC_DIR / "pokemon.js", "application/javascript; charset=utf-8"),
    "/v2-assets/pokemon.css": (STATIC_DIR / "pokemon.css", "text/css; charset=utf-8"),
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


def build_behavior_model_editor_payload() -> dict[str, object]:
    """Join display data with the authored applicability rows needed by the writer."""

    payload = legacy.build_v40_state_profile_editor_data()
    authored = json.loads(BEHAVIOR_MODEL_SOURCE.read_text())
    applicability_keys = (
        "stableId", "name", "kind", "groupMask", "controllerId",
        "profileId", "minimum", "maximum", "flags",
    )
    applicability_rows = [
        {key: row[key] for key in applicability_keys if key in row}
        for row in authored.get("applicability", [])
    ]
    profile_delete_blockers: dict[str, list[dict[str, object]]] = {}
    for domain in ("importRecipes", "tiredTranslations"):
        for row in authored.get(domain, []):
            profile_id = row.get("profileId")
            if not profile_id:
                continue
            profile_delete_blockers.setdefault(str(profile_id), []).append({
                "domain": domain,
                "stableId": row.get("stableId"),
                "registryKey": row.get("registryKey", ""),
            })
    controller_delete_blockers: dict[str, list[dict[str, object]]] = {}

    def add_controller_blocker(controller_id: object, domain: str,
                               row: dict[str, object], **extra: object) -> None:
        if not controller_id:
            return
        controller_delete_blockers.setdefault(str(controller_id), []).append({
            "domain": domain,
            "stableId": row.get("stableId"),
            "registryKey": row.get("registryKey", ""),
            **extra,
        })

    for override in authored.get("overrides", []):
        for action in override.get("actions", []):
            payload_bytes = action.get("payload", [])
            if not isinstance(payload_bytes, list) or len(payload_bytes) != 8:
                continue
            kind = action.get("kind")
            offset = 6 if kind == 4 else 0 if kind in (2, 3, 11) else None
            if offset is None:
                continue
            controller_id = payload_bytes[offset] | (payload_bytes[offset + 1] << 8)
            add_controller_blocker(
                controller_id, "overrides", override,
                actionStableId=action.get("stableId"),
            )
    generated_definition_ids = {
        row.get("stableId") for row in authored.get("overrideDefinitions", [])
        if row.get("hasTiredOriginKind") or row.get("hasRequiredOwnerId")
    }
    for row in authored.get("overrideDefinitions", []):
        if row.get("stableId") in generated_definition_ids:
            add_controller_blocker(row.get("controllerId"), "overrideDefinitions", row)
    for domain in ("importRecipes", "tiredTranslations"):
        for row in authored.get(domain, []):
            add_controller_blocker(row.get("controllerId"), domain, row)
            add_controller_blocker(
                row.get("fallbackControllerId"), domain, row,
                reference="fallbackControllerId",
            )
    payload["behaviorModelAuthoring"] = {
        "applicability": applicability_rows,
        "profileDeleteBlockers": profile_delete_blockers,
        "controllerDeleteBlockers": controller_delete_blockers,
    }
    return payload


def render_normal_battle_palette(body: bytes, palette_path: Path | None) -> bytes:
    """Apply the normal front palette to indexed back-sprite pixels, as the game does."""

    if palette_path is None:
        return body
    try:
        with Image.open(io.BytesIO(body)) as sprite, Image.open(palette_path) as palette:
            normal_palette = palette.getpalette()
            if sprite.mode != "P" or palette.mode != "P" or normal_palette is None:
                return body
            rendered = sprite.copy()
            rendered.putpalette(normal_palette)
            output = io.BytesIO()
            transparency = sprite.info.get("transparency")
            options = {"transparency": transparency} if transparency is not None else {}
            rendered.save(output, format="PNG", **options)
            return output.getvalue()
    except (OSError, ValueError):
        return body


def parse_asset_stage_multipart(content_type: str, body: bytes) -> tuple[str, str, bytes]:
    if not content_type.lower().startswith("multipart/form-data"):
        raise ValueError("asset staging requires multipart/form-data")
    message = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: " + content_type.encode("ascii")
        + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
    )
    fields: dict[str, str] = {}
    upload: bytes | None = None
    seen_parts: set[str] = set()
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if name not in {"file", "symbol", "slot"}:
            raise ValueError("asset staging contains an unknown multipart field")
        if name in seen_parts:
            raise ValueError(f"asset staging contains duplicate {name} parts")
        seen_parts.add(name)
        if name == "file":
            upload = part.get_payload(decode=True)
            if part.get_filename() is None:
                raise ValueError("asset staging file part requires a filename")
        else:
            content = part.get_content()
            if not isinstance(content, str):
                raise ValueError(f"asset staging {name} must be text")
            fields[name] = content.strip()
    if upload is None or seen_parts != {"symbol", "slot", "file"} or set(fields) != {"symbol", "slot"}:
        raise ValueError("asset staging requires symbol, slot, and file")
    return fields["symbol"], fields["slot"], upload


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
            pokemon_icon_match = re.fullmatch(r"/icons/(\d+)\.png", path)
            if pokemon_icon_match:
                with reliability.workspace_guard(ROOT):
                    icon_path = pokemon_data.asset_path(
                        ROOT, int(pokemon_icon_match.group(1), 10), "icon"
                    )
                    body = legacy.render_icon_png(icon_path) if icon_path else None
                if icon_path is None:
                    self.send_bytes(
                        b"Pokemon icon not found\n",
                        "text/plain; charset=utf-8",
                        status=404,
                        cache_control="no-store",
                    )
                    return
                assert body is not None
                etag = f'"sha256:{hashlib.sha256(body).hexdigest()}"'
                if self.headers.get("If-None-Match") == etag:
                    self.send_not_modified(etag)
                    return
                self.send_bytes(body, "image/png", cache_control="no-cache", etag=etag)
                return
            pokemon_asset_match = re.fullmatch(
                r"/pokemon-assets/(\d+)/(male-front|female-front|male-back|female-back|follower)\.png",
                path,
            )
            if pokemon_asset_match:
                with reliability.workspace_guard(ROOT):
                    species_value = int(pokemon_asset_match.group(1), 10)
                    asset_kind = pokemon_asset_match.group(2)
                    asset_path = pokemon_data.asset_path(
                        ROOT,
                        species_value,
                        asset_kind,
                    )
                    body = asset_path.read_bytes() if asset_path else None
                    if body is not None and asset_kind in {"male-back", "female-back"}:
                        palette_path = pokemon_data.asset_path(
                            ROOT,
                            species_value,
                            "male-front" if asset_kind == "male-back" else "female-front",
                        )
                        body = render_normal_battle_palette(body, palette_path)
                if asset_path is None:
                    self.send_bytes(
                        b"Pokemon asset not found\n",
                        "text/plain; charset=utf-8",
                        status=404,
                        cache_control="no-store",
                    )
                    return
                assert body is not None
                etag = f'"sha256:{hashlib.sha256(body).hexdigest()}"'
                if self.headers.get("If-None-Match") == etag:
                    self.send_not_modified(etag)
                    return
                self.send_bytes(body, "image/png", cache_control="no-cache", etag=etag)
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
                    try:
                        behavior_model = legacy.build_v40_state_profile_editor_data()
                        payload["v40BehaviorModelCapability"] = {
                            "available": True,
                            "modelVersion": behavior_model["modelVersion"],
                            "stateProfileCount": len(behavior_model["stateProfiles"]),
                            "controllerCount": len(behavior_model["controllers"]),
                            "transitionCount": len(behavior_model["transitionGraph"]["transitions"]),
                        }
                    except Exception as exc:
                        # V40 model availability is independent from the route,
                        # sound, and Pokémon datasets used by the other decks.
                        payload["v40BehaviorModelCapability"] = {
                            "available": False,
                            "reason": str(exc),
                        }
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
                        "capabilities": legacy.source_capabilities(),
                    }
                )
                return
            if path == "/api/v2/behavior-model":
                with reliability.workspace_guard(ROOT):
                    payload = build_behavior_model_editor_payload()
                    payload["sourceRevision"] = reliability.current_revision(legacy, ROOT)
                    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                    etag = f'"sha256:{hashlib.sha256(body).hexdigest()}"'
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
            staged_asset_match = re.fullmatch(
                r"/api/v2/pokemon-assets/staged/([0-9a-f]{32})", path
            )
            if staged_asset_match:
                preview = pokemon_asset_writer.staged_preview(staged_asset_match.group(1))
                if preview is None:
                    self.send_json({"error": "staged asset is missing or expired"}, status=404)
                else:
                    body, symbol, slot = preview
                    if slot in {"maleBack", "femaleBack"}:
                        species_value = pokemon_asset_writer.species_values(ROOT).get(symbol)
                        palette_path = (
                            pokemon_data.asset_path(
                                ROOT,
                                species_value,
                                "male-front" if slot == "maleBack" else "female-front",
                            )
                            if species_value is not None
                            else None
                        )
                        body = render_normal_battle_palette(body, palette_path)
                    self.send_bytes(body, "image/png", cache_control="no-store")
                return
            if path == "/api/v2/pokemon-data":
                with reliability.workspace_guard(ROOT):
                    asset_snapshot = pokemon_data.asset_snapshot(ROOT)
                    cached_payload, source_revision = reliability.stable_source_read(
                        legacy,
                        ROOT,
                        lambda: pokemon_data.build_dataset(
                            ROOT, legacy, assets=asset_snapshot
                        ),
                        cache_key=f"pokemon-data:{asset_snapshot.revision}",
                    )
                    payload = dict(cached_payload)
                    payload["sourceRevision"] = source_revision
                    payload["optionRevision"] = source_revision
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
            if path == "/api/v2/pokemon-editor-options":
                with reliability.workspace_guard(ROOT):
                    asset_snapshot = pokemon_data.asset_snapshot(ROOT)
                    dataset, dataset_revision = reliability.stable_source_read(
                        legacy,
                        ROOT,
                        lambda: pokemon_data.build_dataset(
                            ROOT, legacy, assets=asset_snapshot
                        ),
                        cache_key=f"pokemon-data:{asset_snapshot.revision}",
                    )
                    cached_payload, source_revision = reliability.stable_source_read(
                        legacy,
                        ROOT,
                        lambda: pokemon_data.build_editor_options(
                            ROOT,
                            legacy,
                            assets=asset_snapshot,
                            dataset=dataset,
                        ),
                        cache_key=f"pokemon-editor-options:{asset_snapshot.revision}",
                    )
                    if source_revision != dataset_revision:
                        raise RuntimeError(
                            "Pokémon source revision changed between index and option reads"
                        )
                    payload = dict(cached_payload)
                    payload["sourceRevision"] = source_revision
                    payload["optionRevision"] = source_revision
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
            pokemon_detail_match = re.fullmatch(
                r"/api/v2/pokemon-data/(SPECIES_[A-Z0-9_]+)", path, re.IGNORECASE
            )
            if pokemon_detail_match:
                symbol = pokemon_detail_match.group(1).upper()
                with reliability.workspace_guard(ROOT):
                    asset_snapshot = pokemon_data.asset_snapshot(ROOT)
                    dataset, dataset_revision = reliability.stable_source_read(
                        legacy,
                        ROOT,
                        lambda: pokemon_data.build_dataset(
                            ROOT, legacy, assets=asset_snapshot
                        ),
                        cache_key=f"pokemon-data:{asset_snapshot.revision}",
                    )
                    cached_payload, source_revision = reliability.stable_source_read(
                        legacy,
                        ROOT,
                        lambda: pokemon_data.build_detail(
                            ROOT,
                            legacy,
                            symbol,
                            assets=asset_snapshot,
                            dataset=dataset,
                        ),
                        cache_key=f"pokemon-detail:{symbol}:{asset_snapshot.revision}",
                    )
                    if source_revision != dataset_revision:
                        raise RuntimeError(
                            "Pokémon source revision changed between index and detail reads"
                        )
                    payload = dict(cached_payload)
                    payload["sourceRevision"] = source_revision
                    payload["optionRevision"] = source_revision
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
            if path == "/api/v2/workspace-meta":
                with reliability.workspace_guard(ROOT):
                    payload = reliability.workspace_metadata(legacy, ROOT)
                self.send_json(payload)
                return
        except reliability.SourceReadConflict as exc:
            self.send_json({"error": str(exc), "code": "source_read_conflict"}, status=409)
            return
        except reliability.CapabilityUnavailable as exc:
            self.send_json(
                {
                    "error": str(exc),
                    "code": "capability_unavailable",
                    "capability": exc.capability,
                    "missingSources": exc.missing_sources,
                },
                status=409,
            )
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
        if path == "/api/v2/pokemon-assets/stage":
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length <= 0 or content_length > pokemon_asset_writer.MAX_ASSET_BYTES + 65536:
                    raise ValueError("asset staging request has an invalid size")
                content_type = self.headers.get("Content-Type", "")
                body = self.rfile.read(content_length)
                symbol, slot, upload = parse_asset_stage_multipart(content_type, body)
                with reliability.workspace_guard(ROOT):
                    source_revision = reliability.current_revision(legacy, ROOT)
                    expected_source = self.headers.get("If-Match")
                    if expected_source and expected_source != source_revision:
                        raise reliability.RevisionConflict(expected_source, source_revision)
                    asset_revision = pokemon_data.asset_snapshot(ROOT, force=True).revision
                    expected_asset = self.headers.get("X-Asset-Revision")
                    if expected_asset and expected_asset != asset_revision:
                        raise reliability.AssetRevisionConflict(expected_asset, asset_revision)
                    result = pokemon_asset_writer.stage_asset(
                        ROOT,
                        symbol,
                        slot,
                        upload,
                        source_revision=source_revision,
                        asset_revision=asset_revision,
                    )
                self.send_json(result)
            except reliability.AssetRevisionConflict as exc:
                self.send_json({"error": str(exc), "code": "asset_revision_conflict", "assetRevision": exc.current}, status=409)
            except reliability.RevisionConflict as exc:
                self.send_json({"error": str(exc), "code": "revision_conflict", "sourceRevision": exc.current}, status=409)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, status=400)
            except Exception as exc:
                self.send_json({"error": str(exc)}, status=500)
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
        except reliability.AssetRevisionConflict as exc:
            self.send_json(
                {
                    "error": str(exc),
                    "code": "asset_revision_conflict",
                    "expectedRevision": exc.expected,
                    "assetRevision": exc.current,
                },
                status=409,
            )
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
        except reliability.CapabilityUnavailable as exc:
            self.send_json(
                {
                    "error": str(exc),
                    "code": "capability_unavailable",
                    "capability": exc.capability,
                    "missingSources": exc.missing_sources,
                },
                status=409,
            )
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=400)
        except FileNotFoundError as exc:
            self.send_json({"error": str(exc)}, status=404)
        except Exception as exc:  # pragma: no cover - surfaced to the local browser
            self.send_json({"error": str(exc)}, status=500)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        match = re.fullmatch(r"/api/v2/pokemon-assets/staged/([0-9a-f]{32})", path)
        if match:
            self.send_json(
                {
                    "discarded": pokemon_asset_writer.discard_token(match.group(1)),
                    "stagingToken": match.group(1),
                }
            )
            return
        self.send_json({"error": "not found"}, status=404)


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
