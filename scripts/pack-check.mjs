import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

const metadata = JSON.parse(
  execFileSync("npm", ["pack", "--json", "--dry-run", "--ignore-scripts"], {
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

const forbidden = ["tests/", ".github/", "node_modules/", ".git/", "__pycache__/", ".env"];
for (const name of files) {
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

