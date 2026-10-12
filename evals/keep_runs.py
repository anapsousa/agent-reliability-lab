"""Copy the raw `claude -p` transcripts somewhere that survives a re-clone.

`evals/runs/claude-code/<run_id>/<task>.jsonl` holds every tool call with the full text
it returned. It is gitignored, because it also holds the private context files the agent
read, and the repo is public. The cost of that: the 2026-09-23 baseline transcripts are
gone, and the trace layer had to rebuild each tool output by replaying it against the
frozen corpus (which cannot rebuild `read_context`, nor anything the real run saw that
the replay does not). Run this after every real run.

    uv run python -m evals.keep_runs --dest /path/outside/the/repo
    uv run python -m evals.keep_runs --dest ~/archive --run research-agent-v1-...

The destination must be outside the repo. Files already present are left alone unless
their content differs, in which case the copy stops: a transcript is never overwritten.
Set LAB_RUNS_ARCHIVE to skip --dest. Then point the trace re-score at the copy:

    uv run python -m evals.trace_rescore --runs /path/outside/the/repo
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path

from evals.runners.claude_code import REPO, RUNS


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keep(dest: Path, run: str = "", src: Path = RUNS) -> tuple[int, int]:
    """Copy new transcripts into `dest`. Returns (copied, already_there)."""
    dest = dest.expanduser().resolve()
    if dest == REPO or REPO in dest.parents:
        raise SystemExit(f"refusing {dest}: inside the repo, which is public")
    runs = [d for d in sorted(src.iterdir()) if d.is_dir() and (not run or d.name == run)]
    if not runs:
        raise SystemExit(f"no transcripts to keep under {src}" + (f" for {run}" if run else ""))
    copied = present = 0
    for run_dir in runs:
        for file in sorted(run_dir.glob("*.jsonl")):
            target = dest / run_dir.name / file.name
            if target.exists():
                if _sha(target) != _sha(file):
                    raise SystemExit(f"{target} exists and differs from {file}; not overwriting")
                present += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
            if _sha(target) != _sha(file):
                raise SystemExit(f"copy of {file} does not match its source")
            copied += 1
    return copied, present


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dest", type=Path, default=None)
    parser.add_argument("--run", default="", help="only this run id; default every run")
    args = parser.parse_args(argv)
    dest = args.dest or (
        Path(os.environ["LAB_RUNS_ARCHIVE"]) if "LAB_RUNS_ARCHIVE" in os.environ else None
    )
    if dest is None:
        sys.exit("give --dest, or set LAB_RUNS_ARCHIVE")
    copied, present = keep(dest, args.run)
    print(f"{copied} copied, {present} already there, in {dest.expanduser().resolve()}")


if __name__ == "__main__":
    main()
