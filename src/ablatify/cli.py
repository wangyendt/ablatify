from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Sequence

from . import __version__


REPO_ROOT = Path(__file__).resolve().parents[2]
CODEX_ENGINE = REPO_ROOT / "vendor" / "codex-keysmith" / "codex-instruct.py"
CLAUDE_ENGINE = REPO_ROOT / "vendor" / "claude-keysmith" / "claude-instruct.py"


@dataclass
class ProviderResult:
    provider: str
    exitCode: int
    outcome: str
    path: str
    stdout: str
    stderr: str
    details: object | None = None


def _run_engine(script: Path, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )


def _passthrough(provider: str, arguments: Sequence[str]) -> int:
    forwarded = list(arguments)
    if forwarded[:1] == ["--"]:
        forwarded = forwarded[1:]
    script = CODEX_ENGINE if provider == "codex" else CLAUDE_ENGINE
    result = _run_engine(script, forwarded)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def _collect_status(
    target: str,
    *,
    codex_dir_value: str | None = None,
    scope: str = "user",
    project_dir: str | None = None,
    name: str | None = None,
    runtime: bool = False,
) -> dict[str, ProviderResult]:
    results: dict[str, ProviderResult] = {}
    codex_dir = Path(codex_dir_value or os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    if target in ("codex", "all"):
        codex = _run_engine(
            CODEX_ENGINE,
            ["--status", "--codex-dir", str(codex_dir), "--lang", "en"],
        )
        activation_match = re.search(r"Config activation:\s*([^\s]+)", codex.stdout)
        health_match = re.search(r"Structural health:\s*([^\s]+)", codex.stdout)
        details = {
            "activation": activation_match.group(1)
            if activation_match
            else "not-installed"
            if not codex_dir.exists()
            else "unknown",
            "health": health_match.group(1) if health_match else "unknown",
        }
        results["codex"] = ProviderResult(
            provider="codex",
            exitCode=codex.returncode,
            outcome="checked" if codex.returncode in (0, 1) else "error",
            path=str(codex_dir),
            stdout=codex.stdout,
            stderr=codex.stderr,
            details=details,
        )
    if target in ("claude", "all"):
        claude_arguments = ["status", "--scope", scope, "--json"]
        if project_dir:
            claude_arguments.extend(["--project-dir", project_dir])
        if name:
            claude_arguments.extend(["--name", name])
        if runtime:
            claude_arguments.append("--runtime")
        claude = _run_engine(CLAUDE_ENGINE, claude_arguments)
        try:
            details = json.loads(claude.stdout) if claude.stdout else None
        except json.JSONDecodeError:
            details = None
        results["claude"] = ProviderResult(
            provider="claude",
            exitCode=claude.returncode,
            outcome="checked" if claude.returncode == 0 else "error",
            path=project_dir or str(Path.home() / ".claude"),
            stdout=claude.stdout,
            stderr=claude.stderr,
            details=details,
        )
    return results


def _status(
    target: str = "all",
    output_format: str = "text",
    *,
    check: bool = False,
    verbose: bool = False,
    codex_dir: str | None = None,
    scope: str = "user",
    project_dir: str | None = None,
    name: str | None = None,
    runtime: bool = False,
    lang: str = "auto",
) -> int:
    results = _collect_status(
        target,
        codex_dir_value=codex_dir,
        scope=scope,
        project_dir=project_dir,
        name=name,
        runtime=runtime,
    )
    successful = all(result.outcome == "checked" for result in results.values())
    installed = True
    for provider, result in results.items():
        if provider == "codex":
            details = result.details if isinstance(result.details, dict) else {}
            installed = installed and details.get("activation") in ("active", "inactive-by-config")
            installed = installed and details.get("health") == "healthy"
        else:
            details = result.details if isinstance(result.details, dict) else {}
            installed = installed and details.get("installed") is True
    if output_format == "json":
        status_ok = successful and (installed or not check)
        payload = {
            "schemaVersion": 1,
            "command": "status",
            "results": {name: asdict(result) for name, result in results.items()},
            "summary": {"outcome": "success" if status_ok else "failed"},
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0 if status_ok else 1

    chinese = lang == "zh-CN" or (lang == "auto" and os.environ.get("LANG", "").lower().startswith("zh"))
    print("Ablatify 状态" if chinese else "Ablatify status")
    for provider, result in results.items():
        details = result.details if isinstance(result.details, dict) else {}
        if provider == "codex":
            state = str(details.get("activation", result.outcome))
        else:
            state = "installed" if details.get("installed") is True else "not-installed"
        print("  {:<7} {:<18} {}".format(provider.title(), state, result.path))
        if verbose:
            if result.stdout:
                print(result.stdout.rstrip())
            if result.stderr:
                print(result.stderr.rstrip(), file=sys.stderr)
    print("\n下一步：" if chinese else "\nNext steps:")
    print("  ablatify deploy codex")
    print("  ablatify deploy claude")
    return 0 if successful and (installed or not check) else 1


def _operation_exit_code(results: dict[str, ProviderResult]) -> int:
    succeeded = sum(result.exitCode == 0 for result in results.values())
    if succeeded == len(results):
        return 0
    if succeeded:
        return 4
    return 1


def _operation_payload(command: str, results: dict[str, ProviderResult]) -> dict[str, object]:
    exit_code = _operation_exit_code(results)
    return {
        "schemaVersion": 1,
        "command": command,
        "results": {name: asdict(result) for name, result in results.items()},
        "summary": {
            "outcome": "success" if exit_code == 0 else "partial" if exit_code == 4 else "failed"
        },
    }


def _resolve_target(positional: str | None, option: str | None) -> str:
    if positional and option and positional != option:
        raise ValueError("target was specified twice with different values")
    target = positional or option
    if target is None:
        raise ValueError("choose a target: codex, claude, or all")
    return target


def _validate_deploy_options(options: argparse.Namespace) -> None:
    target = _resolve_target(options.target, options.target_option)
    if target == "codex":
        if options.project_dir:
            raise ValueError("--project-dir only applies to Claude")
        if options.scope or options.claude_scope:
            raise ValueError("--scope only applies to Claude")
        if options.runtime or options.append_file or options.max_tokens is not None:
            raise ValueError("--runtime, --append-file, and --max-tokens only apply to Claude")
    if target == "claude":
        if options.codex_dir:
            raise ValueError("--codex-dir only applies to Codex")
        if options.skip_hooks_isolation:
            raise ValueError("--skip-hooks-isolation only applies to Codex")


def _deploy_arguments(provider: str, options: argparse.Namespace, *, apply: bool) -> list[str]:
    if provider == "codex":
        codex_dir = options.codex_dir or os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
        arguments = ["--codex-dir", codex_dir, "--lang", options.lang]
        if options.file:
            arguments.extend(["--file", options.file])
        if options.name:
            arguments.extend(["--name", options.name])
        if options.skip_hooks_isolation:
            arguments.append("--skip-hooks-isolation")
    else:
        scope = options.scope or options.claude_scope or "user"
        arguments = ["install", "--scope", scope]
        if options.project_dir:
            arguments.extend(["--project-dir", options.project_dir])
        if options.file:
            arguments.extend(["--file", options.file])
        if options.name:
            arguments.extend(["--name", options.name])
        if options.runtime:
            arguments.append("--runtime")
        if options.append_file:
            arguments.extend(["--append-file", options.append_file])
        if options.max_tokens is not None:
            arguments.extend(["--max-tokens", str(options.max_tokens)])
    arguments.append("--yes" if apply else "--dry-run")
    return arguments


def _claude_scope_conflict(options: argparse.Namespace) -> str | None:
    scope = options.scope or options.claude_scope or "user"
    if scope not in ("project", "local"):
        return None
    project = Path(options.project_dir or os.getcwd()).expanduser().resolve()
    other_scope = "local" if scope == "project" else "project"
    other_memory = project / ("CLAUDE.local.md" if other_scope == "local" else "CLAUDE.md")
    if not other_memory.is_file():
        return None
    name = options.name or "claude-project-rules"
    marker = "<!-- claude-keysmith:start name={} -->".format(name)
    try:
        contents = other_memory.read_text(encoding="utf-8")
    except OSError:
        return None
    if marker in contents:
        return (
            "instruction name {!r} is already used by Claude {} scope in {}; "
            "choose a different --name"
        ).format(name, other_scope, other_memory)
    return None


def _run_deploy(options: argparse.Namespace, *, apply: bool) -> dict[str, ProviderResult]:
    target = _resolve_target(options.target, options.target_option)
    results: dict[str, ProviderResult] = {}
    for provider in ("codex", "claude"):
        if target not in (provider, "all"):
            continue
        if provider == "claude":
            conflict = _claude_scope_conflict(options)
            if conflict:
                results[provider] = ProviderResult(
                    provider="claude",
                    exitCode=1,
                    outcome="error",
                    path=options.project_dir or os.getcwd(),
                    stdout="",
                    stderr="Ablatify: {}\n".format(conflict),
                )
                continue
        script = CODEX_ENGINE if provider == "codex" else CLAUDE_ENGINE
        arguments = _deploy_arguments(provider, options, apply=apply)
        process = _run_engine(script, arguments)
        result_path = (
            options.codex_dir or os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
            if provider == "codex"
            else options.project_dir or str(Path.home() / ".claude")
        )
        results[provider] = ProviderResult(
            provider=provider,
            exitCode=process.returncode,
            outcome="applied" if apply and process.returncode == 0 else "previewed" if process.returncode == 0 else "error",
            path=result_path,
            stdout=process.stdout,
            stderr=process.stderr,
        )
    return results


def _print_operation(
    command: str,
    results: dict[str, ProviderResult],
    output_format: str,
    *,
    verbose: bool = False,
    lang: str = "en",
) -> int:
    exit_code = _operation_exit_code(results)
    if output_format == "json":
        print(json.dumps(_operation_payload(command, results), ensure_ascii=False, sort_keys=True))
        return exit_code
    chinese = lang == "zh-CN" or (lang == "auto" and os.environ.get("LANG", "").lower().startswith("zh"))
    command_names = {
        "deploy": "部署",
        "uninstall": "卸载",
        "doctor": "诊断",
        "recover": "恢复事务",
        "restore-hooks": "恢复 hooks",
        "restore": "恢复备份",
    }
    outcomes = {"applied": "已应用", "previewed": "已预览", "checked": "已检查", "error": "错误"}
    print("Ablatify {}".format(command_names.get(command, command) if chinese else command))
    for provider, result in results.items():
        outcome = outcomes.get(result.outcome, result.outcome) if chinese else result.outcome
        print("  {:<7} {:<10} {}".format(provider.title(), outcome, result.path))
        show_native = verbose or result.exitCode != 0
        if show_native and result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if show_native and result.stderr:
            print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
    return exit_code


def _deploy(options: argparse.Namespace) -> int:
    _validate_deploy_options(options)
    if options.yes and not options.dry_run:
        return _print_operation(
            "deploy",
            _run_deploy(options, apply=True),
            options.format,
            verbose=options.verbose,
            lang=options.lang,
        )

    preview = _run_deploy(options, apply=False)
    preview_exit = _print_operation(
        "deploy", preview, options.format, verbose=options.verbose, lang=options.lang
    )
    if preview_exit != 0 or options.dry_run or options.format == "json":
        return preview_exit

    target = _resolve_target(options.target, options.target_option)
    if sys.stdin.isatty() and sys.stdout.isatty():
        answer = input("\nApply the changes above? [y/N] ").strip().lower()
        if answer in ("y", "yes"):
            return _print_operation(
                "deploy",
                _run_deploy(options, apply=True),
                options.format,
                verbose=options.verbose,
                lang=options.lang,
            )
        print("No changes were applied.")
        return 0

    print("\nPreview only: rerun with --yes to apply:")
    print("  ablatify deploy {} --yes".format(target))
    return 0


def _uninstall_arguments(provider: str, options: argparse.Namespace, *, apply: bool) -> list[str]:
    if provider == "codex":
        codex_dir = options.codex_dir or os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
        arguments = ["--uninstall", "--codex-dir", codex_dir, "--lang", options.lang]
    else:
        scope = options.scope or options.claude_scope or "user"
        arguments = ["uninstall", "--scope", scope]
        if options.project_dir:
            arguments.extend(["--project-dir", options.project_dir])
        if options.name:
            arguments.extend(["--name", options.name])
        if options.runtime:
            arguments.append("--runtime")
    arguments.append("--yes" if apply else "--dry-run")
    return arguments


def _validate_uninstall_options(options: argparse.Namespace) -> None:
    target = _resolve_target(options.target, options.target_option)
    if target == "codex" and (options.project_dir or options.scope or options.claude_scope or options.runtime):
        raise ValueError("--scope, --project-dir, and --runtime only apply to Claude")
    if target == "claude" and options.codex_dir:
        raise ValueError("--codex-dir only applies to Codex")


def _run_uninstall(options: argparse.Namespace, *, apply: bool) -> dict[str, ProviderResult]:
    target = _resolve_target(options.target, options.target_option)
    results: dict[str, ProviderResult] = {}
    for provider in ("codex", "claude"):
        if target not in (provider, "all"):
            continue
        script = CODEX_ENGINE if provider == "codex" else CLAUDE_ENGINE
        process = _run_engine(script, _uninstall_arguments(provider, options, apply=apply))
        results[provider] = ProviderResult(
            provider=provider,
            exitCode=process.returncode,
            outcome="applied" if apply and process.returncode == 0 else "previewed" if process.returncode == 0 else "error",
            path=(options.codex_dir or os.environ.get("CODEX_HOME") or str(Path.home() / ".codex"))
            if provider == "codex"
            else (options.project_dir or str(Path.home() / ".claude")),
            stdout=process.stdout,
            stderr=process.stderr,
        )
    return results


def _uninstall(options: argparse.Namespace) -> int:
    _validate_uninstall_options(options)
    if options.yes and not options.dry_run:
        return _print_operation(
            "uninstall",
            _run_uninstall(options, apply=True),
            options.format,
            verbose=options.verbose,
            lang=options.lang,
        )
    preview = _run_uninstall(options, apply=False)
    preview_exit = _print_operation(
        "uninstall", preview, options.format, verbose=options.verbose, lang=options.lang
    )
    if preview_exit != 0 or options.dry_run or options.format == "json":
        return preview_exit
    target = _resolve_target(options.target, options.target_option)
    if sys.stdin.isatty() and sys.stdout.isatty():
        answer = input("\nApply the changes above? [y/N] ").strip().lower()
        if answer in ("y", "yes"):
            return _print_operation(
                "uninstall",
                _run_uninstall(options, apply=True),
                options.format,
                verbose=options.verbose,
                lang=options.lang,
            )
        print("No changes were applied.")
        return 0
    print("\nPreview only: rerun with --yes to apply:")
    print("  ablatify uninstall {} --yes".format(target))
    return 0


def _doctor(options: argparse.Namespace) -> int:
    process = _run_engine(CLAUDE_ENGINE, ["doctor", "--json"])
    try:
        details = json.loads(process.stdout) if process.stdout else None
    except json.JSONDecodeError:
        details = None
    result = ProviderResult(
        provider="claude",
        exitCode=process.returncode,
        outcome="checked" if process.returncode == 0 else "error",
        path=str(Path.home() / ".claude"),
        stdout=process.stdout,
        stderr=process.stderr,
        details=details,
    )
    return _print_operation("doctor", {"claude": result}, options.format)


def _recover(options: argparse.Namespace) -> int:
    codex_dir = options.codex_dir or os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
    arguments = ["--recover", "--codex-dir", codex_dir, "--lang", "en"]
    if options.yes and not options.dry_run:
        arguments.append("--yes")
    process = _run_engine(CODEX_ENGINE, arguments)
    result = ProviderResult(
        provider="codex",
        exitCode=process.returncode,
        outcome="applied" if options.yes and process.returncode == 0 else "previewed" if process.returncode == 0 else "error",
        path=codex_dir,
        stdout=process.stdout,
        stderr=process.stderr,
    )
    return _print_operation("recover", {"codex": result}, options.format)


def _restore_hooks(options: argparse.Namespace) -> int:
    codex_dir = options.codex_dir or os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
    process = _run_engine(
        CODEX_ENGINE,
        ["--restore-hooks", "--codex-dir", codex_dir, "--lang", "en"],
    )
    result = ProviderResult(
        provider="codex",
        exitCode=process.returncode,
        outcome="applied" if process.returncode == 0 else "error",
        path=codex_dir,
        stdout=process.stdout,
        stderr=process.stderr,
    )
    return _print_operation("restore-hooks", {"codex": result}, options.format)


def _restore_claude(options: argparse.Namespace) -> int:
    arguments = ["restore", "--target", options.target_file, "--backup", options.backup]
    if options.yes and not options.dry_run:
        arguments.append("--yes")
    else:
        arguments.append("--dry-run")
    process = _run_engine(CLAUDE_ENGINE, arguments)
    result = ProviderResult(
        provider="claude",
        exitCode=process.returncode,
        outcome="applied" if options.yes and process.returncode == 0 else "previewed" if process.returncode == 0 else "error",
        path=options.target_file,
        stdout=process.stdout,
        stderr=process.stderr,
    )
    return _print_operation("restore", {"claude": result}, options.format)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ablatify")
    parser.add_argument("--version", action="version", version="%(prog)s {}".format(__version__))
    subparsers = parser.add_subparsers(dest="command")
    status = subparsers.add_parser("status", help="show provider status")
    status.add_argument("target", nargs="?", choices=("codex", "claude", "all"))
    status.add_argument("--target", dest="target_option", choices=("codex", "claude", "all"))
    status.add_argument("--format", choices=("text", "json"), default="text")
    status.add_argument("--check", action="store_true")
    status.add_argument("--verbose", action="store_true")
    status.add_argument("--codex-dir")
    status.add_argument("--scope", choices=("user", "project", "local"), default="user")
    status.add_argument("--project-dir")
    status.add_argument("--name")
    status.add_argument("--runtime", action="store_true")
    status.add_argument("--lang", choices=("auto", "zh-CN", "en"), default="auto")
    deploy = subparsers.add_parser("deploy", help="preview or apply an instruction profile")
    deploy.add_argument("target", nargs="?", choices=("codex", "claude", "all"))
    deploy.add_argument("--target", dest="target_option", choices=("codex", "claude", "all"))
    deploy.add_argument("--dry-run", action="store_true")
    deploy.add_argument("--yes", action="store_true")
    deploy.add_argument("--file")
    deploy.add_argument("--name")
    deploy.add_argument("--codex-dir")
    deploy.add_argument("--scope", choices=("user", "project", "local"))
    deploy.add_argument("--claude-scope", choices=("user", "project", "local"))
    deploy.add_argument("--project-dir")
    deploy.add_argument("--runtime", action="store_true")
    deploy.add_argument("--append-file")
    deploy.add_argument("--max-tokens", type=int)
    deploy.add_argument("--skip-hooks-isolation", action="store_true")
    deploy.add_argument("--format", choices=("text", "json"), default="text")
    deploy.add_argument("--verbose", action="store_true")
    deploy.add_argument("--lang", choices=("auto", "zh-CN", "en"), default="auto")
    uninstall = subparsers.add_parser("uninstall", help="preview or remove an instruction profile")
    uninstall.add_argument("target", nargs="?", choices=("codex", "claude", "all"))
    uninstall.add_argument("--target", dest="target_option", choices=("codex", "claude", "all"))
    uninstall.add_argument("--dry-run", action="store_true")
    uninstall.add_argument("--yes", action="store_true")
    uninstall.add_argument("--name")
    uninstall.add_argument("--codex-dir")
    uninstall.add_argument("--scope", choices=("user", "project", "local"))
    uninstall.add_argument("--claude-scope", choices=("user", "project", "local"))
    uninstall.add_argument("--project-dir")
    uninstall.add_argument("--runtime", action="store_true")
    uninstall.add_argument("--format", choices=("text", "json"), default="text")
    uninstall.add_argument("--verbose", action="store_true")
    uninstall.add_argument("--lang", choices=("auto", "zh-CN", "en"), default="auto")
    doctor = subparsers.add_parser("doctor", help="diagnose the Claude runtime integration")
    doctor.add_argument("target", choices=("claude",))
    doctor.add_argument("--format", choices=("text", "json"), default="text")
    recover = subparsers.add_parser("recover", help="preview or recover interrupted Codex transactions")
    recover.add_argument("target", choices=("codex",))
    recover.add_argument("--codex-dir")
    recover.add_argument("--dry-run", action="store_true")
    recover.add_argument("--yes", action="store_true")
    recover.add_argument("--format", choices=("text", "json"), default="text")
    restore_hooks = subparsers.add_parser("restore-hooks", help="restore Codex hooks.json")
    restore_hooks.add_argument("target", choices=("codex",))
    restore_hooks.add_argument("--codex-dir")
    restore_hooks.add_argument("--format", choices=("text", "json"), default="text")
    restore = subparsers.add_parser("restore", help="preview or restore a Claude backup")
    restore.add_argument("target", choices=("claude",))
    restore.add_argument("--target-file", required=True)
    restore.add_argument("--backup", required=True)
    restore.add_argument("--dry-run", action="store_true")
    restore.add_argument("--yes", action="store_true")
    restore.add_argument("--format", choices=("text", "json"), default="text")
    for provider in ("codex", "claude"):
        native = subparsers.add_parser(provider, help="pass arguments to the {} engine".format(provider))
        native.add_argument("arguments", nargs=argparse.REMAINDER)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        return _status()
    options = _parser().parse_args(arguments)
    if options.command == "status":
        try:
            status_target = _resolve_target(options.target, options.target_option)
        except ValueError as error:
            if options.target is None and options.target_option is None:
                status_target = "all"
            else:
                _parser().error(str(error))
        return _status(
            status_target,
            options.format,
            check=options.check,
            verbose=options.verbose,
            codex_dir=options.codex_dir,
            scope=options.scope,
            project_dir=options.project_dir,
            name=options.name,
            runtime=options.runtime,
            lang=options.lang,
        )
    if options.command == "deploy":
        try:
            return _deploy(options)
        except ValueError as error:
            _parser().error(str(error))
    if options.command == "uninstall":
        try:
            return _uninstall(options)
        except ValueError as error:
            _parser().error(str(error))
    if options.command == "doctor":
        return _doctor(options)
    if options.command == "recover":
        return _recover(options)
    if options.command == "restore-hooks":
        return _restore_hooks(options)
    if options.command == "restore":
        return _restore_claude(options)
    if options.command in ("codex", "claude"):
        return _passthrough(options.command, options.arguments)
    _parser().print_help()
    return 0
