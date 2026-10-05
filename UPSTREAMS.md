# Upstream sources

Ablatify vendors fixed MIT-licensed upstream sources so installs are offline and
reproducible. Selective backports are recorded separately from base snapshots.

| Provider | Project | Base snapshot |
| --- | --- | --- |
| Codex | [Jia-Ethan/codex-keysmith](https://github.com/Jia-Ethan/codex-keysmith) | `cfcd96eb727c324ee8649170c43aaa632ff53cb3` |
| Claude | [Jia-Ethan/claude-keysmith](https://github.com/Jia-Ethan/claude-keysmith) | `8b6a5748b0a3797bcca87e8781748946ead0dc51` |

The engines retain upstream filenames, data formats, manifest names, and
managed-block markers for compatibility. Synchronization is maintainer-only;
npm installation and CLI execution never fetch upstream code. Copyright and MIT
license notices are preserved.

## 2026-10-05 selective synchronization

- Codex: engine, preset tests, and development prompt-bank runner updated to the
  base snapshot above. Other included upstream resources match that snapshot.
  The runner now requires an explicit `OPENAI_BASE_URL` before reading credentials
  or making HTTP requests; additional local regression tests enforce this order.
  This development runner is not shipped in the npm package.
- Claude: backported status diagnostics and JSON-contract tests from
  `b3d8cc25331e8bbf2b9ccfdbdb658ee01f351663` onto the retained base. The engine
  is therefore **not** a byte-for-byte snapshot of a single upstream commit.
  The backport replaces `paths.agents_file()` with an equivalent read-only path
  check; it does not import the optional agents writer or its install/uninstall
  flags. The selected JSON-contract test file matches the reviewed latest source.
- Reviewed Claude main at `b4988334157606eec96f77061b66756902bace69` but did not
  import its prompt changes, optional agents deployment, or breaktest changes.
  Bundled prompts for both providers remain unchanged from our previous release.
- The unified CLI exposes Codex instruction-slot/preset diagnostics in JSON and
  concise text. Claude's `competing_context` stays in the native JSON details;
  text shows counts and upgrade hints. These are clues, not confirmed conflicts
  or a complete inventory of every instruction source. Upstream's static runtime
  capability flags are reported as upstream metadata, not independently verified.
- `scripts/sync-upstreams.py` checks out base snapshots only. Reproducing the
  Claude integration also requires the selective backport described above.

## Integration boundary retained from 2026-09-20

Included: CLI engines, examples, selected CLI tests, and Codex `scenarios/` and
`fixture_packs/` resources for native commands.

Not imported: either GUI, desktop installers/release builders, benchmark runners
other than the development test dependency above, and Codex's `ks-envelope.py` /
`ks-envelope-deploy.py` network service. The packaged source engine has no embedded
runtime helpers and its optional provider-channel hook finds no helper. Ordinary
deploy/uninstall stays offline, does not rewrite provider URLs, and does not
install background services. Public CLI and npm tarball tests enforce this.

Upstream test selection excludes desktop/release-builder, version-bump, envelope,
and scenario-benchmark-runner suites for components we do not ship; all included
CLI suites run in our macOS/Linux/Windows CI. `tests/fixtures/codex-v0.2.0` contains
historical deployment evidence generated using our previous Codex engine; the
integration suite checks its status, overlay upgrade, and uninstall.
