"""Chunk legal documents while preserving citation metadata."""

from __future__ import annotations

import re

from src.legal_rag.cleaning import strip_page_chrome
from src.legal_rag.documents import LegalChunk, LegalDocument


ARTICLE_PATTERN = re.compile(r"(?=Dieu\s+\d+[\.:])", re.IGNORECASE)


def split_text(text: str, chunk_size: int = 1400, overlap: int = 180) -> list[str]:
    """Split text into overlapping chunks by characters."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        cut = cleaned.rfind(". ", start, end)
        if cut > start + chunk_size // 2:
            end = cut + 1
        chunks.append(cleaned[start:end].strip())
        if end >= len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


def extract_article_hint(text: str) -> str:
    match = re.search(r"Dieu\s+\d+", text, flags=re.IGNORECASE)
    return match.group(0) if match else ""


def chunk_document(doc: LegalDocument, chunk_size: int = 1400, overlap: int = 180) -> list[LegalChunk]:
    cleaned_content = strip_page_chrome(doc.content, title=doc.title)
    pieces = split_text(cleaned_content, chunk_size=chunk_size, overlap=overlap)
    chunks: list[LegalChunk] = []
    for idx, piece in enumerate(pieces):
        metadata = {
            **doc.metadata,
            "source": doc.title,
            "issuer": doc.issuer,
            "doc_type": doc.doc_type,
            "issued_date": doc.issued_date,
            "source_url": doc.source_url,
            "article_hint": extract_article_hint(piece),
        }
        chunks.append(
            LegalChunk(
                chunk_id=f"{doc.doc_id}::chunk-{idx:04d}",
                doc_id=doc.doc_id,
                title=doc.title,
                content=piece,
                metadata=metadata,
            )
        )
    return chunks


def chunk_documents(
    docs: list[LegalDocument],
    chunk_size: int = 1400,
    overlap: int = 180,
) -> list[LegalChunk]:
    chunks: list[LegalChunk] = []
    for doc in docs:
        chunks.extend(chunk_document(doc, chunk_size=chunk_size, overlap=overlap))
    return chunks

