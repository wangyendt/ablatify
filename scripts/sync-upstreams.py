#!/usr/bin/env python3
"""Maintainer-only helper for reviewing and importing fixed upstream commits."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile


UPSTREAMS = {
    "codex": (
        "https://github.com/Jia-Ethan/codex-keysmith.git",
        "d7d53fb1ba2f754545c03d0e584adfc46d0a091b",
    ),
    "claude": (
        "https://github.com/Jia-Ethan/claude-keysmith.git",
        "eedde121d28117ff500915b05d27ff0245a4b26e",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=UPSTREAMS)
    parser.add_argument("--commit", help="commit to inspect; defaults to the pinned commit")
    parser.add_argument("--destination", type=Path, help="copy checkout here after verification")
    options = parser.parse_args()
    url, pinned = UPSTREAMS[options.provider]
    commit = options.commit or pinned
    with tempfile.TemporaryDirectory(prefix="ablatify-upstream-") as temporary:
        checkout = Path(temporary) / "repo"
        subprocess.run(["git", "clone", "--quiet", url, str(checkout)], check=True)
        subprocess.run(["git", "-C", str(checkout), "checkout", "--quiet", commit], check=True)
        resolved = subprocess.check_output(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
        ).strip()
        print("{} {}".format(options.provider, resolved))
        if options.destination:
            if options.destination.exists():
                raise SystemExit("destination already exists: {}".format(options.destination))
            shutil.copytree(checkout, options.destination, ignore=shutil.ignore_patterns(".git"))
            print("copied review snapshot to {}".format(options.destination))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

