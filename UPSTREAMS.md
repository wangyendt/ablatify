# Upstream sources

Ablatify vendors fixed snapshots of two MIT-licensed projects so installs are
offline and reproducible.

| Provider | Project | Commit |
| --- | --- | --- |
| Codex | [Jia-Ethan/codex-keysmith](https://github.com/Jia-Ethan/codex-keysmith) | `d7d53fb1ba2f754545c03d0e584adfc46d0a091b` |
| Claude | [Jia-Ethan/claude-keysmith](https://github.com/Jia-Ethan/claude-keysmith) | `eedde121d28117ff500915b05d27ff0245a4b26e` |

The vendored engines retain their original filenames, data formats, manifest
names, and managed-block markers for compatibility. Synchronization is a
maintainer-only operation; npm installation and CLI execution never fetch
upstream code.
