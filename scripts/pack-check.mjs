import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const npmExecPath = process.env.npm_execpath;
if (!npmExecPath) throw new Error("run this check through `npm run pack:check`");
const metadata = JSON.parse(
  execFileSync(process.execPath, [npmExecPath, "pack", "--json", "--dry-run", "--ignore-scripts"], {
    encoding: "utf8",
  }),
)[0];
const files = new Set(metadata.files.map((entry) => entry.path));

const required = [
  "bin/ablatify.js",
  "src/ablatify/__init__.py",
  "src/ablatify/__main__.py",
  "src/ablatify/cli.py",
  "vendor/codex-keysmith/codex-instruct.py",
  "vendor/codex-keysmith/examples/gpt-unrestricted.md",
  "vendor/codex-keysmith/examples/gpt-overlay.md",
  "vendor/codex-keysmith/LICENSE",
  "vendor/claude-keysmith/claude-instruct.py",
  "vendor/claude-keysmith/examples/claude-project-rules.md",
  "vendor/claude-keysmith/examples/claude-append-prompt.md",
  "vendor/claude-keysmith/LICENSE",
  "README.md",
  "LICENSE",
  "THIRD_PARTY_NOTICES.md",
  "UPSTREAMS.md",
  "package.json",
];
for (const name of required) {
  if (!files.has(name)) throw new Error(`npm tarball is missing ${name}`);
}

// Fixture tests and scenario validators are runtime resources, not our test suite.
const resourceFiles = new Set();
const root = fileURLToPath(new URL("..", import.meta.url));
function requireResourceTree(relative) {
  for (const entry of readdirSync(path.join(root, relative), { withFileTypes: true })) {
    if (entry.name === "__pycache__" || entry.name.endsWith(".pyc")) continue;
    const name = `${relative}/${entry.name}`;
    if (entry.isDirectory()) requireResourceTree(name);
    else {
      resourceFiles.add(name);
      if (!files.has(name)) throw new Error(`npm tarball is missing resource ${name}`);
    }
  }
}
requireResourceTree("vendor/codex-keysmith/scenarios");
requireResourceTree("vendor/codex-keysmith/fixture_packs");

const forbidden = [".github/", "node_modules/", ".git/", "__pycache__/", ".env", "gui/", "ks-envelope.py", "ks-envelope-deploy.py"];
for (const name of files) {
  if ((name.startsWith("tests/") || name.includes("/tests/")) && !resourceFiles.has(name)) {
    throw new Error(`npm tarball contains development test ${name}`);
  }
  if (forbidden.some((part) => name === part || name.startsWith(part) || name.includes(`/${part}`))) {
    throw new Error(`npm tarball contains forbidden path ${name}`);
  }
}

const packageJson = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
for (const lifecycle of ["preinstall", "install", "postinstall", "prepare"]) {
  if (packageJson.scripts?.[lifecycle]) {
    throw new Error(`npm install lifecycle script is forbidden: ${lifecycle}`);
  }
}

process.stdout.write(`npm pack check passed (${files.size} files, ${metadata.size} bytes).\n`);
