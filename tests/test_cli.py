from __future__ import annotations

import os
from pathlib import Path
import json
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_ablatify(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "CODEX_HOME": str(home / ".codex"),
            "PYTHONPATH": str(REPO_ROOT / "src"),
        }
    )
    return subprocess.run(
        [sys.executable, "-m", "ablatify", *args],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_no_arguments_reports_both_providers_without_writing(tmp_path: Path) -> None:
    result = run_ablatify(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "Codex" in result.stdout
    assert "Claude" in result.stdout
    assert "ablatify deploy codex" in result.stdout
    assert list((tmp_path / "home").iterdir()) == []


def test_status_json_has_a_versioned_provider_envelope(tmp_path: Path) -> None:
    result = run_ablatify(tmp_path, "status", "--format", "json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schemaVersion"] == 1
    assert payload["command"] == "status"
    assert set(payload["results"]) == {"codex", "claude"}
    assert payload["summary"]["outcome"] == "success"


def test_native_provider_passthrough_preserves_output_and_exit_code(tmp_path: Path) -> None:
    codex = run_ablatify(tmp_path, "codex", "--", "--version")
    claude = run_ablatify(tmp_path, "claude", "--", "--version")

    assert codex.returncode == 0, codex.stderr
    assert "codex-instruct" in codex.stdout
    assert claude.returncode == 0, claude.stderr
    assert "claude-keysmith v6" in claude.stdout


def test_codex_deploy_dry_run_previews_default_home_without_writing(tmp_path: Path) -> None:
    codex_dir = tmp_path / "home" / ".codex"
    codex_dir.mkdir(parents=True)
    config = codex_dir / "config.toml"
    config.write_text('model = "gpt-5"\n', encoding="utf-8")

    result = run_ablatify(tmp_path, "deploy", "codex", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "Codex" in result.stdout
    assert "dry-run" in result.stdout.lower() or "preview" in result.stdout.lower()
    assert config.read_text(encoding="utf-8") == 'model = "gpt-5"\n'
    assert not (codex_dir / "gpt-unrestricted.md").exists()


def test_deploy_all_yes_applies_each_provider_default_profile(tmp_path: Path) -> None:
    codex_dir = tmp_path / "home" / ".codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "config.toml").write_text('model = "gpt-5"\n', encoding="utf-8")

    result = run_ablatify(tmp_path, "deploy", "all", "--yes")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (codex_dir / "gpt-unrestricted.md").is_file()
    assert (codex_dir / ".codex-keysmith-manifest.json").is_file()
    claude_home = tmp_path / "home" / ".claude"
    assert (claude_home / "keysmith" / "claude-project-rules.md").is_file()
    assert "<!-- claude-keysmith:start" in (claude_home / "CLAUDE.md").read_text(encoding="utf-8")


def test_noninteractive_deploy_without_yes_only_previews_and_prints_retry(tmp_path: Path) -> None:
    result = run_ablatify(tmp_path, "deploy", "claude")

    assert result.returncode == 0, result.stderr
    assert "ablatify deploy claude --yes" in result.stdout
    assert not (tmp_path / "home" / ".claude").exists()


def test_uninstall_all_yes_removes_the_default_global_profiles(tmp_path: Path) -> None:
    codex_dir = tmp_path / "home" / ".codex"
    codex_dir.mkdir(parents=True)
    original_config = 'model = "gpt-5"\n'
    (codex_dir / "config.toml").write_text(original_config, encoding="utf-8")
    deployed = run_ablatify(tmp_path, "deploy", "all", "--yes")
    assert deployed.returncode == 0, deployed.stdout + deployed.stderr

    result = run_ablatify(tmp_path, "uninstall", "all", "--yes")

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (codex_dir / "gpt-unrestricted.md").exists()
    assert (codex_dir / "config.toml").read_text(encoding="utf-8") == original_config
    claude_home = tmp_path / "home" / ".claude"
    assert not (claude_home / "keysmith" / "claude-project-rules.md").exists()
    assert "<!-- claude-keysmith:start" not in (claude_home / "CLAUDE.md").read_text(encoding="utf-8")


def test_claude_project_and_local_scopes_reject_the_same_managed_name(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    first = run_ablatify(
        tmp_path,
        "deploy",
        "claude",
        "--scope",
        "project",
        "--project-dir",
        str(project),
        "--name",
        "shared",
        "--yes",
    )
    assert first.returncode == 0, first.stdout + first.stderr

    conflict = run_ablatify(
        tmp_path,
        "deploy",
        "claude",
        "--scope",
        "local",
        "--project-dir",
        str(project),
        "--name",
        "shared",
        "--yes",
    )

    assert conflict.returncode == 1
    assert "already used by Claude project scope" in conflict.stderr
    assert not (project / "CLAUDE.local.md").exists()


def test_all_targets_report_partial_success_with_exit_code_four(tmp_path: Path) -> None:
    result = run_ablatify(tmp_path, "deploy", "all", "--yes", "--format", "json")

    assert result.returncode == 4
    payload = json.loads(result.stdout)
    assert payload["summary"]["outcome"] == "partial"
    assert payload["results"]["codex"]["exitCode"] != 0
    assert payload["results"]["claude"]["exitCode"] == 0


def test_status_check_fails_until_the_selected_provider_is_installed(tmp_path: Path) -> None:
    before = run_ablatify(tmp_path, "status", "claude", "--check")
    assert before.returncode == 1
    assert "not-installed" in before.stdout

    deployed = run_ablatify(tmp_path, "deploy", "claude", "--yes")
    assert deployed.returncode == 0, deployed.stdout + deployed.stderr
    after = run_ablatify(tmp_path, "status", "claude", "--check")
    assert after.returncode == 0, after.stdout + after.stderr
    assert "installed" in after.stdout


def test_doctor_claude_exposes_the_native_diagnostics_as_json(tmp_path: Path) -> None:
    result = run_ablatify(tmp_path, "doctor", "claude", "--format", "json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schemaVersion"] == 1
    assert payload["command"] == "doctor"
    assert set(payload["results"]) == {"claude"}


def test_recover_codex_defaults_to_a_read_only_preview(tmp_path: Path) -> None:
    codex_dir = tmp_path / "home" / ".codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "config.toml").write_text("", encoding="utf-8")

    result = run_ablatify(tmp_path, "recover", "codex")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "recover" in result.stdout.lower() or "transaction" in result.stdout.lower()


def test_restore_hooks_codex_restores_the_isolated_file(tmp_path: Path) -> None:
    codex_dir = tmp_path / "home" / ".codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "config.toml").write_text("", encoding="utf-8")
    disabled = codex_dir / "hooks.json.disabled"
    disabled.write_text('{"hooks": []}\n', encoding="utf-8")

    result = run_ablatify(tmp_path, "restore-hooks", "codex")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (codex_dir / "hooks.json").read_text(encoding="utf-8") == '{"hooks": []}\n'
    assert not disabled.exists()


def test_restore_claude_previews_then_restores_an_explicit_backup(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    backup = tmp_path / "CLAUDE.md.bak"
    target.write_text("current\n", encoding="utf-8")
    backup.write_text("previous\n", encoding="utf-8")

    preview = run_ablatify(
        tmp_path, "restore", "claude", "--target-file", str(target), "--backup", str(backup)
    )
    assert preview.returncode == 0, preview.stdout + preview.stderr
    assert target.read_text(encoding="utf-8") == "current\n"

    applied = run_ablatify(
        tmp_path,
        "restore",
        "claude",
        "--target-file",
        str(target),
        "--backup",
        str(backup),
        "--yes",
    )
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert target.read_text(encoding="utf-8") == "previous\n"


def test_external_instruction_file_is_given_to_both_providers(tmp_path: Path) -> None:
    codex_dir = tmp_path / "home" / ".codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "config.toml").write_text("", encoding="utf-8")
    instruction = tmp_path / "team.md"
    instruction.write_text("# Team profile\n\nShared rules.\n", encoding="utf-8")

    result = run_ablatify(tmp_path, "deploy", "all", "--file", str(instruction), "--yes")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (codex_dir / "gpt-unrestricted.md").read_text(encoding="utf-8") == instruction.read_text(
        encoding="utf-8"
    )
    assert (
        tmp_path / "home" / ".claude" / "keysmith" / "claude-project-rules.md"
    ).read_text(encoding="utf-8") == instruction.read_text(encoding="utf-8")


def test_status_supports_explicit_chinese_and_english_text(tmp_path: Path) -> None:
    chinese = run_ablatify(tmp_path, "status", "claude", "--lang", "zh-CN")
    english = run_ablatify(tmp_path, "status", "claude", "--lang", "en")

    assert chinese.returncode == 0, chinese.stderr
    assert "Ablatify 状态" in chinese.stdout
    assert english.returncode == 0, english.stderr
    assert "Ablatify status" in english.stdout


def test_default_operation_output_is_concise_and_verbose_is_opt_in(tmp_path: Path) -> None:
    concise = run_ablatify(tmp_path, "deploy", "claude", "--dry-run", "--lang", "en")
    verbose = run_ablatify(
        tmp_path, "deploy", "claude", "--dry-run", "--lang", "en", "--verbose"
    )

    assert concise.returncode == 0, concise.stderr
    assert "Claude" in concise.stdout and "previewed" in concise.stdout
    assert "instruction bytes" not in concise.stdout
    assert verbose.returncode == 0, verbose.stderr
    assert "instruction bytes" in verbose.stdout


def test_target_option_alias_and_provider_specific_validation_are_friendly(tmp_path: Path) -> None:
    status = run_ablatify(tmp_path, "status", "--target", "claude", "--format", "json")
    invalid = run_ablatify(tmp_path, "deploy", "codex", "--project-dir", str(tmp_path))

    assert status.returncode == 0, status.stderr
    assert set(json.loads(status.stdout)["results"]) == {"claude"}
    assert invalid.returncode == 2
    assert "--project-dir only applies to Claude" in invalid.stderr
