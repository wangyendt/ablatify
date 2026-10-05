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
        encoding="utf-8",
        errors="replace",
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
    assert "claude-keysmith v7.2" in claude.stdout


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
    assert not (codex_dir / "gpt-overlay.md").exists()


def test_deploy_all_yes_applies_each_provider_default_profile(tmp_path: Path) -> None:
    codex_dir = tmp_path / "home" / ".codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "config.toml").write_text('model = "gpt-5"\n', encoding="utf-8")

    result = run_ablatify(tmp_path, "deploy", "all", "--yes")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (codex_dir / "gpt-overlay.md").is_file()
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
    assert not (codex_dir / "gpt-overlay.md").exists()
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
    assert (codex_dir / "gpt-overlay.md").read_text(encoding="utf-8") == instruction.read_text(
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


def test_reactivate_previews_then_restores_missing_config_field(tmp_path: Path) -> None:
    codex = tmp_path / 'home' / '.codex'
    codex.mkdir(parents=True)
    config = codex / 'config.toml'
    config.write_text('model = "gpt-5"\n', encoding='utf-8')
    assert run_ablatify(tmp_path, 'deploy', 'codex', '--yes').returncode == 0
    config.write_text('model = "gpt-5"\n', encoding='utf-8')
    preview = run_ablatify(tmp_path, 'reactivate', 'codex')
    assert preview.returncode == 0, preview.stdout + preview.stderr
    assert config.read_text() == 'model = "gpt-5"\n'
    applied = run_ablatify(tmp_path, 'reactivate', 'codex', '--yes')
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert 'gpt-overlay.md' in config.read_text()


def test_claude_backups_and_recover_are_exposed_with_native_evidence(tmp_path: Path) -> None:
    assert run_ablatify(tmp_path, 'deploy', 'claude', '--yes').returncode == 0
    assert run_ablatify(tmp_path, 'uninstall', 'claude', '--yes').returncode == 0
    backups = run_ablatify(tmp_path, 'backups', 'claude', '--format', 'json')
    assert backups.returncode == 0, backups.stdout + backups.stderr
    details = json.loads(backups.stdout)['results']['claude']['details']
    assert details['schema'] == 'claude-keysmith/v1'
    assert details['backups']
    recovered = run_ablatify(tmp_path, 'recover', 'claude', '--yes', '--dry-run', '--format', 'json')
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    result = json.loads(recovered.stdout)['results']['claude']
    assert result['outcome'] == 'previewed'
    assert result['details']['mode'] == 'preview'


def test_scoped_restore_rejects_unmanaged_backup(tmp_path: Path) -> None:
    target, backup = tmp_path / 'CLAUDE.md', tmp_path / 'arbitrary.bak'
    target.write_text('current')
    backup.write_text('old')
    result = run_ablatify(tmp_path, 'restore', 'claude', '--scope', 'user',
                          '--target-file', str(target), '--backup', str(backup), '--yes')
    assert result.returncode != 0
    assert target.read_text() == 'current'


def test_packaged_codex_libraries_are_available_through_native_cli(tmp_path: Path) -> None:
    scenarios = run_ablatify(tmp_path, 'codex', '--', '--scenario-list')
    packs = run_ablatify(tmp_path, 'codex', '--', '--scaffold-list')
    assert scenarios.returncode == 0, scenarios.stdout + scenarios.stderr
    assert 'example_fixture' in scenarios.stdout
    assert packs.returncode == 0, packs.stdout + packs.stderr
    assert 'pytest_complete' in packs.stdout


def test_deploy_does_not_change_provider_or_install_network_helper(tmp_path: Path) -> None:
    codex = tmp_path / 'home' / '.codex'
    codex.mkdir(parents=True)
    provider = '\nmodel_provider = "test"\n[model_providers.test]\nname = "test"\nbase_url = "https://example.invalid/v1"\n'
    (codex / 'config.toml').write_text(provider)
    result = run_ablatify(tmp_path, 'deploy', 'codex', '--yes')
    assert result.returncode == 0, result.stdout + result.stderr
    actual = (codex / 'config.toml').read_text()
    assert actual.replace('model_instructions_file = "./gpt-overlay.md"\n', '') == provider
    assert not list((tmp_path / 'home').rglob('*envelope*'))
    assert not (tmp_path / 'home' / 'Library').exists()


def test_historical_codex_deployment_can_upgrade_and_uninstall(tmp_path: Path) -> None:
    import shutil
    codex = tmp_path / 'home' / '.codex'
    shutil.copytree(REPO_ROOT / 'tests' / 'fixtures' / 'codex-v0.2.0', codex)
    manifest = json.loads((codex / '.codex-keysmith-manifest.json').read_text())
    for section in ('config', 'md'):
        entry = manifest[section]
        path = codex / entry['path']
        stamp = entry['after']['mtime_ns']
        os.utime(path, ns=(stamp, stamp))
        if entry.get('backup'):
            path = codex / entry['backup']
            stamp = entry['before']['mtime_ns']
            os.utime(path, ns=(stamp, stamp))
    status = run_ablatify(tmp_path, 'status', 'codex', '--check')
    assert status.returncode == 0, status.stdout + status.stderr
    # First release had no overlay; exercise its genuine manifest and bytes.
    assert manifest['tool_version'] == '0.2.0'
    upgrade = run_ablatify(tmp_path, 'deploy', 'codex', '--yes')
    assert upgrade.returncode == 0, upgrade.stdout + upgrade.stderr
    assert (codex / 'gpt-overlay.md').exists()
    uninstall = run_ablatify(tmp_path, 'uninstall', 'codex', '--yes')
    assert uninstall.returncode == 0, uninstall.stdout + uninstall.stderr


def test_status_check_detects_claude_recovery_residue(tmp_path: Path) -> None:
    assert run_ablatify(tmp_path, 'deploy', 'claude', '--yes').returncode == 0
    residue = tmp_path / 'home' / '.claude' / 'keysmith' / '.journal-corrupt.json'
    residue.write_text('{invalid')
    status = run_ablatify(tmp_path, 'status', 'claude', '--check', '--format', 'json')
    assert status.returncode == 1
    assert json.loads(status.stdout)['results']['claude']['details']['recovery_state']['recovery_required']
    before = residue.read_bytes()
    recovered = run_ablatify(tmp_path, 'recover', 'claude', '--format', 'json')
    assert recovered.returncode != 0
    assert residue.read_bytes() == before


def test_codex_status_surfaces_instruction_diagnostics_read_only(tmp_path: Path) -> None:
    codex_dir = tmp_path / 'home' / '.codex'
    codex_dir.mkdir(parents=True)
    (codex_dir / 'config.toml').write_text('model = "gpt-5"\n', encoding='utf-8')
    deployed = run_ablatify(tmp_path, 'deploy', 'codex', '--yes')
    assert deployed.returncode == 0, deployed.stdout + deployed.stderr
    (codex_dir / 'AGENTS.md').write_text('Project style guide\n', encoding='utf-8')
    before = {p.name: p.read_bytes() for p in codex_dir.iterdir() if p.is_file()}
    result = run_ablatify(tmp_path, 'status', 'codex', '--format', 'json', '--check')
    assert result.returncode == 0, result.stdout + result.stderr
    details = json.loads(result.stdout)['results']['codex']['details']
    assert details['instruction_slot'] == 'model_instructions_file'
    assert details['preset'] == 'overlay'
    assert details['competing_files'] == ['AGENTS.md']
    assert 'current match' in details['measured_default']
    text = run_ablatify(tmp_path, 'status', 'codex', '--lang', 'en')
    assert 'Instruction slot:' in text.stdout
    assert 'not a confirmed conflict' in text.stdout
    assert before == {p.name: p.read_bytes() for p in codex_dir.iterdir() if p.is_file()}


def test_claude_status_surfaces_context_without_enabling_agents(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv('CLAUDE_KEYSMITH_HOME', raising=False)
    root = tmp_path / 'home' / '.claude'
    (root / 'rules').mkdir(parents=True)
    (root / 'rules' / 'style.md').write_text('Style guide\n', encoding='utf-8')
    (root / 'MEMORY.md').write_text('Notes\n', encoding='utf-8')
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    result = run_ablatify(tmp_path, 'status', 'claude', '--format', 'json')
    assert result.returncode == 0, result.stdout + result.stderr
    context = json.loads(result.stdout)['results']['claude']['details']['competing_context']
    assert context['extra_rules'] == ['style.md']
    assert context['project_memory_md'] == [str(root / 'MEMORY.md')]
    assert context['agents_carrier'] is False
    assert context['host_upgrade_required'] is None
    text = run_ablatify(tmp_path, 'status', 'claude', '--lang', 'zh-CN')
    assert '额外配置线索（不代表冲突）: rules=1, MEMORY.md=1' in text.stdout
    assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    help_result = run_ablatify(tmp_path, 'claude', '--', 'install', '--help')
    assert '--agents' not in help_result.stdout


def test_claude_project_context_detects_existing_agent_without_writes(tmp_path: Path) -> None:
    root = tmp_path / '.claude'
    (root / 'agents').mkdir(parents=True)
    (root / 'agents' / 'keysmith.md').write_text('Existing agent\n', encoding='utf-8')
    (root / 'MEMORY.md').write_text('Project notes\n', encoding='utf-8')
    result = run_ablatify(tmp_path, 'status', 'claude', '--scope', 'project', '--project-dir', str(tmp_path), '--format', 'json')
    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)['results']['claude']['details']['competing_context']
    assert context['agents_carrier'] is True
    assert context['project_memory_md'] == [str(root / 'MEMORY.md')]
    assert not (root / 'keysmith').exists()


def test_status_notes_cover_upgrade_and_nondefault_without_changing_health(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(REPO_ROOT / 'src'))
    from ablatify.cli import _status_notes

    details = {
        'instruction_slot': 'model_instructions_file',
        'preset': 'custom',
        'measured_default': 'overlay (current preset=custom; switch to overlay or envelope-append)',
        'competing_files': [],
        'health': 'healthy',
    }
    before = dict(details)
    assert any('differs' in note for note in _status_notes('codex', details, False))
    assert any('不同' in note for note in _status_notes('codex', details, True))
    assert details == before
    claude = {'competing_context': {'host_upgrade_required': True, 'agents_carrier': True}}
    assert 'Runtime configuration needs an upgrade' in _status_notes('claude', claude, False)
    assert 'runtime 配置需要升级' in _status_notes('claude', claude, True)
    assert _status_notes('claude', {}, False) == []
    assert _status_notes('codex', {}, True) == []
