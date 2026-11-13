"""Run folders: one per script execution, with metadata for reproducibility."""
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version

from .config import ROOT, resolve, sha256_file

PACKAGES = ["requests", "pandas", "pyyaml", "pypdf", "scikit-learn", "keybert", "sentence-transformers"]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git(*args):
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _pkg(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _write(path, meta):
    path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")


def start_run(stage: str, cfg: dict, inputs: dict | None = None, resume: str | None = None,
              params: dict | None = None):
    """Create (or reopen with resume=<run_id>) runs/<run_id>/ and write run_metadata.json.

    inputs: {name: path} of files this run reads; their SHA-256 hashes are recorded.
    params: command-line arguments or other run parameters worth recording.
    Returns (run_dir, meta).
    """
    if resume:
        run_dir = ROOT / "runs" / resume
        meta_path = run_dir / "run_metadata.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"No run to resume at {run_dir}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("config_sha256") != cfg["_sha256"]:
            print("WARNING: config/project.yaml changed since this run started.")
        meta.setdefault("resumed_utc", []).append(now_utc())
        _write(meta_path, meta)
        return run_dir, meta

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"_{stage}"
    run_dir = ROOT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    meta = {
        "run_id": run_id,
        "stage": stage,
        "started_utc": now_utc(),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "config_path": cfg["_path"],
        "config_sha256": cfg["_sha256"],
        "config": {k: v for k, v in cfg.items() if not k.startswith("_")},
        "inputs": {name: {"path": str(p), "sha256": sha256_file(p)}
                   for name, p in (inputs or {}).items() if resolve(p).is_file()},
        "params": params or {},
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": {p: _pkg(p) for p in PACKAGES},
    }
    _write(run_dir / "run_metadata.json", meta)
    print(f"Run: {run_id}")
    return run_dir, meta


def finish_run(run_dir, meta: dict, summary: dict):
    meta["finished_utc"] = now_utc()
    meta["summary"] = summary
    _write(run_dir / "run_metadata.json", meta)
    print(json.dumps(summary, indent=2, default=str))
