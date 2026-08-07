"""Self-update support: `rail update` command + first-run-of-day auto-update.

Two layouts are supported:

- **installed** — installed by ``install.sh``: the package lives at
  ``PREFIX/lib/rail-cli/rail_cli/`` next to ``.install-meta``, which records the
  original ``PREFIX`` and the git clone path (``REPO``). Updating delegates to
  ``install.sh --prefix <PREFIX> --update`` (git pull + reinstall to the same
  place, so the installed copy never falls behind the repo).
- **repo** — running from the git clone itself (or a pip editable install):
  the package's parent directory is the repo root. Updating is a plain
  ``git pull --ff-only origin main``.

Auto-update (env ``AUTO_UPDATE``, default on) runs at most once per calendar
day: a marker file at ``$XDG_CACHE_HOME/rail-cli/last-auto-update`` (default
``~/.cache/rail-cli/``) records the day the check was last attempted. The
marker is written *before* the update runs, so concurrent processes and
re-entrant calls (e.g. install.sh's verify step) see the day as already
checked. All auto-update output goes to stderr so stdout JSON is never
corrupted.
"""

from __future__ import annotations

import datetime
import os
import pathlib
import subprocess
import sys

REPO_REMOTE_PATTERN = "rail-cli"  # must match install.sh
AUTO_UPDATE_OFF = {"0", "false", "no", "off", "n", "disabled"}


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def marker_path() -> pathlib.Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return pathlib.Path(base) / "rail-cli" / "last-auto-update"


def auto_update_enabled() -> bool:
    """AUTO_UPDATE defaults to on; explicit off values disable it."""
    val = os.environ.get("AUTO_UPDATE")
    if val is None or val.strip() == "":
        return True
    return val.strip().lower() not in AUTO_UPDATE_OFF


def _today() -> str:
    return datetime.date.today().strftime("%Y%m%d")


def reserve_today() -> None:
    """Mark today as already checked (after a successful manual `rail update`)."""
    path = marker_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_today())
    except OSError:
        pass


def check_and_reserve_today() -> bool:
    """True if this is the day's first run — the caller should update now.

    Returns False if the marker already holds today's date, or if the cache
    dir is unwritable (auto-update degrades to a silent no-op).
    """
    path = marker_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a+", encoding="utf-8") as f:
            try:
                import fcntl

                fcntl.flock(f, fcntl.LOCK_EX)
            except ImportError:
                pass  # non-POSIX fallback: best effort
            f.seek(0)
            if f.read().strip() == _today():
                return False
            f.seek(0)
            f.truncate()
            f.write(_today())
            f.flush()
            return True
    except OSError:
        return False


def _read_meta(meta_file: pathlib.Path) -> dict:
    info = {}
    try:
        for line in meta_file.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                info[k.strip()] = v.strip()
    except OSError:
        pass
    return info


def _is_railgo_repo(path: pathlib.Path) -> bool:
    """True if `path` is a git repo whose origin is the rail-cli repo."""
    if not (path / ".git").exists():
        return False
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0 and REPO_REMOTE_PATTERN in out.stdout


def detect_install() -> dict | None:
    """Locate the install layout; None means self-update is impossible
    (e.g. a plain pip copy with no repo and no install metadata)."""
    pkg_dir = pathlib.Path(__file__).resolve().parent
    meta_file = pkg_dir.parent / ".install-meta"
    if meta_file.exists():
        info = _read_meta(meta_file)
        return {
            "mode": "installed",
            "repo": pathlib.Path(info.get("REPO", "")),
            "prefix": info.get("PREFIX", ""),
            "meta": meta_file,
        }
    root = pkg_dir.parent
    if (root / ".git").exists():
        return {"mode": "repo", "repo": root, "prefix": "", "meta": None}
    return None


def resolve_repo(info: dict | None) -> pathlib.Path | None:
    """The repo to update from: meta REPO, else the cwd (healing stale meta).

    The cwd fallback repairs installs whose ``.install-meta`` predates the
    REPO field: running `rail update` from inside the clone records it.
    """
    repo = info["repo"] if info else None
    if repo and _is_railgo_repo(repo):
        return repo
    if info is None:
        return None
    cwd = pathlib.Path.cwd()
    if _is_railgo_repo(cwd):
        if info.get("meta") is not None:
            try:
                lines = [l for l in info["meta"].read_text(encoding="utf-8").splitlines()
                         if not l.startswith("REPO=")]
                lines.append(f"REPO={cwd}")
                info["meta"].write_text("\n".join(lines) + "\n", encoding="utf-8")
            except OSError:
                pass
        return cwd
    return None


def _head(repo: pathlib.Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _run_update_cmd(cmd: list[str], cwd: pathlib.Path, timeout: int) -> tuple[int, str]:
    """Run the update helper, forwarding its output to OUR stderr.

    install.sh info lines and `git pull` summaries go to their own stdout;
    without this the auto-update would pollute the CLI's stdout right before
    the API command's JSON output. Returns (returncode, error_hint).
    """
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 1, "执行超时（网络或安装卡住？请重试）"
    except (OSError, subprocess.SubprocessError) as e:
        return 1, f"执行失败: {e}"
    if proc.stdout:
        print(proc.stdout, end="", file=sys.stderr)
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    return proc.returncode, ""


def _update_repo(repo: pathlib.Path) -> tuple[int, str]:
    """Repo mode: plain git pull."""
    before = _head(repo)
    rc, err = _run_update_cmd(["git", "pull", "--ff-only", "origin", "main"], repo, 120)
    if rc != 0:
        return rc, err or "git pull 失败（如有本地改动请先 git stash / git commit）"
    after = _head(repo)
    if after and after != before:
        return 0, f"已更新到 {after}"
    return 0, "已是最新版本"


def _update_installed(repo: pathlib.Path, prefix: str) -> tuple[int, str]:
    """Installed mode: delegate to install.sh --update (pull + reinstall)."""
    script = repo / "install.sh"
    if not script.is_file():
        return 1, f"仓库内未找到 install.sh: {script}"
    cmd = ["bash", str(script)]
    if prefix:
        cmd += ["--prefix", prefix]
    cmd += ["--update"]
    rc, err = _run_update_cmd(cmd, repo, 600)
    if rc != 0:
        return rc, err or "更新失败（见上方错误信息）"
    return 0, "更新完成"


def run_update() -> tuple[int, str]:
    """Perform the update. Returns (exit_code, summary message)."""
    info = detect_install()
    if info is None:
        return 1, "未找到 rail-cli 仓库或安装元数据，无法更新。请从 git clone 的仓库运行 ./install.sh 安装。"
    repo = resolve_repo(info)
    if repo is None:
        return 1, "未找到 rail-cli 仓库（记录的路径或当前目录都不是）。请进入仓库目录后运行 rail update，或重新 ./install.sh 安装。"
    if info["mode"] == "installed":
        return _update_installed(repo, info["prefix"])
    return _update_repo(repo)


def maybe_auto_update() -> None:
    """First-run-of-day auto-update. Never raises, never writes stdout."""
    if not auto_update_enabled():
        return
    if not check_and_reserve_today():
        return
    code, msg = run_update()
    if code == 0:
        _log(msg)
    else:
        _log(f"自动更新失败: {msg}（可稍后运行 rail update 手动重试）")
