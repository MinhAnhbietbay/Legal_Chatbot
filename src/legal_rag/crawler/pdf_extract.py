"""Extract text from downloaded legal-document PDF attachments.

Most vanban.chinhphu.vn documents have no full text in their HTML detail
page — only a metadata table (see chinhphu_parser.py) plus a link to a PDF
that holds the actual legal text. This module turns those PDF bytes into
plain text.
"""

from __future__ import annotations

import io

from pypdf import PdfReader


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Return concatenated text from every page, or "" if the bytes aren't a readable PDF."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception:
        return ""
    parts: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text:
            parts.append(text)
    return "\n".join(parts).strip()
