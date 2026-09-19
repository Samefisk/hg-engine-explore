"""Cheap receipt summaries and explicit non-product failure dispositions.

Nothing here starts the game, a compiler, or a verifier. Recorded passes are
not acceptance; the full roadmap gate rechecks evidence and build identity.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

from tools.overworld.runs import RUN_SCHEMA, digest_value, file_record, run_id_for, utc_now
from tools.overworld.validation import ValidationFailure

DISPOSITIONS = Path("documentation/overworld-system/failure-dispositions.json")


def _file_shape(record: Any) -> bool:
    if (not isinstance(record, dict) or not isinstance(record.get("path"), str)
            or not record["path"] or type(record.get("present")) is not bool):
        return False
    if not record["present"]:
        return record.get("size") is None and record.get("sha256") is None
    digest = record.get("sha256")
    return (type(record.get("size")) is int and record["size"] >= 0
            and isinstance(digest, str) and len(digest) == 64
            and all(character in "0123456789abcdef" for character in digest))


def read_manifest(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text())
    except ValueError as error:
        raise ValidationFailure("manifest JSON is invalid") from error
    if not isinstance(document, dict) or document.get("schema") != RUN_SCHEMA:
        raise ValidationFailure("manifest schema is not current")
    identity, result = document.get("identity"), document.get("result")
    if (not isinstance(identity, dict) or not isinstance(result, dict)
            or not isinstance(identity.get("target"), str)
            or not isinstance(identity.get("kind"), str)
            or type(result.get("passed")) is not bool
            or not isinstance(result.get("steps"), list) or not result["steps"]):
        raise ValidationFailure("manifest identity or result shape is invalid")
    if any(isinstance(value, dict) and "path" in value and not _file_shape(value)
           for value in identity.values()):
        raise ValidationFailure("manifest file identity shape is invalid")
    for step in result["steps"]:
        if not isinstance(step, dict) or type(step.get("passed")) is not bool:
            raise ValidationFailure("manifest step shape is invalid")
        if "proofClaims" in step and not isinstance(step["proofClaims"], dict):
            raise ValidationFailure("manifest claim shape is invalid")
        elapsed = step.get("elapsedSeconds", 0)
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValidationFailure("manifest duration is invalid")
    try:
        run_id, result_hash = run_id_for(document["identity"], document["result"],
                                       document["proofLevel"], document["costTier"])
    except (KeyError, TypeError) as error:
        raise ValidationFailure("manifest is incomplete") from error
    if document.get("runId") != run_id or document.get("resultSha256") != result_hash:
        raise ValidationFailure("manifest receipt differs from its digest")
    return document


def shared_history(repo: Path, scenarios: dict[str, Any], source: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read shared job receipts without issuing new acceptance or running checks."""
    by_test = {}
    for key, scenario in scenarios.items():
        adapter = scenario.get("adapter") or {}
        if adapter.get("kind") == "devtools-test":
            by_test.setdefault(adapter["test"], []).append(key)
    if not by_test: return [], []
    records, invalid, files = [], [], {}
    scoped_inputs = {}

    def current_file(record, *, expected=None, owned=None, allow_missing=False):
        if not isinstance(record, dict) or not isinstance(record.get("path"), str): return False
        target = Path(record["path"])
        if not target.is_absolute(): target = repo / target
        if target.is_symlink() or not target.resolve().is_relative_to(repo.resolve()): return False
        if expected is not None and target.resolve() != expected.resolve(): return False
        if owned is not None and not target.resolve().is_relative_to(owned.resolve()): return False
        key = str(target.resolve())
        if key not in files: files[key] = file_record(target, repo)
        actual = files[key]
        if allow_missing and _file_shape(record) and record["present"] is False:
            return actual["present"] is False
        return actual["present"] and actual["sha256"] == record.get("sha256") \
            and ("size" not in record or actual["size"] == record["size"])

    try:
        registry = json.loads((repo / "tools/overworld/runtime_proof_registry.json").read_text()).get("sharedTests", {})
        if not isinstance(registry, dict): raise ValueError("shared test registration map is invalid")
    except (OSError, ValueError, AttributeError) as error:
        return [], [{"path": "tools/overworld/runtime_proof_registry.json", "reason": str(error)}]
    for path in sorted((repo / "build/overworld-devtools").glob("test-*/manifest.json")):
        try:
            if path.is_symlink() or not path.resolve().is_relative_to((repo / "build/overworld-devtools").resolve()) \
                    or path.stat().st_size > 16 * 1024 * 1024:
                raise ValueError("shared manifest is not a bounded owned file")
            document = json.loads(path.read_text())
            if not isinstance(document, dict) or document.get("execution") != "shared-devtools":
                raise ValueError("shared manifest execution shape is invalid")
            if document.get("test") not in by_test: continue
            if document.get("runId") != path.parent.name:
                raise ValueError("shared manifest run identity differs from its directory")
            if document.get("state") in ("starting", "running", "canceling"):
                progress_path = path.with_name("progress.json")
                if progress_path.is_file():
                    if progress_path.is_symlink() or progress_path.stat().st_size > 16 * 1024 * 1024:
                        raise ValueError("shared progress is not a bounded owned file")
                    progress = json.loads(progress_path.read_text())
                    if not isinstance(progress, dict) or any(progress.get(key) != document.get(key)
                            for key in ("runId", "test", "execution")):
                        raise ValueError("shared progress identity differs from its manifest")
                    document = progress
            outcome = document.get("state")
            if outcome not in ("starting", "running", "canceling", "completed", "failed", "canceled") \
                    or type(document.get("passed")) is not bool or type(document.get("acceptedProof")) is not bool:
                raise ValueError("shared result shape is invalid")
            elapsed = document.get("elapsedSeconds", 0)
            if type(elapsed) not in (float, int) or not math.isfinite(elapsed) or elapsed < 0:
                raise ValueError("shared duration is invalid")
            accepted = document["acceptedProof"]
            if accepted and (outcome != "completed" or document["passed"] is not True):
                raise ValueError("shared acceptance conflicts with its terminal result")
            registration = registry.get(document["test"])
            preflight = document.get("fixtureProof", {})
            identity = document.get("identity", {})
            acceptance = document.get("proofAcceptance", {})
            if preflight is None and not accepted: preflight = {}
            if any(not isinstance(item, dict) for item in (preflight, identity, acceptance)):
                raise ValueError("shared proof/identity shape is invalid")
            recipe_path = repo / "tests/overworld/test-recipes" / (document["test"] + ".json")
            attempt = document.get("attemptIdentity")
            if attempt is not None and (not isinstance(attempt, dict) or attempt.get("schemaVersion") != 1):
                raise ValueError("shared attempt identity shape is invalid")
            attempt = attempt if attempt is not None else {
                "source": preflight.get("source"), "testSourceSha256": document.get("testSourceSha256")}
            candidate_known = isinstance(attempt.get("source"), dict) and bool(attempt["source"]) \
                and isinstance(attempt.get("testSourceSha256"), str)
            same_source = attempt.get("source") == source
            scope = preflight.get("proofInputs")
            checker_current = True
            if scope is not None:
                from .proof_inputs import proof_inputs
                if document["test"] not in scoped_inputs:
                    scoped_inputs[document["test"]] = proof_inputs(repo, json.loads(recipe_path.read_text()))
                now = scoped_inputs[document["test"]]
                same_source = isinstance(scope, dict) and scope.get("schema") == now["schema"] \
                    and scope.get("capture") == now["capture"]
                checker_current = isinstance(scope, dict) and scope.get("checker") == now["checker"]
            current = (candidate_known and isinstance(registration, dict) and same_source
                       and current_file({"path": str(recipe_path), "sha256": attempt["testSourceSha256"]})
                       and attempt["testSourceSha256"] == registration.get("recipeSha256"))
            if current:
                recipe = json.loads(recipe_path.read_text())
                expected_files = {"rom": repo / recipe["fixture"]["rom"], "save": repo / recipe["fixture"]["save"],
                                  "debugDescriptor": repo / "build/overworld-system.debug.json"}
                if "files" in attempt:
                    attempted_files = attempt["files"]
                    if not isinstance(attempted_files, dict) or set(attempted_files) != set(expected_files) \
                            or not all(_file_shape(item) for item in attempted_files.values()):
                        raise ValueError("shared attempt fixture identities are invalid")
                    current = all(current_file(attempted_files[key], expected=expected, allow_missing=True)
                                  for key, expected in expected_files.items())
                elif identity:
                    current = identity.get("sessionId") == document.get("sessionId") and all(
                        current_file(identity.get(key), expected=expected) for key, expected in expected_files.items())
            if accepted:
                current = current and identity.get("sessionId") == document.get("sessionId") and all(
                    current_file(identity.get(key), expected=expected) for key, expected in expected_files.items()) \
                    and preflight.get("passed") is True and preflight.get("registration") == registration \
                    and acceptance.get("source") == (preflight.get("source") if scope is not None else source) \
                    and acceptance.get("eligible") is True \
                    and acceptance.get("claims") == registration.get("claims") \
                    and acceptance.get("requirements") == registration.get("requirements") \
                    and acceptance.get("proofLevel") == registration.get("proofLevel") \
                    and current_file(document.get("observationsArtifact"), owned=path.parent)
            state = "unverified" if not candidate_known else "stale" if not current else \
                "unfinished" if outcome in ("starting", "running", "canceling") else \
                "recorded-pass" if current and accepted else \
                "recorded-diagnostic" if document["passed"] else "failed"
            for key in by_test[document["test"]]:
                records.append({"scenario": key, "runId": document["runId"], "state": state,
                    "outcome": outcome, "manifest": path.relative_to(repo).as_posix(),
                    "execution": "shared-devtools", "acceptedProofRecorded": accepted,
                    "currentInputs": bool(current), "candidateKnown": candidate_known,
                    "proofFreshness": "replay-required" if current and not checker_current else
                                      "recorded-only" if current else "stale",
                    "liveOwnership": "not-checked" if outcome in ("starting", "running", "canceling") else "terminal",
                    "elapsedSeconds": elapsed,
                    "observedFrames": document.get("evaluation", {}).get("observedFrames", document.get("observedFrames", 0)),
                    "failure": document.get("evaluation", {}).get("failures", []), "reviewState": "none"})
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            invalid.append({"path": path.relative_to(repo).as_posix(), "reason": str(error)})
    return records, invalid


def summarize(repo: Path, scenarios: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    rows = {key: {"id": key, "state": "planned" if item["status"] != "active" else "untested",
                  "proofLevel": item["proofLevel"], "runs": [], "elapsedSeconds": 0.0,
                  "testKind": item.get("verification", {}).get("kind"),
                  "setupAudit": item.get("verification", {}).get("setupAudit")}
            for key, item in sorted(scenarios.items())}
    invalid = []
    historical = []
    try:
        reviews = load_dispositions(repo)
        ledger_errors = []
    except (OSError, ValidationFailure) as error:
        reviews, ledger_errors = [], [str(error)]
    file_cache = {}
    for path in sorted((repo / "build/overworld-runs").glob("**/*.json")):
        try:
            document = read_manifest(path)
        except (OSError, ValueError, ValidationFailure) as error:
            target = historical if str(error) == "manifest schema is not current" else invalid
            target.append({"path": path.relative_to(repo).as_posix(), "reason": str(error)})
            continue
        identity = document["identity"]
        key = identity.get("target")
        if identity.get("kind") != "scenario" or key not in rows:
            continue
        current = (identity.get("source") == source
                   and identity.get("scenarioRevision") == digest_value(scenarios[key]))
        for value in identity.values():
            if isinstance(value, dict) and "path" in value and "sha256" in value:
                name = value["path"]
                if name not in file_cache:
                    file_cache[name] = file_record(Path(name), repo)
                current &= value == file_cache[name]
        passed = document["result"].get("passed") is True
        state = "stale" if not current else "recorded-pass" if passed else "failed"
        row = rows[key]
        row["runs"].append({"runId": document["runId"], "state": state,
                            "manifest": path.relative_to(repo).as_posix(),
                            "reviewState": "recorded-pending-final-check" if any(
                                review.get("failedRunId") == document["runId"]
                                for review in reviews) else "none"})
        row["elapsedSeconds"] += sum(step.get("elapsedSeconds", 0.0)
                                      for step in document["result"].get("steps", [])
                                      if isinstance(step, dict))
        # A later pass cannot hide a current failure. Planned stays planned.
        if row["state"] != "planned":
            priorities = {"untested": 0, "stale": 1, "recorded-pass": 2, "failed": 3}
            if priorities[state] > priorities[row["state"]]:
                row["state"] = state
    shared, shared_invalid = shared_history(repo, scenarios, source)
    invalid.extend(shared_invalid)
    priorities = {"untested": 0, "unverified": 1, "stale": 2, "recorded-diagnostic": 3,
                  "recorded-pass": 4, "unfinished": 5, "failed": 6}
    for entry in shared:
        row = rows[entry["scenario"]]
        row["runs"].append(entry)
        row["elapsedSeconds"] += entry["elapsedSeconds"]
        if row["state"] != "planned" and priorities[entry["state"]] > priorities[row["state"]]:
            row["state"] = entry["state"]
    counts = {state: sum(row["state"] == state for row in rows.values())
              for state in ("planned", "untested", "unverified", "stale", "failed", "recorded-pass", "recorded-diagnostic", "unfinished")}
    return {"schemaVersion": 1, "acceptance": "not-evaluated", "counts": counts,
            "scenarios": list(rows.values()), "invalidReceipts": invalid,
            "historicalReceipts": historical,
            "setupAuditsPending": [key for key, item in sorted(scenarios.items())
                                   if item["status"] == "active"
                                   and item.get("verification", {}).get("setupAudit") == "pending"],
            "failureLedgerErrors": ledger_errors,
            "note": "Recorded results only; no fixture, observer, emulator, or final gate was run."}


def failure_can_be_reviewed(document: dict[str, Any]) -> bool:
    if document["result"].get("passed") is not False:
        return False
    failed_steps = []
    for step in document["result"].get("steps", []):
        if not isinstance(step, dict):
            return False
        claims = step.get("proofClaims", {})
        if not isinstance(claims, dict) or any(value is False for value in claims.values()):
            return False
        if step.get("resultKind") == "actor-observation" and step.get("passed") is False:
            return False
        # Missing measurements are not evidence of a host fault. A frozen
        # game often produces no receipt at all. Only proven pre-runtime
        # failures can be resolved without a corrected candidate.
        if step.get("proofExecution") or step.get("failureStage") == "runtime":
            return False
        if step.get("passed") is False:
            failed_steps.append(step)
    return bool(failed_steps) and all(step.get("failureStage") in
        ("fixture-preflight", "collector-launch") for step in failed_steps)


def load_dispositions(repo: Path) -> list[dict[str, Any]]:
    path = repo / DISPOSITIONS
    if not path.exists():
        return []
    try:
        document = json.loads(path.read_text())
    except ValueError as error:
        raise ValidationFailure("failure disposition ledger has invalid JSON") from error
    if (not isinstance(document, dict) or document.get("schemaVersion") != 1
            or not isinstance(document.get("records"), list)
            or any(not isinstance(record, dict) for record in document.get("records", []))):
        raise ValidationFailure("failure disposition ledger has an invalid schema")
    fields = ("failedRunId", "failedReceiptSha256", "replacementRunId", "category",
              "reason", "reviewer", "recordedAtUtc")
    for record in document["records"]:
        if (any(not isinstance(record.get(field), str) or not record[field] for field in fields)
                or record["category"] not in ("setup", "harness", "host")
                or not _file_shape(record.get("reviewEvidence"))):
            raise ValidationFailure("failure disposition record has invalid fields")
    return document["records"]


def resolution_for(repo: Path, failed: dict[str, Any], accepted_ids: set[str]) -> dict[str, Any] | None:
    if not failure_can_be_reviewed(failed):
        return None
    for record in load_dispositions(repo):
        if (record.get("failedRunId") != failed["runId"]
                or record.get("failedReceiptSha256") != digest_value(failed)
                or record.get("category") not in ("setup", "harness", "host")
                or record.get("replacementRunId") not in accepted_ids
                or not record.get("reason") or not record.get("reviewer")):
            continue
        evidence = record.get("reviewEvidence")
        if (isinstance(evidence, dict) and evidence.get("present") is True
                and evidence.get("size", 0) > 0
                and file_record(Path(evidence["path"]), repo) == evidence):
            return record
    return None


def record_resolution(repo: Path, failed: dict[str, Any], replacement: dict[str, Any],
                      category: str, reason: str, reviewer: str, evidence: Path) -> dict[str, Any]:
    if not failure_can_be_reviewed(failed):
        raise ValidationFailure("observed gameplay failures cannot be waived; fix and verify a new candidate")
    if category not in ("setup", "harness", "host") or not reason.strip() or not reviewer.strip():
        raise ValidationFailure("failure resolution needs category, reason, and reviewer")
    if (failed["identity"]["target"] != replacement["identity"]["target"]
            or failed["identity"] != replacement["identity"]
            or replacement["result"].get("passed") is not True):
        raise ValidationFailure("replacement must be a passing run of the same exact candidate and scenario")
    evidence_record = file_record(evidence, repo)
    if not evidence_record or not evidence_record.get("present") or not evidence_record.get("size"):
        raise ValidationFailure("failure review needs a nonempty evidence file")
    # Keep review evidence local and addressable on resume.
    evidence_path = evidence if evidence.is_absolute() else repo / evidence
    try:
        evidence_path.resolve().relative_to(repo.resolve())
    except ValueError as error:
        raise ValidationFailure("review evidence must be saved in this repository") from error
    record = {"failedRunId": failed["runId"], "failedReceiptSha256": digest_value(failed),
              "replacementRunId": replacement["runId"], "category": category,
              "reason": reason.strip(), "reviewer": reviewer.strip(),
              "reviewEvidence": evidence_record, "recordedAtUtc": utc_now()}
    records = load_dispositions(repo)
    if any(item.get("failedRunId") == failed["runId"] for item in records):
        raise ValidationFailure("this failure already has a review record; preserve it and review the existing entry")
    records.append(record)
    path = repo / DISPOSITIONS
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", prefix=".failure-review-", dir=path.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps({"schemaVersion": 1, "records": records}, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return record
