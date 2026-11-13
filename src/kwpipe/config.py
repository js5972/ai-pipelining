"""Load config/project.yaml and hash files."""
import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = "config/project.yaml"


def resolve(path) -> Path:
    """Absolute path; relative paths are taken from the repository root."""
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path) -> str:
    return sha256_bytes(resolve(path).read_bytes())


def load_config(path=DEFAULT_CONFIG) -> dict:
    p = resolve(path)
    raw = p.read_bytes()
    cfg = yaml.safe_load(raw.decode("utf-8"))
    cfg["_path"] = str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
    cfg["_sha256"] = sha256_bytes(raw)
    return cfg
