# Upstream sources

Ablatify vendors fixed snapshots of two MIT-licensed projects so installs are
offline and reproducible.

| Provider | Project | Commit |
| --- | --- | --- |
| Codex | [Jia-Ethan/codex-keysmith](https://github.com/Jia-Ethan/codex-keysmith) | `f469195577bb3f9fb408ed9a496b29359ae6fe03` |
| Claude | [Jia-Ethan/claude-keysmith](https://github.com/Jia-Ethan/claude-keysmith) | `8b6a5748b0a3797bcca87e8781748946ead0dc51` |

The vendored engines retain their original filenames, data formats, manifest
names, and managed-block markers for compatibility. Synchronization is a
maintainer-only operation; npm installation and CLI execution never fetch
upstream code.

## 2026-09-20 integration scope

The CLI engines, examples, and selected CLI tests are byte-for-byte snapshots
of the commits above. Codex's optional `scenarios/` and `fixture_packs/` resources
are included for native CLI commands. MIT licenses are unchanged.

Not imported: either GUI, desktop installers/release builders, benchmark runners,
and Codex's `ks-envelope.py` / `ks-envelope-deploy.py` network service. In this
package the source engine has no embedded runtime helpers and its optional
provider-channel hook finds no helper, so ordinary deploy/uninstall stays offline,
does not rewrite provider URLs, and does not install background services. This
boundary is tested at the public CLI and npm tarball levels.

Upstream test selection excludes desktop/release-builder, version-bump, envelope,
and scenario-benchmark-runner suites for components we do not ship; all included
CLI suites run in our macOS/Linux/Windows CI. `tests/fixtures/codex-v0.2.0` is real
historical deployment evidence generated using our previous pinned Codex engine;
our integration test checks its status, overlay upgrade, and uninstall.
