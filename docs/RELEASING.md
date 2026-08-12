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
