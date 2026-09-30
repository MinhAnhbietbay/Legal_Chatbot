"""Load JSON/JSONL exports from VN-Law-Advisor or similar crawlers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.legal_rag.documents import LegalDocument


def _iter_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    payload = json.loads(text)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("documents", "data", "items", "records"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ValueError(f"Unsupported JSON export shape: {path}")


def load_legal_documents(input_path: str | Path) -> list[LegalDocument]:
    """Load one file or all JSON/JSONL files in a folder."""
    path = Path(input_path)
    files = sorted(path.glob("*.json*")) if path.is_dir() else [path]

    docs: list[LegalDocument] = []
    for file_path in files:
        for record in _iter_records(file_path):
            doc = LegalDocument.from_raw(record)
            if doc.content.strip():
                docs.append(doc)
    return docs

