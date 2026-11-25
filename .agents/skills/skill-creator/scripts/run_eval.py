#!/usr/bin/env python3
"""Run trigger evaluation for a skill description.

Tests whether Claude Code or Cursor reads a temporary skill for a set of
queries. Outputs results as JSON.
"""

import argparse
import json
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from scripts.agent_backends import (
    SUPPORTED_BACKENDS,
    build_stream_command,
    cursor_event_triggers_skill,
    ensure_backend_ready,
    resolve_backend,
    stream_subprocess_env,
)
from scripts.utils import parse_skill_md


def find_project_root(backend: str = "auto") -> Path:
    """Find the nearest root from which the selected harness discovers skills."""
    backend = resolve_backend(backend)
    current = Path.cwd()
    for parent in [current, *current.parents]:
        harness_dir = ".cursor" if backend == "cursor" else ".claude"
        if (
            (parent / harness_dir).is_dir()
            or (parent / ".agents").is_dir()
            or (parent / ".git").exists()
        ):
            return parent
    return current


def _candidate_name(skill_name: str) -> str:
    unique_id = uuid.uuid4().hex[:8]
    suffix = f"-eval-{unique_id}"
    return f"{skill_name[: 64 - len(suffix)].rstrip('-')}{suffix}"


def _candidate_content(
    clean_name: str,
    skill_name: str,
    skill_description: str,
    backend: str,
) -> str:
    indented_desc = "\n  ".join(skill_description.split("\n"))
    name_line = f"name: {clean_name}\n" if backend == "cursor" else ""
    return (
        f"---\n"
        f"{name_line}"
        f"description: |\n"
        f"  {indented_desc}\n"
        f"---\n\n"
        f"# {skill_name}\n\n"
        f"This skill handles: {skill_description}\n"
    )


def _write_cursor_candidate(
    project_root: Path,
    clean_name: str,
    skill_name: str,
    skill_description: str,
) -> Path:
    candidate_file = project_root / ".cursor" / "skills" / clean_name / "SKILL.md"
    candidate_file.parent.mkdir(parents=True, exist_ok=True)
    candidate_file.write_text(
        _candidate_content(clean_name, skill_name, skill_description, "cursor")
    )
    return candidate_file


def _mirror_cursor_discovery_context(
    project_root: Path,
    workspace: Path,
    optimized_skill_name: str,
) -> None:
    """Mirror routing context while excluding the skill being optimized."""
    for filename in ("AGENTS.md", "CLAUDE.md"):
        source = project_root / filename
        if source.is_file():
            shutil.copy2(source, workspace / filename)

    discovery_paths = (
        Path(".cursor/rules"),
        Path(".cursor/skills"),
        Path(".agents/skills"),
        Path(".claude/skills"),
        Path(".codex/skills"),
    )
    for relative in discovery_paths:
        source = project_root / relative
        if source.is_dir():
            shutil.copytree(
                source,
                workspace / relative,
                dirs_exist_ok=True,
                symlinks=True,
            )

    # Remove every project copy of the skill under test. Other skills and
    # routing rules remain available, so selection pressure resembles the real
    # project without letting the installed description mask the candidate.
    for skills_root in (
        workspace / ".cursor" / "skills",
        workspace / ".agents" / "skills",
        workspace / ".claude" / "skills",
        workspace / ".codex" / "skills",
    ):
        if not skills_root.is_dir():
            continue
        for skill_md in list(skills_root.rglob("SKILL.md")):
            if skill_md.parent.name == optimized_skill_name:
                if skill_md.parent.is_symlink():
                    skill_md.parent.unlink()
                else:
                    shutil.rmtree(skill_md.parent)


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    project_root: str,
    model: str | None = None,
    backend: str = "auto",
    candidate_name: str | None = None,
) -> bool:
    """Run a single query and return whether the skill was triggered.

    Claude uses a temporary command, preserving the original implementation.
    Cursor uses a temporary real skill under .cursor/skills and detects its
    documented stream-json read/tool event. Candidate names are unique so
    concurrent evaluation batches cannot collide.
    """
    backend = resolve_backend(backend)
    clean_name = candidate_name or _candidate_name(skill_name)
    project_root_path = Path(project_root)
    owns_candidate = candidate_name is None
    cursor_dir_existed = (project_root_path / ".cursor").exists()
    skills_dir_existed = (project_root_path / ".cursor" / "skills").exists()

    if backend == "cursor":
        candidate_dir = project_root_path / ".cursor" / "skills" / clean_name
        candidate_file = candidate_dir / "SKILL.md"
    else:
        candidate_dir = project_root_path / ".claude" / "commands"
        candidate_file = candidate_dir / f"{clean_name}.md"

    try:
        if owns_candidate:
            candidate_dir.mkdir(parents=True, exist_ok=True)
            candidate_file.write_text(
                _candidate_content(clean_name, skill_name, skill_description, backend)
            )
        elif not candidate_file.exists():
            raise RuntimeError(f"Shared candidate skill is missing: {candidate_file}")

        cmd = build_stream_command(backend, query, model)

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=(subprocess.PIPE if backend == "cursor" else subprocess.DEVNULL),
            cwd=project_root,
            env=stream_subprocess_env(backend),
        )

        if backend == "cursor":
            try:
                stdout_bytes, stderr_bytes = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                process.kill()
                process.communicate()
                raise RuntimeError(
                    f"cursor trigger-evaluation process timed out after {timeout}s"
                ) from exc
            if process.returncode != 0:
                detail = stderr_bytes.decode("utf-8", errors="replace").strip()
                raise RuntimeError(
                    f"cursor trigger-evaluation process exited {process.returncode}: "
                    f"{detail or 'no diagnostic output'}"
                )
            output = stdout_bytes.decode("utf-8", errors="replace")
            for line in output.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if cursor_event_triggers_skill(event, clean_name):
                    return True
            return False

        triggered = False
        start_time = time.time()
        buffer = ""
        # Track state for stream event detection
        pending_tool_name = None
        accumulated_json = ""

        stdout = process.stdout
        if stdout is None:
            raise RuntimeError("stdout pipe was not created")

        try:
            while time.time() - start_time < timeout:
                if process.poll() is not None:
                    remaining = stdout.read()
                    if remaining:
                        buffer += remaining.decode("utf-8", errors="replace")
                    break

                ready, _, _ = select.select([stdout], [], [], 1.0)
                if not ready:
                    continue

                chunk = os.read(stdout.fileno(), 8192)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Claude: early detection via stream events.
                    if event.get("type") == "stream_event":
                        se = event.get("event", {})
                        se_type = se.get("type", "")

                        if se_type == "content_block_start":
                            cb = se.get("content_block", {})
                            if cb.get("type") == "tool_use":
                                tool_name = cb.get("name", "")
                                if tool_name in ("Skill", "Read"):
                                    pending_tool_name = tool_name
                                    accumulated_json = ""
                                else:
                                    return False

                        elif se_type == "content_block_delta" and pending_tool_name:
                            delta = se.get("delta", {})
                            if delta.get("type") == "input_json_delta":
                                accumulated_json += delta.get("partial_json", "")
                                if clean_name in accumulated_json:
                                    return True

                        elif se_type in ("content_block_stop", "message_stop"):
                            if pending_tool_name:
                                return clean_name in accumulated_json
                            if se_type == "message_stop":
                                return False

                    # Fallback: full assistant message
                    elif event.get("type") == "assistant":
                        message = event.get("message", {})
                        for content_item in message.get("content", []):
                            if content_item.get("type") != "tool_use":
                                continue
                            tool_name = content_item.get("name", "")
                            tool_input = content_item.get("input", {})
                            if tool_name == "Skill" and clean_name in tool_input.get(
                                "skill", ""
                            ):
                                triggered = True
                            elif tool_name == "Read" and clean_name in tool_input.get(
                                "file_path", ""
                            ):
                                triggered = True
                            return triggered

                    elif event.get("type") == "result":
                        return triggered
        finally:
            # Clean up process on any exit path (return, exception, timeout)
            if process.poll() is None:
                process.kill()
                process.wait()

        if process.returncode not in (None, 0):
            raise RuntimeError(
                f"{backend} trigger-evaluation process exited {process.returncode}"
            )
        return triggered
    finally:
        if backend == "cursor" and owns_candidate:
            if candidate_dir.exists():
                shutil.rmtree(candidate_dir)
            # Remove only parent directories this invocation created.
            removable_parents = []
            if not skills_dir_existed:
                removable_parents.append(candidate_dir.parent)
            if not cursor_dir_existed:
                removable_parents.append(candidate_dir.parent.parent)
            for parent in removable_parents:
                try:
                    parent.rmdir()
                except OSError:
                    pass
        elif backend != "cursor" and candidate_file.exists():
            candidate_file.unlink()


def run_eval(
    eval_set: list[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    project_root: Path,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    model: str | None = None,
    backend: str = "auto",
) -> dict:
    """Run the full eval set and return results."""
    backend = ensure_backend_ready(backend)
    total_runs = len(eval_set) * runs_per_query

    def execute_batch(
        workspace: Path,
        shared_candidate_name: str | None,
    ) -> tuple[dict[str, list[bool]], dict[str, dict], int]:
        failed_runs = 0
        query_triggers: dict[str, list[bool]] = {}
        query_items: dict[str, dict] = {}
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            future_to_info = {}
            for item in eval_set:
                for run_idx in range(runs_per_query):
                    future = executor.submit(
                        run_single_query,
                        item["query"],
                        skill_name,
                        description,
                        timeout,
                        str(workspace),
                        model,
                        backend,
                        shared_candidate_name,
                    )
                    future_to_info[future] = (item, run_idx)

            for future in as_completed(future_to_info):
                item, _ = future_to_info[future]
                query = item["query"]
                query_items[query] = item
                query_triggers.setdefault(query, [])
                try:
                    query_triggers[query].append(future.result())
                except Exception as e:
                    print(f"Warning: query failed: {e}", file=sys.stderr)
                    query_triggers[query].append(False)
                    failed_runs += 1
        return query_triggers, query_items, failed_runs

    if backend == "cursor":
        # All parallel runs must see exactly one candidate. An isolated shared
        # workspace prevents UUID races and keeps the user's project untouched.
        with tempfile.TemporaryDirectory(prefix="skill-trigger-eval-") as temp_dir:
            workspace = Path(temp_dir)
            _mirror_cursor_discovery_context(project_root, workspace, skill_name)
            shared_candidate_name = _candidate_name(skill_name)
            _write_cursor_candidate(
                workspace, shared_candidate_name, skill_name, description
            )
            query_triggers, query_items, failed_runs = execute_batch(
                workspace, shared_candidate_name
            )
    else:
        query_triggers, query_items, failed_runs = execute_batch(project_root, None)

    if failed_runs:
        raise RuntimeError(
            f"{failed_runs} of {total_runs} {backend} trigger-evaluation runs failed; "
            "refusing to treat infrastructure failures as non-triggers."
        )

    results = []
    for query, triggers in query_triggers.items():
        item = query_items[query]
        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        results.append(
            {
                "query": query,
                "should_trigger": should_trigger,
                "trigger_rate": trigger_rate,
                "triggers": sum(triggers),
                "runs": len(triggers),
                "pass": did_pass,
            }
        )

    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    return {
        "skill_name": skill_name,
        "description": description,
        "backend": backend,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run trigger evaluation for a skill description"
    )
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument(
        "--description", default=None, help="Override description to test"
    )
    parser.add_argument(
        "--num-workers", type=int, default=10, help="Number of parallel workers"
    )
    parser.add_argument(
        "--timeout", type=int, default=30, help="Timeout per query in seconds"
    )
    parser.add_argument(
        "--runs-per-query", type=int, default=3, help="Number of runs per query"
    )
    parser.add_argument(
        "--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model to use (default: selected CLI's configured model)",
    )
    parser.add_argument(
        "--backend",
        choices=SUPPORTED_BACKENDS,
        default="auto",
        help="Agent CLI used for trigger tests (default: auto)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print progress to stderr"
    )
    args = parser.parse_args()

    eval_set = json.loads(Path(args.eval_set).read_text())
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, original_description, content = parse_skill_md(skill_path)
    description = args.description or original_description
    backend = resolve_backend(args.backend)
    project_root = find_project_root(backend)

    if args.verbose:
        print(f"Evaluating: {description}", file=sys.stderr)

    output = run_eval(
        eval_set=eval_set,
        skill_name=name,
        description=description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        project_root=project_root,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        model=args.model,
        backend=backend,
    )

    if args.verbose:
        summary = output["summary"]
        print(
            f"Results: {summary['passed']}/{summary['total']} passed", file=sys.stderr
        )
        for r in output["results"]:
            status = "PASS" if r["pass"] else "FAIL"
            rate_str = f"{r['triggers']}/{r['runs']}"
            print(
                f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:70]}",
                file=sys.stderr,
            )

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
