import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "semble_refresh_search.sh"


def _fake_semble(tmp_path: Path) -> tuple[Path, Path]:
    log_path = tmp_path / "semble-args.txt"
    fake_bin = tmp_path / "semble"
    fake_bin.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$@\" > \"$SEMBLE_ARG_LOG\"\n",
        encoding="utf-8",
    )
    fake_bin.chmod(0o755)
    return fake_bin, log_path


def _run_script(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    fake_bin, log_path = _fake_semble(tmp_path)
    env = {
        **os.environ,
        "SEMBLE_BIN": str(fake_bin),
        "SEMBLE_ARG_LOG": str(log_path),
        "SEMBLE_SKIP_UPGRADE": "1",
    }
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_search_mode_passes_query_path_top_k_and_content(tmp_path: Path) -> None:
    result = _run_script(tmp_path, "search", "memos api client", ".", "7", "all")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "semble-args.txt").read_text(encoding="utf-8").splitlines() == [
        "search",
        "-k",
        "7",
        "memos api client",
        ".",
        "--content",
        "all",
    ]


def test_find_related_mode_passes_file_line_path_top_k_and_content(tmp_path: Path) -> None:
    result = _run_script(
        tmp_path,
        "find-related",
        "src/memosima/memos/probe.py",
        "35",
        ".",
        "4",
        "code",
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "semble-args.txt").read_text(encoding="utf-8").splitlines() == [
        "find-related",
        "-k",
        "4",
        "src/memosima/memos/probe.py",
        "35",
        ".",
        "--content",
        "code",
    ]


def test_missing_arguments_show_usage(tmp_path: Path) -> None:
    result = _run_script(tmp_path)

    assert result.returncode == 64
    assert "Usage:" in result.stderr
