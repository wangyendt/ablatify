import { execFileSync, execSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const expectedVersion = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8")).version;
const npmExecPath = process.env.npm_execpath;
if (!npmExecPath) throw new Error("run this check through `npm run install:smoke`");
const prefix = mkdtempSync(path.join(tmpdir(), "ablatify-install-"));
let tarball;
try {
  const packed = JSON.parse(
    execFileSync(process.execPath, [npmExecPath, "pack", "--json", "--ignore-scripts"], {
      cwd: root,
      encoding: "utf8",
    }),
  )[0];
  tarball = path.join(root, packed.filename);
  execFileSync(process.execPath, [npmExecPath, "install", "--prefix", prefix, "--ignore-scripts", tarball], {
    stdio: "pipe",
  });
  const executable = path.join(
    prefix,
    "node_modules",
    ".bin",
    process.platform === "win32" ? "ablatify.cmd" : "ablatify",
  );
  const output = (
    process.platform === "win32"
      ? execSync(`"${executable}" --version`, {
          encoding: "utf8",
          shell: process.env.ComSpec || "cmd.exe",
        })
      : execFileSync(executable, ["--version"], { encoding: "utf8" })
  ).trim();
  if (output !== `ablatify ${expectedVersion}`) {
    throw new Error(`unexpected installed CLI version: ${output}`);
  }
  process.stdout.write(`installed tarball smoke test passed: ${output}\n`);
} finally {
  if (tarball) rmSync(tarball, { force: true });
  rmSync(prefix, { recursive: true, force: true });
}
