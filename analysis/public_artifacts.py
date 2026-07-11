"""Resolve eval artifacts locally, falling back to the public HF dataset."""
from __future__ import annotations

from pathlib import Path


REPO = "JayZenith/Glyph-RLVR-Eval-Results"


def resolve(local: Path, remote_path: str) -> Path:
    if local.exists():
        return local
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise FileNotFoundError(
            f"{local} is absent; install huggingface_hub to download {REPO}/{remote_path}"
        ) from exc
    return Path(hf_hub_download(REPO, remote_path, repo_type="dataset"))
