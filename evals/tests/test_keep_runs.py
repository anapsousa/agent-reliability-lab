"""keep_runs copies transcripts out of the repo and never overwrites one."""

import pytest

from evals import keep_runs
from evals.runners.claude_code import REPO


def make_run(root, run="run-1", task="rsch-001", text="{}\n"):
    d = root / run
    d.mkdir(parents=True)
    (d / f"{task}.jsonl").write_text(text, encoding="utf-8")
    return d


def test_copies_new_transcripts_and_is_idempotent(tmp_path):
    src, dest = tmp_path / "runs", tmp_path / "archive"
    make_run(src)
    assert keep_runs.keep(dest, src=src) == (1, 0)
    assert (dest / "run-1" / "rsch-001.jsonl").exists()
    assert keep_runs.keep(dest, src=src) == (0, 1)


def test_refuses_to_overwrite_a_different_transcript(tmp_path):
    src, dest = tmp_path / "runs", tmp_path / "archive"
    make_run(src, text='{"a": 1}\n')
    keep_runs.keep(dest, src=src)
    (src / "run-1" / "rsch-001.jsonl").write_text('{"a": 2}\n', encoding="utf-8")
    with pytest.raises(SystemExit, match="not overwriting"):
        keep_runs.keep(dest, src=src)


def test_refuses_a_destination_inside_the_repo(tmp_path):
    src = tmp_path / "runs"
    make_run(src)
    with pytest.raises(SystemExit, match="inside the repo"):
        keep_runs.keep(REPO / "evals" / "archive", src=src)


def test_only_the_named_run_is_copied(tmp_path):
    src, dest = tmp_path / "runs", tmp_path / "archive"
    make_run(src, run="run-1")
    make_run(src, run="run-2")
    assert keep_runs.keep(dest, run="run-2", src=src) == (1, 0)
    assert not (dest / "run-1").exists()


def test_nothing_to_keep_is_an_error(tmp_path):
    (tmp_path / "runs").mkdir()
    with pytest.raises(SystemExit, match="no transcripts"):
        keep_runs.keep(tmp_path / "archive", src=tmp_path / "runs")
