"""Launch the sealed native bootstrap behind a live-process AMFI gate.

The Swift controller source is supplied on standard input to Apple's
root-owned system Swift frontend.  The controller starts the requested image
with POSIX_SPAWN_START_SUSPENDED, authenticates the kernel-bound process rather
than its mutable pathname, and only then permits dyld or user code to run.
"""

from __future__ import annotations

import os
import signal
import stat
import subprocess
from collections.abc import Mapping, Sequence
from typing import Any


SYSTEM_SWIFT = "/usr/bin/swift"
ARGUMENT_SEPARATOR = "\x1f"
EXPECTED_DYNAMIC_CODE_FLAGS = "22012b01"
PROTECTED_SPAWN_SOURCE = r'''import Darwin

@_silgen_name("csops")
func csops(_ pid: pid_t, _ operations: UInt32,
           _ address: UnsafeMutableRawPointer?, _ size: Int) -> Int32
@_silgen_name("proc_pidpath")
func proc_pidpath(_ pid: Int32, _ buffer: UnsafeMutableRawPointer!,
                  _ bufferSize: UInt32) -> Int32

let separator = Character("\u{1f}")

func requiredEnvironment(_ name: String) -> String {
    guard let value = getenv(name), value.pointee != 0 else {
        fputs("protected spawn: missing " + name + "\n", stderr)
        exit(125)
    }
    return String(cString: value)
}

func decodeFields(_ name: String) -> [String] {
    let value = requiredEnvironment(name)
    let fields = value.split(separator: separator,
                             omittingEmptySubsequences: false).map(String.init)
    if fields.isEmpty || fields.contains(where: { $0.isEmpty }) {
        fputs("protected spawn: malformed " + name + "\n", stderr)
        exit(125)
    }
    return fields
}

func fifoBarrier() -> Bool {
    let published = getenv("SMR_PROTECTED_SPAWNED_FIFO")
    let continuation = getenv("SMR_PROTECTED_CONTINUE_FIFO")
    if published == nil && continuation == nil { return true }
    guard let published, let continuation else { return false }
    let output = open(published, O_WRONLY | O_CLOEXEC)
    if output < 0 { return false }
    let notice = Array("SPAWNED\n".utf8)
    let wrote = notice.withUnsafeBytes {
        write(output, $0.baseAddress, $0.count)
    }
    close(output)
    if wrote != notice.count { return false }
    let input = open(continuation, O_RDONLY | O_CLOEXEC)
    if input < 0 { return false }
    var received = [UInt8](repeating: 0, count: 9)
    var offset = 0
    while offset < received.count {
        let remaining = received.count - offset
        let count = received.withUnsafeMutableBytes {
            read(input, $0.baseAddress!.advanced(by: offset),
                 remaining)
        }
        if count <= 0 { close(input); return false }
        offset += count
    }
    close(input)
    return received == Array("CONTINUE\n".utf8)
}

func stopped(_ status: Int32) -> Bool {
    return (status & 0xff) == 0x7f
}

func killAndReap(_ pid: pid_t) {
    _ = kill(pid, SIGKILL)
    var status: Int32 = 0
    while waitpid(pid, &status, 0) < 0 && errno == EINTR {}
}

let arguments = decodeFields("SMR_PROTECTED_ARGV")
let childEnvironment = decodeFields("SMR_PROTECTED_ENV")
let expectedPath = requiredEnvironment("SMR_PROTECTED_EXPECTED_PATH")
let expectedCDHash = requiredEnvironment("SMR_PROTECTED_EXPECTED_CDHASH")
let expectedFlagsText = requiredEnvironment("SMR_PROTECTED_EXPECTED_FLAGS")
guard arguments[0] == expectedPath,
      expectedCDHash.count == 40,
      let expectedFlags = UInt32(expectedFlagsText, radix: 16) else {
    fputs("protected spawn: malformed external seal\n", stderr)
    exit(125)
}

var argv = arguments.map { strdup($0) }
argv.append(nil)
defer { for pointer in argv { free(pointer) } }
var envp = childEnvironment.map { strdup($0) }
envp.append(nil)
defer { for pointer in envp { free(pointer) } }
var attributes: posix_spawnattr_t? = nil
guard posix_spawnattr_init(&attributes) == 0 else { exit(125) }
defer { posix_spawnattr_destroy(&attributes) }
var fileActions: posix_spawn_file_actions_t? = nil
guard posix_spawn_file_actions_init(&fileActions) == 0,
      posix_spawn_file_actions_adddup2(&fileActions, STDIN_FILENO,
                                      STDIN_FILENO) == 0,
      posix_spawn_file_actions_adddup2(&fileActions, STDOUT_FILENO,
                                      STDOUT_FILENO) == 0,
      posix_spawn_file_actions_adddup2(&fileActions, STDERR_FILENO,
                                      STDERR_FILENO) == 0 else { exit(125) }
defer { posix_spawn_file_actions_destroy(&fileActions) }
let spawnFlags = Int16(POSIX_SPAWN_START_SUSPENDED |
                       POSIX_SPAWN_CLOEXEC_DEFAULT)
guard posix_spawnattr_setflags(&attributes, spawnFlags) == 0 else { exit(125) }

var child: pid_t = 0
let spawnResult = posix_spawn(&child, expectedPath, &fileActions, &attributes,
                              &argv, &envp)
guard spawnResult == 0 && child > 0 else {
    fputs("protected spawn: posix_spawn failed\n", stderr)
    exit(125)
}

var stopStatus: Int32 = 0
var observedStop = false
for _ in 0..<5000 {
    let waited = waitpid(child, &stopStatus, WNOHANG | WUNTRACED)
    if waited == child {
        observedStop = stopped(stopStatus)
        break
    }
    if waited < 0 && errno != EINTR { break }
    usleep(1000)
}
if !observedStop || !fifoBarrier() {
    killAndReap(child)
    fputs("protected spawn: child did not reach authenticated stop\n", stderr)
    exit(125)
}

var liveCDHash = [UInt8](repeating: 0, count: 20)
let cdhashResult = liveCDHash.withUnsafeMutableBytes {
    csops(child, 5, $0.baseAddress, 20)
}
let liveCDHashText = liveCDHash.map {
    let value = String($0, radix: 16)
    return value.count == 1 ? "0" + value : value
}.joined()
var liveFlags: UInt32 = 0
let flagsResult = withUnsafeMutableBytes(of: &liveFlags) {
    csops(child, 0, $0.baseAddress, MemoryLayout<UInt32>.size)
}
var pathBuffer = [CChar](repeating: 0, count: 4096)
let pathLength = pathBuffer.withUnsafeMutableBytes {
    proc_pidpath(child, $0.baseAddress, 4096)
}
let livePath = pathLength > 0 ? String(cString: pathBuffer) : ""
guard cdhashResult == 0,
      flagsResult == 0,
      liveCDHashText == expectedCDHash,
      liveFlags == expectedFlags,
      livePath == expectedPath else {
    killAndReap(child)
    fputs("protected spawn: live process identity differs\n", stderr)
    exit(126)
}

guard kill(child, SIGCONT) == 0 else {
    killAndReap(child)
    fputs("protected spawn: child release failed\n", stderr)
    exit(125)
}
var exitStatus: Int32 = 0
var waited: pid_t = -1
repeat { waited = waitpid(child, &exitStatus, 0) }
while waited < 0 && errno == EINTR
guard waited == child else {
    killAndReap(child)
    exit(125)
}
if (exitStatus & 0x7f) == 0 {
    exit((exitStatus >> 8) & 0xff)
}
exit(128 + (exitStatus & 0x7f))
'''


def _invalidate_explicit_results(arguments: Sequence[str]) -> None:
    targets: list[str] = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--":
            break
        if argument == "--invalidate-result":
            if index + 1 >= len(arguments):
                raise ValueError("--invalidate-result requires a value")
            targets.append(os.fspath(arguments[index + 1]))
            index += 2
            continue
        if argument.startswith("--invalidate-result="):
            targets.append(argument.partition("=")[2])
        index += 1
    for target in targets:
        if not target:
            raise ValueError("result invalidation target is empty")
        try:
            metadata = os.lstat(target)
        except FileNotFoundError:
            continue
        if stat.S_ISDIR(metadata.st_mode):
            raise IsADirectoryError(target)
        os.unlink(target)


def run_native_bootstrap(
    arguments: Sequence[str],
    *,
    expected_cdhash: str,
    child_environment: Mapping[str, str],
    capture_output: bool = False,
    text: bool = False,
    timeout: float | None = None,
    spawned_fifo: str | None = None,
    continue_fifo: str | None = None,
    **unsupported: Any,
) -> subprocess.CompletedProcess[Any]:
    """Run one exact bootstrap image after authenticating its stopped PID."""
    if unsupported:
        raise TypeError(
            "unsupported protected-spawn options: "
            + ", ".join(sorted(unsupported))
        )
    argv = tuple(os.fspath(argument) for argument in arguments)
    if not argv or any(
        not argument or ARGUMENT_SEPARATOR in argument for argument in argv
    ):
        raise ValueError("protected bootstrap argv is malformed")
    argv = (os.path.realpath(argv[0]), *argv[1:])
    _invalidate_explicit_results(argv)
    environment_items = tuple(
        f"{name}={value}" for name, value in sorted(child_environment.items())
    )
    if not environment_items or any(
        not item or ARGUMENT_SEPARATOR in item for item in environment_items
    ):
        raise ValueError("protected bootstrap environment is malformed")
    supervisor_environment = {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "SMR_PROTECTED_ARGV": ARGUMENT_SEPARATOR.join(argv),
        "SMR_PROTECTED_ENV": ARGUMENT_SEPARATOR.join(environment_items),
        "SMR_PROTECTED_EXPECTED_PATH": argv[0],
        "SMR_PROTECTED_EXPECTED_CDHASH": expected_cdhash,
        "SMR_PROTECTED_EXPECTED_FLAGS": EXPECTED_DYNAMIC_CODE_FLAGS,
    }
    if spawned_fifo is not None or continue_fifo is not None:
        if spawned_fifo is None or continue_fifo is None:
            raise ValueError("protected-spawn barriers must be paired")
        supervisor_environment.update(
            {
                "SMR_PROTECTED_SPAWNED_FIFO": spawned_fifo,
                "SMR_PROTECTED_CONTINUE_FIFO": continue_fifo,
            }
        )
    command = [SYSTEM_SWIFT, "-"]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        text=text,
        env=supervisor_environment,
        start_new_session=True,
    )
    payload = PROTECTED_SPAWN_SOURCE if text else PROTECTED_SPAWN_SOURCE.encode()
    try:
        stdout, stderr = process.communicate(input=payload, timeout=timeout)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        _invalidate_explicit_results(argv)
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
