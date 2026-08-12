# Ablatify domain context

## Confirmed public seams

The implementation is tested only through the user-visible boundaries agreed
for the initial release:

1. The `ablatify` command and `python -m ablatify` entry points.
2. Provider passthrough via `ablatify codex -- ...` and
   `ablatify claude -- ...`.
3. Versioned JSON emitted by `--format json`.
4. The packed npm tarball installed into a clean temporary prefix.

Provider engine behavior remains covered by the vendored upstream functional
test suites. Internal coordinator helpers are not a separate test seam.

