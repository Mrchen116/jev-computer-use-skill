"""Run fresh Sol/medium Codex sessions on read-only public sites or local fixtures."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from fixtures import CASES, FixtureServer
from live_cases import LIVE_CASES, LiveSuite, canonical, observed_pages
from miniwob_cases import MINIWOB_CASES, MiniWoBSuite

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "skills/jev-computer-use/scripts"
sys.path.insert(0, str(SOURCE))
from jev_computer_use.desktop import Desktop, nodes

RATES = {
    "sol_input": 4.0,
    "sol_cached": 0.4,
    "sol_write": 5.0,
    "sol_output": 20.0,
    "jev_input": 0.042,
    "jev_output": 0.0,
}


def cost(usage, jev):
    cached, written = (
        usage.get("cached_input_tokens", 0),
        usage.get("cache_write_input_tokens", 0),
    )
    return (
        (usage["input_tokens"] - cached - written) * RATES["sol_input"]
        + cached * RATES["sol_cached"]
        + written * RATES["sol_write"]
        + usage["output_tokens"] * RATES["sol_output"]
        + jev.get("input_tokens", 0) * RATES["jev_input"]
    ) / 1_000_000


def run_one(server, case, seed, arm, root, key_file, timeout):
    ident = f"{case}-{seed}-{arm}"
    try:
        return _run_one(server, case, seed, arm, root, key_file, timeout)
    finally:
        auth = root / ident / "home/auth.json"
        if auth.exists():
            auth.unlink()
        cleanup = Desktop()
        try:
            current = cleanup.execute({"verb": "app", "app": "com.google.Chrome"})
            world = server.worlds.get(ident)
            allowed = getattr(world, "allowed_prefixes", [server.origin + "/" + ident])
            current_host, current_path = canonical(current["url"])
            own_page = any(
                current_host == canonical(prefix)[0]
                and (
                    current_path == canonical(prefix)[1]
                    or current_path.startswith(canonical(prefix)[1] + "/")
                )
                for prefix in allowed
            )
            if own_page:
                cleanup.execute({"verb": "keyboard"}, "super+w")
        except RuntimeError as error:
            (root / ident / "cleanup-error.txt").write_text(str(error))
        finally:
            cleanup.close()


def _run_one(server, case, seed, arm, root, key_file, timeout):
    ident = f"{case}-{seed}-{arm}"
    directory = root / ident
    directory.mkdir()
    home = directory / "home"
    home.mkdir(mode=0o700)
    work = directory / "work"
    work.mkdir()
    auth = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "auth.json"
    shutil.copy2(auth, home / "auth.json")
    os.chmod(home / "auth.json", 0o600)
    world, url = server.add(case, seed, ident)
    setup_started = time.monotonic()
    desktop = Desktop()
    try:
        initial = desktop.execute({"verb": "app", "app": "com.google.Chrome"})
        if not nodes(initial["raw"]):
            raise RuntimeError(
                "Native CUA returned an empty accessibility tree; restore the UI before starting an evaluated agent"
            )
        desktop.execute({"verb": "keyboard"}, "super+n")
        desktop.execute({"verb": "app", "app": "com.google.Chrome"})
        address = desktop.execute({"verb": "keyboard"}, "super+l")
        focus = re.search(r"The focused UI element is (\d+)\b", address["raw"])
        fields = [field for field in address["fields"] if focus and field["ref"] == focus[1]]
        if len(fields) != 1:
            raise RuntimeError("Expected a focused address field after the location shortcut")
        desktop.execute(fields[0], url)
        loaded = desktop.execute({"verb": "enter"})
        load_deadline = time.monotonic() + 30
        while True:
            if canonical(loaded["url"]) == canonical(url) and nodes(loaded["raw"]):
                break
            if time.monotonic() >= load_deadline:
                (directory / "setup-failure.json").write_text(json.dumps({
                    "expected_url": url, "observed_url": loaded["url"],
                    "window": loaded["raw"].splitlines()[0] if loaded["raw"] else "",
                }, ensure_ascii=False))
                raise RuntimeError("The dedicated evaluation window did not load its starting page")
            time.sleep(.5)
            loaded = desktop.observe()
        if hasattr(world, "prepare"):
            world.prepare(desktop, loaded)
    finally:
        desktop.close()
    setup_seconds = time.monotonic() - setup_started
    mcp_args = [
        "-m",
        "jev_computer_use.mcp",
        "--journal",
        str(directory / "native.jsonl"),
    ]
    if arm == "hybrid":
        mcp_args += ["--hybrid", "--key-file", str(key_file)]
        if getattr(server, "protocol", "legacy") == "legacy":
            mcp_args.append("--legacy-stages")
    config = (
        """model="gpt-5.6-sol"
model_reasoning_effort="medium"
service_tier="default"
web_search="disabled"
[features]
shell_tool=false
multi_agent=false
[mcp_servers.cua_repl]
"""
        + f"command={json.dumps(sys.executable)}\nargs={json.dumps(mcp_args)}\ntool_timeout_sec=180\n"
        + f"[mcp_servers.cua_repl.env]\nPYTHONPATH={json.dumps(str(SOURCE))}\nJEV_EVAL_SCOPES={json.dumps(json.dumps(getattr(world, 'allowed_prefixes', [url])))}\n"
    )
    if arm == "hybrid":
        tool = "delegate_task" if getattr(server, "protocol", "legacy") == "general" else "delegate_stage"
        config += (
            f'[mcp_servers.cua_repl.tools.{tool}]\napproval_mode="approve"\n'
        )
        if tool == "delegate_task":
            # Deliver the large current UI directly. Code Mode otherwise has a
            # second 10k output cap independent of the MCP tool's own budget.
            config += 'output_token_limit=60000\n[features.code_mode]\ndirect_only_tool_namespaces=["mcp__cua_repl"]\n'
            config += '[mcp_servers.cua_repl.tools.read_task_history]\napproval_mode="approve"\n'
    (home / "config.toml").write_text(config)
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    (directory / "schema.json").write_text(json.dumps(schema))
    if getattr(world, "live", False):
        safety = (
            "This is a READ-ONLY public website task. Stay within these authorized URL prefixes: "
            + ", ".join(world.allowed_prefixes)
            + ". Do not sign in, submit forms, download, install, send messages, change accounts, star or edit anything. Navigation, search, sorting and reading are allowed."
        )
    else:
        safety = "Stay exclusively within this localhost demo. All displayed people, products and saves are synthetic and reversible."
    prompt = f"""Complete this computer-use task using the provided native cua_repl tools.
The harness has opened a NEW dedicated Google Chrome window at {url}. The app ID is com.google.Chrome; for native js access bind it with cua.getApp("com.google.Chrome"). Stay exclusively in this window. Do not create more windows, inspect or operate personal tabs, apps, files, accounts or system settings. {safety}
Use only documented CUA observation and UI action APIs. No filesystem, network requests, page source, DOM evaluation, hidden state, developer tools, or fixture/backend access. You may parse observed accessibility text and batch grounded deterministic actions/loops as native CUA permits; do not intentionally make extra model calls. Keep fresh observations after UI changes. Do not close the tab; the harness will clean up.
Task: {world.task}
Return a concise final answer with the requested evidence. Any URL must be the actual source URL you observed, not a guessed route.
"""
    if arm == "hybrid":
        if getattr(server, "protocol", "legacy") == "general":
            prompt += "\nUse the general Jev Skill below through the supplied delegate_task MCP tool (there is no shell in this evaluation). The tool uses the same runner as the CLI. The harness already bound its dedicated Chrome window; do not list apps first. Use this exact state_dir for every invocation: " + str(directory / "task-state") + ". A delegation is capped at 110 active seconds; choose a reasonable budget within that. Resume the same whole task with guidance/input_texts when useful. Native tools remain available for reasoning-heavy work or unsupported operations. Do not send every click through separate delegations.\n"
            prompt += (REPO / "skills/jev-computer-use/SKILL.md").read_text()
        else:
            prompt += (
                "\nUse the installed Jev Skill guidance below. It may bind the supplied Chrome app itself; a separate native binding call is unnecessary.\n"
                + (REPO / "skills/jev-computer-use/references/stages.md").read_text()
            )
    (directory / "prompt.txt").write_text(prompt)
    env = {
        k: v for k, v in os.environ.items() if not k.startswith(("CODEX_", "TYPESAFE_"))
    }
    env["CODEX_HOME"] = str(home)
    command = [
        "codex",
        "exec",
        "--json",
        "--skip-git-repo-check",
        "-s",
        "read-only",
        "-C",
        str(work),
        "--output-schema",
        str(directory / "schema.json"),
        "-o",
        str(directory / "answer.json"),
        "-",
    ]
    start = time.monotonic()
    with (
        (directory / "events.jsonl").open("w") as out,
        (directory / "stderr.txt").open("w") as err,
    ):
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=out,
            stderr=err,
            text=True,
            env=env,
            start_new_session=True,
        )
        process.stdin.write(prompt)
        process.stdin.close()
        timed_out = False
        interrupted = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=15)
        except KeyboardInterrupt:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=15)
            interrupted = True
    seconds = time.monotonic() - start
    answer = (
        json.loads((directory / "answer.json").read_text())["answer"]
        if (directory / "answer.json").exists()
        and (directory / "answer.json").stat().st_size
        else ""
    )
    events = [
        json.loads(l)
        for l in (directory / "events.jsonl").read_text().splitlines()
        if l.strip()
    ]
    usage = next(
        (e["usage"] for e in reversed(events) if e["type"] == "turn.completed"), None
    )
    actual = []
    provider_responses = set()
    max_request_input = 0
    for f in (home / "sessions").rglob("*.jsonl"):
        for line in f.open():
            item = json.loads(line)
            if item["type"] == "token_usage_record":
                provider_responses.add(item["payload"]["response_id"])
            if item["type"] == "turn_context":
                actual.append({k: item["payload"].get(k) for k in ("model", "effort")})
            if (
                item["type"] == "event_msg"
                and item["payload"].get("type") == "token_count"
            ):
                info = item["payload"].get("info") or {}
                max_request_input = max(
                    max_request_input,
                    (info.get("last_token_usage") or {}).get("input_tokens", 0),
                )
    journal = (
        [json.loads(l) for l in (directory / "native.jsonl").read_text().splitlines()]
        if (directory / "native.jsonl").exists()
        else []
    )
    jev = {"input_tokens": 0, "output_tokens": 0}
    unmetered_jev_calls = 0
    infrastructure_errors = []
    for event in journal:
        unmetered_jev_calls = max(
            unmetered_jev_calls, event.get("unmetered_jev_calls", 0)
        )
        if event.get("jev_usage_total") is not None:
            jev = event["jev_usage_total"]
        result_text = json.dumps(event.get("result", {}))
        if (
            "The Mac is locked" in result_text
            or "Browser is not available" in result_text
        ):
            infrastructure_errors.append("native_ui_unavailable")
    if getattr(world, "live", False):
        world.pages = observed_pages(journal)
    result = {
        "case": case,
        "seed": seed,
        "arm": arm,
        "seconds": seconds,
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "interrupted": interrupted,
        "setup_seconds": setup_seconds,
        "max_request_input_tokens": max_request_input,
        "llm_requests": len(provider_responses),
        "model_verified": bool(actual)
        and all(c == {"model": "gpt-5.6-sol", "effort": "medium"} for c in actual),
        "model_contexts": actual,
        "infrastructure_errors": sorted(set(infrastructure_errors)),
        "llm_usage": usage,
        "jev_usage": jev,
        "usd": cost(usage, jev) if usage and not unmetered_jev_calls else None,
        "known_usd": cost(usage, jev) if usage else None,
        "unmetered_jev_calls": unmetered_jev_calls,
        "judge": world.judge(answer, url),
        "answer": answer,
        "native_calls": max((e.get("native_calls", 0) for e in journal), default=0),
        "delegation": {
            "stages": sum(e.get("kind") in ("stage_detail", "task_detail") for e in journal),
            "actions_per_stage": [
                e["counts"]["actions"]
                for e in journal
                if e.get("kind") in ("stage_detail", "task_detail")
            ],
            "outcomes": [
                e["status"] for e in journal if e.get("kind") in ("stage_detail", "task_detail")
            ],
            "jev_seconds": sum(
                c["seconds"]
                for e in journal
                if e.get("kind") in ("stage_detail", "task_detail")
                for c in e["jev_calls"]
            ),
        },
    }
    (directory / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    print(
        json.dumps(
            {k: result[k] for k in ("case", "seed", "arm", "seconds", "usd", "judge")},
            ensure_ascii=False,
        ),
        flush=True,
    )
    if interrupted:
        # Preserve independent state even when the operator stops a bad attempt.
        # Missing final billing telemetry remains unknown, never an invented zero.
        raise KeyboardInterrupt
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--suite", choices=["live", "synthetic", "miniwob"], default="live")
    p.add_argument("--cases", nargs="+", choices=sorted(set(CASES) | set(LIVE_CASES) | set(MINIWOB_CASES)))
    p.add_argument("--miniwob-root", type=Path, help="Pinned Farama MiniWoB++ checkout")
    p.add_argument("--miniwob-deadline", type=int, default=300)
    p.add_argument("--seeds", nargs="+", type=int, default=[11])
    p.add_argument(
        "--arms",
        nargs="+",
        choices=["baseline", "hybrid"],
        default=["baseline", "hybrid"],
    )
    p.add_argument("--key-file", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--protocol", choices=["legacy", "general"], default="legacy")
    args = p.parse_args()
    permitted = {"live": LIVE_CASES, "synthetic": CASES, "miniwob": MINIWOB_CASES}[args.suite]
    if args.suite == "miniwob" and args.miniwob_root is None:
        p.error("--miniwob-root is required for MiniWoB++")
    if args.cases is None:
        args.cases = list(permitted)
    if any(case not in permitted for case in args.cases):
        p.error("Case is not part of the selected suite")
    if "hybrid" in args.arms and args.key_file is None:
        p.error("--key-file is required for hybrid")
    args.output.mkdir(parents=True, exist_ok=False)
    os.chmod(args.output, 0o700)
    sources = [
        *Path(__file__).parent.glob("*.py"),
        *SOURCE.glob("jev_computer_use/*.py"),
        REPO / "skills/jev-computer-use/references/stages.md",
        REPO / "skills/jev-computer-use/SKILL.md",
        REPO / "skills/jev-computer-use/references/tasks.md",
    ]
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "suite": args.suite,
        "protocol": args.protocol,
        "seeds": args.seeds,
        "cases": args.cases,
        "arms": args.arms,
        "rates_per_million": RATES,
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip(),
        "codex_version": subprocess.check_output(
            ["codex", "--version"], text=True
        ).strip(),
        "source_sha256": {
            str(f.relative_to(REPO)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(sources)
        },
    }
    if args.suite == "miniwob":
        server = MiniWoBSuite(args.miniwob_root, args.output, args.miniwob_deadline)
        manifest["miniwob"] = server.metadata()
    else:
        server = LiveSuite(args.output, args.cases) if args.suite == "live" else FixtureServer()
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    server.protocol = args.protocol
    results = []
    awake = (
        subprocess.Popen(["caffeinate", "-d", "-i", "-w", str(os.getpid())])
        if shutil.which("caffeinate")
        else None
    )
    try:
        for i, seed in enumerate(args.seeds):
            for j, case in enumerate(args.cases):
                arms = args.arms if (i + j) % 2 == 0 else args.arms[::-1]
                for arm in arms:
                    result = run_one(
                        server,
                        case,
                        seed,
                        arm,
                        args.output,
                        args.key_file,
                        args.timeout,
                    )
                    results.append(result)
                    if result["infrastructure_errors"]:
                        raise RuntimeError(
                            "Native UI is unavailable; resolve the environment before continuing the suite"
                        )
    finally:
        server.close()
        if awake is not None:
            awake.terminate()
            awake.wait()
        (args.output / "results.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2)
        )


if __name__ == "__main__":

    def terminate(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    main()
