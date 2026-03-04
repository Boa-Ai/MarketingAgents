"""
Spawn a single OpenClaw agent for startup + contact enrichment tasks.

Prereqs:
- `openclaw` installed and on PATH
- You have a `.env` file with:
    BRAVE_API_KEY
    OPENCLAW_MODEL (optional; e.g. ollama/qwen3:8b)
    OPENCLAW_ANTHROPIC_MODEL (optional; used when OPENCLAW_PROVIDER=anthropic)
- Google Sheets API service account key at: ./service-account-key.json
"""
from __future__ import annotations

import json
import os
import selectors
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT_DIR / "logs"
SUCCESS_MARKER = "STATUS: APPEND_CONFIRMED"
OPENCLAW_WORKSPACE = Path.home() / ".openclaw" / "workspace"


def load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {'"', "'"}
        ):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def require_env(var: str) -> str:
    val = os.environ.get(var, "").strip()
    if not val:
        raise SystemExit(
            f"Missing {var}. Set it in .env or export it:\n"
            f' export {var}="..."\n'
        )
    return val


def render_directions(spreadsheet_id: str) -> str:
    directions_path = Path(__file__).with_name("directions.md")
    if not directions_path.exists():
        raise SystemExit(f"Missing directions file: {directions_path}")

    text = directions_path.read_text(encoding="utf-8")
    return text.replace("{{SPREADSHEET_ID}}", spreadsheet_id)


def save_session_log(session_id: str, output: str) -> Path:
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / f"{session_id}.log"
    path.write_text(output, encoding="utf-8")
    return path


def sync_openclaw_workspace(worker_prefix: str) -> None:
    OPENCLAW_WORKSPACE.mkdir(parents=True, exist_ok=True)

    files_to_sync = [
        ROOT_DIR / "google-sheets-helper.js",
        ROOT_DIR / "service-account-key.json",
    ]

    for source in files_to_sync:
        if not source.exists():
            continue
        target = OPENCLAW_WORKSPACE / source.name
        shutil.copy2(source, target)
        print(f"{worker_prefix}Synced workspace file: {target}", flush=True)


def run_and_stream(cmd: list[str], env: dict[str, str], prefix: str) -> tuple[int, str]:
    return run_and_stream_with_heartbeat(
        cmd=cmd,
        env=env,
        prefix=prefix,
        session_id="",
        heartbeat_seconds=30,
    )


def summarize_session_event(event: dict[str, object]) -> str | None:
    event_type = str(event.get("type", ""))
    if event_type == "model_change":
        provider = str(event.get("provider", "?"))
        model_id = str(event.get("modelId", "?"))
        return f"model={provider}/{model_id}"

    if event_type != "message":
        return None

    message_obj = event.get("message")
    if not isinstance(message_obj, dict):
        return None

    role = str(message_obj.get("role", ""))
    if role == "assistant":
        content = message_obj.get("content")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "toolCall":
                    tool_name = str(part.get("name", "tool"))
                    args = part.get("arguments")
                    if isinstance(args, dict):
                        command = str(args.get("command", "")).strip()
                        if command:
                            short = command if len(command) <= 120 else f"{command[:117]}..."
                            return f"assistant toolCall {tool_name}: {short}"
                    return f"assistant toolCall {tool_name}"
        return "assistant message"

    if role == "toolResult":
        tool_name = str(message_obj.get("toolName", "tool"))
        is_error = bool(message_obj.get("isError")) or bool(event.get("isError"))
        return f"toolResult {tool_name} ({'error' if is_error else 'ok'})"

    return None


def read_session_progress(session_id: str, offset: int) -> tuple[int, str | None]:
    if not session_id:
        return offset, None

    path = Path.home() / ".openclaw" / "agents" / "main" / "sessions" / f"{session_id}.jsonl"
    if not path.exists():
        return offset, None

    size = path.stat().st_size
    if size <= offset:
        return offset, None

    with path.open("rb") as fh:
        fh.seek(offset)
        chunk_bytes = fh.read(size - offset)
    new_offset = size
    chunk = chunk_bytes.decode("utf-8", errors="replace")

    summary: str | None = None
    for line in chunk.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            parsed = summarize_session_event(event)
            if parsed:
                summary = parsed

    return new_offset, summary


def run_and_stream_with_heartbeat(
    cmd: list[str],
    env: dict[str, str],
    prefix: str,
    session_id: str,
    heartbeat_seconds: int,
) -> tuple[int, str]:
    proc = subprocess.Popen(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        bufsize=1,
    )

    start = time.monotonic()
    last_heartbeat = start
    session_offset = 0
    lines: list[str] = []

    if proc.stdout is not None:
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)

        while True:
            events = selector.select(timeout=1.0)
            for key, _ in events:
                line = key.fileobj.readline()
                if line:
                    lines.append(line)
                    print(f"{prefix}{line}", end="", flush=True)

            if proc.poll() is not None:
                for line in proc.stdout:
                    lines.append(line)
                    print(f"{prefix}{line}", end="", flush=True)
                break

            now = time.monotonic()
            if now - last_heartbeat >= heartbeat_seconds:
                elapsed = int(now - start)
                session_offset, progress = read_session_progress(session_id, session_offset)
                if progress:
                    print(
                        f"{prefix}[runner] still working after {elapsed}s ({progress})",
                        flush=True,
                    )
                else:
                    print(
                        f"{prefix}[runner] still working after {elapsed}s",
                        flush=True,
                    )
                last_heartbeat = now

        selector.close()

    return_code = proc.wait()
    return return_code, "".join(lines)


def get_openclaw_default_model() -> str:
    proc = subprocess.run(
        ["openclaw", "config", "get", "agents.defaults.model.primary"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return "(unknown)"
    value = proc.stdout.strip()
    return value or "(unknown)"


def get_env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def build_attempt_message(base_message: str, attempt: int) -> str:
    if attempt == 1:
        return base_message
    return (
        f"RETRY ATTEMPT {attempt}.\n"
        "Previous attempt did not confirm append.\n"
        "Prioritize speed: perform the required commands immediately and return only the required final status block.\n\n"
        f"{base_message}"
    )


def get_provider() -> str:
    provider = os.environ.get("OPENCLAW_PROVIDER", "local").strip().lower()
    if provider in {"local", "anthropic"}:
        return provider
    return "local"


def main() -> int:
    load_dotenv()
    worker_id = os.environ.get("SPREADSHEET_WORKER_ID", "1")
    worker_prefix = f"[worker {worker_id}] "

    if shutil.which("openclaw") is None:
        print(f"{worker_prefix}Error: `openclaw` not found on PATH.", file=sys.stderr, flush=True)
        return 2

    require_env("BRAVE_API_KEY")
    sync_openclaw_workspace(worker_prefix)

    if len(sys.argv) > 1:
        spreadsheet_id = sys.argv[1]
    else:
        spreadsheet_id = os.environ.get("SPREADSHEET_ID", "").strip()
        if not spreadsheet_id:
            print(
                "Usage: python main.py spreadsheet_agent <spreadsheet_id>\n"
                "Or set SPREADSHEET_ID in .env",
                file=sys.stderr,
            )
            return 1

    base_message = render_directions(spreadsheet_id)
    timeout_seconds = get_env_int("OPENCLAW_TIMEOUT_SECONDS", 1200)
    max_attempts = get_env_int("OPENCLAW_MAX_ATTEMPTS", 2)
    thinking_level = os.environ.get("OPENCLAW_THINKING", "minimal").strip() or "minimal"
    heartbeat_seconds = get_env_int("OPENCLAW_HEARTBEAT_SECONDS", 30)
    provider = get_provider()

    print(f"{worker_prefix}Spreadsheet: {spreadsheet_id}", flush=True)
    print(f"{worker_prefix}Provider: {provider}", flush=True)
    print(f"{worker_prefix}OpenClaw default model: {get_openclaw_default_model()}", flush=True)
    print(
        f"{worker_prefix}Run config: timeout={timeout_seconds}s, thinking={thinking_level}, attempts={max_attempts}, heartbeat={heartbeat_seconds}s",
        flush=True,
    )

    for attempt in range(1, max_attempts + 1):
        session_id = f"spreadsheet-{uuid.uuid4().hex[:8]}"
        attempt_message = build_attempt_message(base_message, attempt)
        cmd = [
            "openclaw",
            "agent",
            "--session-id",
            session_id,
            "--thinking",
            thinking_level,
            "--timeout",
            str(timeout_seconds),
            "--message",
            attempt_message,
        ]
        if provider == "local":
            cmd.insert(4, "--local")

        print(f"{worker_prefix}Spawning agent: {session_id} (attempt {attempt}/{max_attempts})", flush=True)
        print(f"{worker_prefix}Running: {' '.join(cmd)}", flush=True)

        return_code, output = run_and_stream_with_heartbeat(
            cmd=cmd,
            env=os.environ.copy(),
            prefix=f"{worker_prefix}[agent] ",
            session_id=session_id,
            heartbeat_seconds=heartbeat_seconds,
        )
        spreadsheet_log = save_session_log(session_id, output)
        print(f"{worker_prefix}[spreadsheet] raw agent log saved: {spreadsheet_log}", flush=True)

        if return_code != 0:
            print(
                f"{worker_prefix}[spreadsheet] openclaw returned non-zero exit code: {return_code}",
                file=sys.stderr,
                flush=True,
            )
            if attempt == max_attempts:
                return return_code
            continue

        if SUCCESS_MARKER in output:
            return 0

        print(
            f"{worker_prefix}[spreadsheet] missing success marker `{SUCCESS_MARKER}` on attempt {attempt}.",
            file=sys.stderr,
            flush=True,
        )
        if attempt < max_attempts:
            print(f"{worker_prefix}[spreadsheet] retrying with a fresh session...", flush=True)

    return 3


if __name__ == "__main__":
    raise SystemExit(main())
