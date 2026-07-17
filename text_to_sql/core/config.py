"""
config.py  —  Load and validate config.yaml
"""
import yaml
from pathlib import Path

_ROOT = Path(__file__).parent.parent  # project root


def load() -> dict:
    cfg_path = _ROOT / "config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"config.yaml not found at {cfg_path}")
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    # Resolve relative SQLite path from project root
    if cfg["database"]["type"] == "sqlite":
        db_path = Path(cfg["database"]["path"])
        if not db_path.is_absolute():
            cfg["database"]["path"] = str(_ROOT / db_path)

    return cfg
