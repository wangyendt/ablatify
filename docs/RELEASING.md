# Releasing Ablatify

## First release

The first `0.1.0` publication establishes the unscoped npm package. It is done
locally from the exact commit that passed CI:

1. Leave the GitHub repository variable `AUTO_PUBLISH_NPM` unset.
2. Run `npm ci --ignore-scripts && npm run verify`.
3. Run `npm login` and complete npm two-factor authentication.
4. Inspect `npm pack --dry-run`.
5. Run `npm publish --access public`. The local bootstrap release has no
   provenance; subsequent OIDC releases generate it automatically.

## Trusted publishing

After `ablatify@0.1.0` exists, open its npm package settings and add a Trusted
Publisher with these exact values:

```text
Provider: GitHub Actions
Organization or user: wangyendt
Repository: ablatify
Workflow filename: publish-npm.yml
Allowed action: npm publish
```

Then set npm Publishing access to **Require two-factor authentication and
disallow tokens**.

In GitHub, add one Actions repository variable:

```text
AUTO_PUBLISH_NPM=true
```

No repository secret and no long-lived `NPM_TOKEN` are used. The release
workflow commits the next patch version with `GITHUB_TOKEN`, then explicitly
dispatches the OIDC publishing workflow. Only paths that affect the npm
tarball trigger this process.

## Cross-platform release gates

Both release stages call the reusable `ci.yml` workflow, which runs the full
verification suite on macOS, Linux, and Windows with Python 3.9 and 3.14:

1. `release-on-main.yml` verifies the exact triggering SHA before its `bump` job
   can change or push a version. The checkout is pinned to that same SHA.
2. `publish-npm.yml` verifies the exact `expected_sha` release commit before its
   `publish` job can access the OIDC publishing step. This also covers manual
   workflow dispatch and the bot-generated version commit (which does not trigger
   ordinary push CI). A failed, cancelled, or skipped gate blocks its dependent job.

Verification jobs have only `contents: read`, without OIDC or write permissions.
No new repository secrets or variables are required. A separate ordinary CI run
may appear alongside the release gate; neither stage relies on a prior green run
for a different commit. Test-only, workflow-only, and this developer document's
changes still trigger ordinary CI but do not bump or publish an npm version.

The historical Codex fixture originated on macOS. Tests verify its original
bytes/hashes, then adapt only the temporary copy's manifest timestamps to values
read back from the current filesystem. A 100-nanosecond case exercises Windows
FILETIME precision on every CI platform; production fingerprint checks remain
unchanged.
