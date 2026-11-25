"""Shared CLI adapters for skill-creator's supported agent harnesses."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

SUPPORTED_BACKENDS = ("auto", "claude", "cursor")


def resolve_backend(requested: str = "auto") -> str:
    """Resolve an agent backend and fail with an actionable error if unavailable."""
    if requested not in SUPPORTED_BACKENDS:
        raise ValueError(
            f"Unsupported backend {requested!r}; choose one of {', '.join(SUPPORTED_BACKENDS)}"
        )

    if requested != "auto":
        executable = "claude" if requested == "claude" else "cursor"
        if shutil.which(executable) is None:
            raise RuntimeError(
                f"The {requested} backend requires `{executable}` on PATH. "
                f"Install or authenticate that CLI, or choose a different --backend."
            )
        return requested

    # Prefer the harness that appears to own the current session. Preserve the
    # original Claude behavior when both CLIs are installed but no session hint
    # is available.
    cursor_session = any(
        os.environ.get(name)
        for name in ("CURSOR_AGENT", "CURSOR_SESSION_ID", "CURSOR_TRACE_ID")
    )
    if cursor_session and shutil.which("cursor"):
        return "cursor"
    if os.environ.get("CLAUDECODE") and shutil.which("claude"):
        return "claude"
    if shutil.which("claude"):
        return "claude"
    if shutil.which("cursor"):
        return "cursor"

    raise RuntimeError(
        "No supported agent CLI found. Install/authenticate `cursor` or `claude`, "
        "or run the qualitative evaluation workflow without the optimizer."
    )


def backend_display_name(backend: str) -> str:
    return "Cursor" if backend == "cursor" else "Claude Code"


def ensure_backend_ready(backend: str) -> str:
    """Resolve a backend and fail before a batch if its CLI is not usable."""
    backend = resolve_backend(backend)
    if backend == "cursor":
        result = subprocess.run(
            ["cursor", "agent", "status", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        status_text = f"{result.stdout}\n{result.stderr}".strip()
        try:
            status = json.loads(result.stdout)
        except json.JSONDecodeError:
            status = {}
        authenticated = status.get("isAuthenticated")
        if result.returncode != 0 or authenticated is not True:
            detail = status_text or f"exit code {result.returncode}"
            raise RuntimeError(
                "Cursor Agent CLI is not authenticated. Run `cursor agent login` "
                f"before using --backend cursor. Status: {detail}"
            )
    return backend


def build_stream_command(
    backend: str,
    prompt: str,
    model: str | None = None,
) -> list[str]:
    """Build a non-mutating NDJSON command for trigger detection."""
    backend = resolve_backend(backend)
    if backend == "cursor":
        cmd = [
            "cursor",
            "agent",
            "--print",
            "--output-format",
            "stream-json",
            "--mode",
            "ask",
            "--trust",
        ]
        if model:
            cmd.extend(["--model", model])
        cmd.append(prompt)
        return cmd

    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
    ]
    if model:
        cmd.extend(["--model", model])
    return cmd


def _subprocess_env(backend: str) -> dict[str, str]:
    env = os.environ.copy()
    if backend == "claude":
        # Claude Code sets this guard for interactive nesting. Programmatic
        # `claude -p` subprocesses are safe and were supported by the original
        # implementation.
        env.pop("CLAUDECODE", None)
    return env


def call_text_agent(
    prompt: str,
    model: str | None,
    backend: str,
    timeout: int = 300,
) -> str:
    """Call the selected agent in read-only print mode and return plain text."""
    backend = ensure_backend_ready(backend)
    if backend == "cursor":
        cmd = [
            "cursor",
            "agent",
            "--print",
            "--output-format",
            "text",
            "--mode",
            "ask",
            "--trust",
        ]
        if model:
            cmd.extend(["--model", model])
        # Cursor accepts piped stdin in print mode. Keep the potentially large
        # SKILL.md/history prompt off argv to avoid platform ARG_MAX limits.
        input_text = prompt
    else:
        cmd = ["claude", "-p", "--output-format", "text"]
        if model:
            cmd.extend(["--model", model])
        # Keep large Claude prompts off argv, matching the original behavior.
        input_text = prompt

    result = subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        env=_subprocess_env(backend),
        timeout=timeout,
    )
    if result.returncode != 0:
        detail = (
            result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
        )
        raise RuntimeError(
            f"{backend_display_name(backend)} CLI exited {result.returncode}: {detail}"
        )
    return result.stdout


def stream_subprocess_env(backend: str) -> dict[str, str]:
    """Return the environment for a streaming backend subprocess."""
    return _subprocess_env(resolve_backend(backend))


def contains_marker(value: object, marker: str) -> bool:
    """Return whether a nested JSON-compatible value contains a path marker."""
    if isinstance(value, str):
        return marker in value
    if isinstance(value, dict):
        return any(contains_marker(item, marker) for item in value.values())
    if isinstance(value, list):
        return any(contains_marker(item, marker) for item in value)
    return False


def cursor_event_triggers_skill(event: dict, marker: str) -> bool:
    """Detect a Cursor skill load from its documented stream-json tool event."""
    if event.get("type") != "tool_call":
        return False
    tool_call = event.get("tool_call", {})
    if not isinstance(tool_call, dict):
        return False
    expected_suffix = f"/{marker}/SKILL.md"

    def is_candidate_path(value: object) -> bool:
        return isinstance(value, str) and value.replace("\\", "/").endswith(
            expected_suffix
        )

    read_call = tool_call.get("readToolCall")
    if isinstance(read_call, dict):
        args = read_call.get("args", {})
        if isinstance(args, dict) and is_candidate_path(args.get("path")):
            return True

    # Some Cursor versions expose tools through the generic function envelope.
    function = tool_call.get("function")
    if isinstance(function, dict):
        name = str(function.get("name", "")).lower()
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        if name in {"read", "read_file"} and isinstance(arguments, dict):
            return is_candidate_path(
                arguments.get("path")
                or arguments.get("file_path")
                or arguments.get("target_file")
            )
        if name == "skill" and isinstance(arguments, dict):
            return arguments.get("skill") == marker
    return False
