"""Persists the mapping of visited document URLs to content hashes between crawl runs.

Stores `url -> content_hash` (sha256 of extracted text) so resumes skip unmodified
documents, re-crawl/update documents whose content has changed on the server, and
add new documents. Supports backward compatibility with legacy list-based state files.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def compute_content_hash(text: str) -> str:
    """Return SHA-256 hex digest of normalized UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_seen(path: Path) -> dict[str, str]:
    """Load visited state mapping url -> content_hash.

    Backward compatible: if `seen` in JSON is a list of URLs (legacy format),
    maps each URL to an empty string `""` so that a subsequent crawl will re-crawl once.
    """
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_seen = data.get("seen", {})
    if isinstance(raw_seen, list):
        return {url: "" for url in raw_seen}
    if isinstance(raw_seen, dict):
        return dict(raw_seen)
    return {}


def save_seen(path: Path, seen: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_seen = dict(sorted(seen.items()))
    path.write_text(json.dumps({"seen": sorted_seen}, ensure_ascii=False, indent=2), encoding="utf-8")
