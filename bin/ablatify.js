#!/usr/bin/env node

"use strict";

const { execFileSync, spawn } = require("node:child_process");
const path = require("node:path");

const packageRoot = path.resolve(__dirname, "..");

function candidates() {
  if (process.env.ABLATIFY_PYTHON) {
    return [{ command: process.env.ABLATIFY_PYTHON, prefix: [] }];
  }
  if (process.platform === "win32") {
    return [
      { command: "py", prefix: ["-3"] },
      { command: "python", prefix: [] },
      { command: "python3", prefix: [] },
    ];
  }
  return [
    { command: "python3", prefix: [] },
    { command: "python", prefix: [] },
  ];
}

function findPython() {
  for (const candidate of candidates()) {
    try {
      const output = execFileSync(
        candidate.command,
        [...candidate.prefix, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
        { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] },
      ).trim();
      const [major, minor] = output.split(".").map(Number);
      if (major > 3 || (major === 3 && minor >= 9)) {
        return candidate;
      }
    } catch {
      // Keep probing the explicit cross-platform candidate list.
    }
  }
  return null;
}

const python = findPython();
if (!python) {
  const checked = candidates().map((item) => [item.command, ...item.prefix].join(" ")).join(", ");
  process.stderr.write(
    `Ablatify needs Python 3.9 or newer. Checked: ${checked}.\n` +
      "Install Python, or set ABLATIFY_PYTHON to a compatible interpreter.\n",
  );
  process.exit(3);
}

const pythonPath = [path.join(packageRoot, "src"), process.env.PYTHONPATH]
  .filter(Boolean)
  .join(path.delimiter);
const child = spawn(
  python.command,
  [...python.prefix, "-m", "ablatify", ...process.argv.slice(2)],
  {
    cwd: process.cwd(),
    env: { ...process.env, PYTHONPATH: pythonPath },
    stdio: "inherit",
  },
);

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    if (!child.killed) child.kill(signal);
  });
}

child.on("error", (error) => {
  process.stderr.write(`Failed to start Python: ${error.message}\n`);
  process.exitCode = 3;
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exitCode = code === null ? 1 : code;
});

