"""Experiment provenance — every result artifact carries its own manifest.

House rule (D45): a result JSON must be sufficient to reconstruct the claim
without the conversation that produced it. `run_manifest()` records commit,
dirty-tree flag, seeds, package versions, GPU, and the hashes of input
artifacts; `wilson_ci()` puts intervals on every headline rate.
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except Exception:
        return ""


def file_hash(path: str | Path, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def run_manifest(seed: int | None = None,
                 inputs: dict[str, str | Path] | None = None,
                 config: dict | None = None) -> dict:
    """Provenance block for a result artifact."""
    import numpy
    versions = {"python": sys.version.split()[0], "numpy": numpy.__version__}
    try:
        import torch
        versions["torch"] = torch.__version__
        if torch.cuda.is_available():
            versions["gpu"] = torch.cuda.get_device_name(0)
    except Exception:
        pass
    m = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit": _git("rev-parse", "HEAD"),
        "dirty": bool(_git("status", "--porcelain")),
        "command": " ".join(sys.argv),
        "seed": seed,
        "platform": platform.platform(),
        "versions": versions,
    }
    if inputs:
        m["input_hashes"] = {k: file_hash(v) for k, v in inputs.items()
                             if Path(v).exists()}
    if config:
        m["config"] = config
    return m


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    hw = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - hw), min(1.0, c + hw))
