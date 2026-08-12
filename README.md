# Ablatify

Unified, offline instruction profiles for Codex and Claude.

> Ablatify is an independent derivative project. It is not affiliated with or
> endorsed by OpenAI, Anthropic, or Jia-Ethan's Keysmith series.

## Thanks and attribution

Ablatify exists because of the careful work in these two MIT-licensed projects:

- [Jia-Ethan/codex-keysmith](https://github.com/Jia-Ethan/codex-keysmith)
- [Jia-Ethan/claude-keysmith](https://github.com/Jia-Ethan/claude-keysmith)

Thank you to Jia-Ethan and the upstream contributors. Their engines are
vendored at fixed commits, with their original copyright and MIT license
notices preserved. See [UPSTREAMS.md](UPSTREAMS.md) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Requirements

- Node.js 20 or newer
- Python 3.9 or newer
- Codex and/or Claude Code already installed when using the corresponding
  provider

## Install

```bash
npm install --global ablatify
ablatify
```

The npm installation has no install lifecycle scripts and does not change any
Codex, Claude, shell, or user configuration. If Python is not on `PATH`, point
the launcher to it:

```bash
ABLATIFY_PYTHON=/path/to/python3 ablatify --version
```

## Common commands

```bash
# Concise, read-only status for both providers
ablatify
ablatify status
ablatify status codex
ablatify status claude

# Preview, then confirm interactively in a terminal
ablatify deploy codex
ablatify deploy claude
ablatify deploy all

# Non-interactive automation
ablatify deploy all --yes
ablatify uninstall all --yes

# Machine-readable output
ablatify status --format json
ablatify deploy all --dry-run --format json

# Diagnostics and recovery
ablatify recover codex
ablatify restore-hooks codex
ablatify doctor claude
ablatify restore claude --target-file ./CLAUDE.md --backup ./CLAUDE.md.bak --yes
```

`status` defaults to both providers. Mutating commands require an explicit
`codex`, `claude`, or `all` target. `all` runs each provider independently; if
only one succeeds, Ablatify returns exit code `4` and reports `partial` in JSON.

### Claude scopes

Claude defaults to the global `user` scope:

```bash
ablatify deploy claude                       # --scope user
ablatify deploy claude --scope project      # current directory
ablatify deploy claude --scope local        # current directory
ablatify deploy claude --scope project --project-dir /path/to/project
```

Project and local scopes cannot reuse the same managed instruction name in one
project because both upstream scopes share one instruction directory. Choose a
different `--name` when both scopes are needed.

### Advanced provider options

Common options include `--file`, `--name`, `--codex-dir`, `--project-dir`,
`--runtime`, `--append-file`, `--max-tokens`, `--skip-hooks-isolation`,
`--dry-run`, `--yes`, `--verbose`, `--lang auto|zh-CN|en`, and
`--format text|json`. Run command-specific help for the exact set.

Every original upstream option remains available through native passthrough:

```bash
ablatify codex -- --help
ablatify claude -- --help
```

## Built-in and external profiles

Without `--file`, each provider uses its own upstream bundled profile. They are
not merged or substituted for one another. With `--target all --file FILE`,
the same explicit file is handed to both engines, and each engine retains its
own deployment semantics. Claude runtime injection still uses its separate
append profile unless `--append-file` is supplied.

## Local changes and privacy

Ablatify has no telemetry, update check, prompt download, or other runtime
network access. It can change the following local files only after an explicit
command:

- Codex: the selected `.codex` directory, including `config.toml`, the managed
  Markdown profile, manifest/transaction evidence, and hook isolation files.
- Claude: user or project `CLAUDE.md`/`CLAUDE.local.md` files and
  `.claude/keysmith` instruction files.
- Claude `--runtime` only: `~/.claude/settings.json`, prompt files, and the
  supported zsh or PowerShell profile wrapper.

Use `--dry-run` before automation. Both upstream engines create backups, and
Codex retains its durable transaction/recovery behavior. Runtime behavior and
exact file formats remain documented by the linked upstream projects.

## Exit codes

| Code | Meaning |
| ---: | --- |
| 0 | All selected providers succeeded, or a read-only preview/status completed |
| 1 | State conflict or operation failure |
| 2 | Invalid CLI arguments |
| 3 | Python 3.9+ is unavailable |
| 4 | Some, but not all, selected providers succeeded |

`ablatify status` treats `not-installed` as a normal state. Use
`ablatify status --check` when CI should return nonzero for a missing or
unhealthy installation.

## Development

```bash
python -m pip install 'pytest>=7.4,<9'
npm ci --ignore-scripts
npm run verify
```

Tests exercise the public CLI, native passthrough, JSON protocol, npm launcher,
clean tarball installation, and the vendored upstream functional suites.

## 中文简介

Ablatify 将 Codex 与 Claude 的指令配置整合到一个离线 CLI 中。默认运行
`ablatify` 只读取双方状态；执行部署、卸载或恢复前会预览变更，自动化环境需
显式添加 `--yes`。npm 安装阶段不会修改任何用户配置，也不会自动下载运行时。

全局 Claude 配置可直接执行：

```bash
ablatify deploy claude
```

同时启用双方：

```bash
ablatify deploy all --yes
```

项目特别感谢并保留
[codex-keysmith](https://github.com/Jia-Ethan/codex-keysmith) 与
[claude-keysmith](https://github.com/Jia-Ethan/claude-keysmith) 的 MIT 授权及
原作者信息；Ablatify 是独立衍生项目，并非其官方系列成员。

## License

Ablatify is MIT licensed. Vendored upstream components remain covered by their
included MIT licenses.
