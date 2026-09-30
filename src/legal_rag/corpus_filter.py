"""Domain filter for Vietnamese banking and credit-law documents."""

from __future__ import annotations

import unicodedata

from src.legal_rag.cleaning import looks_like_noise_document, normalize_vietnamese
from src.legal_rag.documents import LegalDocument


BANKING_KEYWORDS = (
    "tin dung",
    "cho vay",
    "ngan hang",
    "lai suat",
    "bao dam tien vay",
    "the chap",
    "cam co",
    "phan loai no",
    "trich lap du phong",
    "to chuc tin dung",
    "kha nang tra no",
    "han muc tin dung",
)

TARGET_ISSUERS = (
    "ngan hang nha nuoc",
    "chinh phu",
    "quoc hoi",
    "bo tai chinh",
)

TARGET_DOC_HINTS = (
    "39/2016/tt-nhnn",
    "02/2013/tt-nhnn",
    "11/2021/tt-nhnn",
    "31/2024/qh15",
    "cac to chuc tin dung",
)


def is_banking_doc(doc: LegalDocument) -> bool:
    if looks_like_noise_document(doc.title, doc.source_url, doc.content):
        return False

    haystack = normalize_vietnamese(
        " ".join([doc.title, doc.content, doc.issuer, doc.doc_type, doc.source_url])
    )
    issuer_hit = not doc.issuer or any(issuer in haystack for issuer in TARGET_ISSUERS)
    keyword_hit = any(keyword in haystack for keyword in BANKING_KEYWORDS)
    target_doc_hit = any(hint in haystack for hint in TARGET_DOC_HINTS)
    document_shape_hit = (
        "so ky hieu" in haystack
        or "ngay ban hanh" in haystack
        or "docid=" in haystack
        or any(kind in haystack for kind in ("thong tu", "nghi dinh", "quyet dinh", " luat "))
    )
    return issuer_hit and document_shape_hit and (keyword_hit or target_doc_hit)


def filter_banking_docs(docs: list[LegalDocument]) -> list[LegalDocument]:
    return [doc for doc in docs if is_banking_doc(doc)]

