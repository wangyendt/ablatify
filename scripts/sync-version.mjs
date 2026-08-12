import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const packageJson = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8"));
const versionFile = path.join(root, "src", "ablatify", "__init__.py");
const original = readFileSync(versionFile, "utf8");
const updated = original.replace(
  /^__version__ = "[^"]+"$/m,
  `__version__ = "${packageJson.version}"`,
);
if (updated === original && !original.includes(`__version__ = "${packageJson.version}"`)) {
  throw new Error("could not locate Ablatify __version__ assignment");
}
writeFileSync(versionFile, updated);

