"""Shared document models for legal corpus ingestion and retrieval."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class LegalDocument:
    doc_id: str
    title: str
    content: str
    issuer: str = ""
    doc_type: str = ""
    issued_date: str = ""
    source_url: str = ""
    source_system: str = "vn-law-advisor-export"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "LegalDocument":
        """Create a normalized document from common crawler/export shapes."""
        metadata = dict(raw.get("metadata") or {})
        doc_id = str(
            raw.get("doc_id")
            or raw.get("id")
            or raw.get("law_id")
            or raw.get("document_id")
            or raw.get("url")
            or raw.get("source_url")
            or raw.get("title")
            or "unknown"
        )
        return cls(
            doc_id=doc_id,
            title=str(raw.get("title") or raw.get("name") or raw.get("ten_van_ban") or ""),
            content=str(raw.get("content") or raw.get("text") or raw.get("noi_dung") or ""),
            issuer=str(raw.get("issuer") or raw.get("agency") or raw.get("co_quan_ban_hanh") or ""),
            doc_type=str(raw.get("doc_type") or raw.get("type") or raw.get("loai_van_ban") or ""),
            issued_date=str(raw.get("issued_date") or raw.get("date") or raw.get("ngay_ban_hanh") or ""),
            source_url=str(raw.get("source_url") or raw.get("url") or ""),
            source_system=str(raw.get("source_system") or "vn-law-advisor-export"),
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LegalChunk:
    chunk_id: str
    doc_id: str
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

