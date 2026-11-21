#!/usr/bin/env python3
"""Numbers for the README and release post: how much went into the tool.

    python3 tools/project-stats.py [--transcripts DIR]

Counts commits, days worked, lines changed, Python lines, tests and the
design spec from the git checkout. With --transcripts (a folder of Claude
Code session transcripts, *.jsonl), also counts the messages and screenshots
sent while building it. Prints a Markdown table.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def transcript_counts(folder: Path) -> tuple[int, int]:
    """(messages, screenshots) typed by the person, not tool results or notices."""
    messages = images = 0
    for f in folder.glob("*.jsonl"):
        for line in f.read_text(errors="replace").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") != "user" or e.get("isMeta") or e.get("isCompactSummary"):
                continue
            content = e.get("message", {}).get("content")
            if isinstance(content, str):
                messages += not content.startswith("<")
            elif isinstance(content, list):
                blocks = [b for b in content if isinstance(b, dict)]
                if any(b.get("type") == "tool_result" for b in blocks):
                    continue
                if any(b.get("type") == "text" and not b["text"].startswith("<") for b in blocks):
                    messages += 1
                    images += sum(b.get("type") == "image" for b in blocks)
    return messages, images


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcripts", type=Path, help="folder of session transcripts (*.jsonl)")
    a = ap.parse_args()
    dates = git("log", "--format=%ad", "--date=short").split()
    added = removed = 0
    for line in git("log", "--shortstat", "--format=").splitlines():
        m_add = re.search(r"(\d+) insertion", line)
        m_del = re.search(r"(\d+) deletion", line)
        added += int(m_add.group(1)) if m_add else 0
        removed += int(m_del.group(1)) if m_del else 0
    py = sum(len((ROOT / f).read_text(errors="replace").splitlines())
             for f in git("ls-files", "*.py").split())
    spec = len((ROOT / "docs" / "design-spec.md").read_text().splitlines())
    r = subprocess.run([sys.executable, "-m", "unittest", "tests.test_generator"], cwd=ROOT,
                       capture_output=True, text=True)
    tests = re.search(r"Ran (\d+) tests", r.stderr)
    rows = [("Commits", f"{len(dates)}, over {len(set(dates))} days ({min(dates)} to {max(dates)})"),
            ("Lines added / removed", f"{added:,} / {removed:,}"),
            ("Python code", f"{py:,} lines"),
            ("Automated tests", tests.group(1) if tests else "?"),
            ("Design spec", f"{spec:,} lines")]
    if a.transcripts:
        messages, images = transcript_counts(a.transcripts)
        rows[:0] = [("Messages", str(messages)), ("Screenshots", str(images))]
    print("| | Count |\n|---|---|")
    for name, value in rows:
        print(f"| {name} | {value} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
