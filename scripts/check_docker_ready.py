#!/usr/bin/env python3
"""Bound Docker daemon startup so ROM builds fail with an actionable error."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time


def probe(docker: str, timeout: float) -> tuple[str, str]:
    try:
        completed = subprocess.run(
            [docker, "info", "--format", "{{.ServerVersion}}"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=max(1.0, timeout),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "timeout", ""
    except OSError as exc:
        return "error", str(exc)
    if completed.returncode == 0 and completed.stdout.strip():
        return "ready", completed.stdout.strip()
    detail = completed.stderr.strip() or completed.stdout.strip()
    return "unavailable", detail.splitlines()[-1] if detail else "Docker daemon unavailable"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true", help="start Docker Desktop on macOS when it is not running")
    parser.add_argument("--wait", type=float, default=120.0, help="maximum startup wait in seconds")
    parser.add_argument("--probe-timeout", type=float, default=12.0, help="timeout for each Docker probe")
    args = parser.parse_args()

    docker = shutil.which("docker")
    if not docker:
        print("Docker CLI is not installed or is not on PATH.", file=sys.stderr)
        return 1

    print("Checking Docker daemon readiness...", flush=True)
    status, detail = probe(docker, args.probe_timeout)
    if status == "ready":
        print(f"Docker daemon ready (server {detail}).", flush=True)
        return 0
    if status == "timeout":
        print(
            "Docker did not answer the readiness probe. Restart Docker Desktop, then retry the build.",
            file=sys.stderr,
        )
        return 1

    if args.start and sys.platform == "darwin":
        print("Docker daemon is unavailable; starting Docker Desktop...", flush=True)
        try:
            subprocess.run(
                ["/usr/bin/open", "-ga", "Docker"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"Could not start Docker Desktop: {exc}", file=sys.stderr)
            return 1

        deadline = time.monotonic() + max(0.0, args.wait)
        while time.monotonic() < deadline:
            time.sleep(2)
            remaining = deadline - time.monotonic()
            status, detail = probe(docker, min(args.probe_timeout, max(1.0, remaining)))
            if status == "ready":
                print(f"Docker daemon ready (server {detail}).", flush=True)
                return 0
            if status == "timeout":
                break

    suffix = f" Last response: {detail}" if detail else ""
    print(
        "Docker daemon is unavailable. Start or restart Docker Desktop, then retry the build." + suffix,
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
