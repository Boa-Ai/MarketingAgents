from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

SPREADSHEET_AGENT = Path("spreadsheet_agent/run.py")
SUPPORTED_PROVIDERS = {"local", "anthropic"}


def usage() -> str:
    return (
        "Usage:\n"
        "  python main.py <agent_name> [--count N] [--provider local|anthropic] [--anthropic|--local] [agent_args...]\n\n"
        "Available agents: spreadsheet_agent\n\n"
        "Examples:\n"
        "  python main.py spreadsheet_agent YOUR_SPREADSHEET_ID\n"
        "  python main.py spreadsheet_agent --count 3 YOUR_SPREADSHEET_ID\n"
        "  python main.py spreadsheet_agent --anthropic YOUR_SPREADSHEET_ID"
    )


def parse_launcher_args(args: list[str]) -> tuple[int, str, list[str]]:
    count = 1
    provider = "local"
    remaining: list[str] = []
    i = 0
    seen_count = False
    seen_provider = False

    while i < len(args):
        token = args[i]
        if token == "--count":
            if seen_count:
                raise ValueError("`--count` specified more than once.")
            if i + 1 >= len(args):
                raise ValueError("`--count` requires a value, e.g. `--count 3`.")
            raw = args[i + 1].strip()
            i += 2
            seen_count = True
        elif token.startswith("--count="):
            if seen_count:
                raise ValueError("`--count` specified more than once.")
            raw = token.split("=", 1)[1].strip()
            i += 1
            seen_count = True
        elif token == "--provider":
            if seen_provider:
                raise ValueError("Provider specified more than once.")
            if i + 1 >= len(args):
                raise ValueError("`--provider` requires a value: local or anthropic.")
            raw_provider = args[i + 1].strip().lower()
            i += 2
            seen_provider = True
            if raw_provider not in SUPPORTED_PROVIDERS:
                raise ValueError(f"Invalid `--provider` value: {raw_provider!r}.")
            provider = raw_provider
            continue
        elif token.startswith("--provider="):
            if seen_provider:
                raise ValueError("Provider specified more than once.")
            raw_provider = token.split("=", 1)[1].strip().lower()
            i += 1
            seen_provider = True
            if raw_provider not in SUPPORTED_PROVIDERS:
                raise ValueError(f"Invalid `--provider` value: {raw_provider!r}.")
            provider = raw_provider
            continue
        elif token == "--anthropic":
            if seen_provider:
                raise ValueError("Provider specified more than once.")
            provider = "anthropic"
            seen_provider = True
            i += 1
            continue
        elif token == "--local":
            if seen_provider:
                raise ValueError("Provider specified more than once.")
            provider = "local"
            seen_provider = True
            i += 1
            continue
        else:
            remaining.append(token)
            i += 1
            continue

        try:
            parsed = int(raw)
        except ValueError as exc:
            raise ValueError(f"Invalid `--count` value: {raw!r}. Must be a positive integer.") from exc
        if parsed < 1:
            raise ValueError("`--count` must be >= 1.")
        count = parsed

    return count, provider, remaining


def load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def get_openclaw_model() -> str:
    proc = subprocess.run(
        ["openclaw", "config", "get", "agents.defaults.model.primary"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def ensure_openclaw_model(model: str) -> None:
    if shutil.which("openclaw") is None:
        raise RuntimeError("`openclaw` not found on PATH; cannot set OPENCLAW_MODEL.")

    current = get_openclaw_model()
    if current == model:
        print(f"[main] OPENCLAW_MODEL already set: {model}", flush=True)
        return

    cmd = ["openclaw", "models", "set", model]
    print(f"[main] setting OpenClaw model: {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
        raise RuntimeError(f"Failed to set OPENCLAW_MODEL={model!r}: {detail}")

    resolved = get_openclaw_model()
    if resolved:
        print(f"[main] OpenClaw default model is now: {resolved}", flush=True)


def main() -> int:
    load_dotenv()

    if len(sys.argv) < 2:
        print(usage(), file=sys.stderr)
        return 1

    agent_name = sys.argv[1].strip()
    if agent_name != "spreadsheet_agent":
        print(f"Unknown agent: {agent_name}\n", file=sys.stderr)
        print(usage(), file=sys.stderr)
        return 1

    try:
        count, provider, agent_args = parse_launcher_args(sys.argv[2:])
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        print(usage(), file=sys.stderr)
        return 1

    if provider == "anthropic":
        requested_model = os.environ.get("OPENCLAW_ANTHROPIC_MODEL", "").strip()
    else:
        requested_model = os.environ.get("OPENCLAW_MODEL", "").strip()

    if requested_model:
        try:
            ensure_openclaw_model(requested_model)
        except RuntimeError as err:
            print(f"Error: {err}", file=sys.stderr)
            return 1
    elif provider == "anthropic":
        current_model = get_openclaw_model() or "(unknown)"
        print(
            f"[main] warning: OPENCLAW_ANTHROPIC_MODEL is not set; using current default model: {current_model}",
            flush=True,
        )
        if current_model.startswith("ollama/"):
            print(
                "[main] warning: provider=anthropic with an Ollama default model may run slowly or unexpectedly. "
                "Set OPENCLAW_ANTHROPIC_MODEL (e.g. claude-sonnet-4-5) to force Anthropic.",
                flush=True,
            )

    print(f"[main] launching {count} spreadsheet worker(s) with provider={provider}", flush=True)

    procs: list[tuple[int, subprocess.Popen[str]]] = []
    for i in range(count):
        cmd = [sys.executable, str(SPREADSHEET_AGENT), *agent_args]
        env = os.environ.copy()
        env["OPENCLAW_PROVIDER"] = provider
        env["SPREADSHEET_WORKER_ID"] = str(i + 1)
        env["PYTHONUNBUFFERED"] = "1"
        print(f"[main] starting worker {i + 1}: {' '.join(cmd)}", flush=True)
        proc = subprocess.Popen(
            cmd,
            text=True,
            env=env,
        )
        procs.append((i + 1, proc))

    exit_codes: list[int] = []
    for worker_id, proc in procs:
        worker_code = proc.wait()
        print(f"[main] worker {worker_id} exit code: {worker_code}", flush=True)
        exit_codes.append(worker_code)

    return 0 if all(code == 0 for code in exit_codes) else 1


if __name__ == "__main__":
    for _ in range(31):
        exit_code = main()
        if exit_code != 0:
            raise SystemExit(exit_code)
    raise SystemExit(0)
