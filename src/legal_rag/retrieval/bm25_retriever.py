"""Okapi BM25 tự viết cho corpus pháp luật. Không dependency ngoài.

Khác `SimpleLegalRetriever` (TF-IDF, giữ lại làm baseline) ở hai điểm:
- Trả về `ScoredChunk` mang cả điểm, vì eval cần điểm để tính MRR và Spec B cần nó
  để tính confidence. Retriever cũ bỏ mất điểm.
- Có `metadata_filter` để lọc theo `category`/`year` mà crawler đã ghi vào metadata.

Tokenizer dùng `tokenize_legal()` nên không loại token nào — stopword được BM25 dập
bằng IDF, không bằng danh sách tay (xem spec §3.4).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import log

from src.legal_rag.documents import LegalChunk
from src.legal_rag.text_fold import fold_vietnamese, tokenize_legal


@dataclass
class ScoredChunk:
    chunk: LegalChunk
    score: float


class BM25LegalRetriever:
    """Okapi BM25 với chuẩn hoá độ dài tài liệu."""

    def __init__(self, chunks: list[LegalChunk], k1: float = 1.2, b: float = 0.75) -> None:
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.term_counts: list[Counter[str]] = [
            Counter(tokenize_legal(f"{chunk.content} {chunk.title}")) for chunk in chunks
        ]
        self.doc_lengths: list[int] = [sum(counts.values()) for counts in self.term_counts]
        total_length = sum(self.doc_lengths)
        # Corpus rỗng hoặc mọi chunk rỗng: giữ avgdl = 0.0 và chặn ở search(),
        # không để phép chia cho 0 nổ ra.
        self.avg_doc_length = total_length / len(chunks) if chunks and total_length else 0.0

        doc_freq: Counter[str] = Counter()
        for counts in self.term_counts:
            doc_freq.update(counts.keys())
        total_docs = len(chunks)
        self.idf: dict[str, float] = {
            term: log(1 + (total_docs - freq + 0.5) / (freq + 0.5))
            for term, freq in doc_freq.items()
        }

    def _passes_filters(
        self,
        chunk: LegalChunk,
        doc_filters: list[str],
        metadata_filter: dict[str, str] | None,
    ) -> bool:
        if metadata_filter:
            for key, value in metadata_filter.items():
                if str(chunk.metadata.get(key, "")) != str(value):
                    return False
        if doc_filters:
            haystack = fold_vietnamese(
                " ".join([chunk.doc_id, chunk.title, str(chunk.metadata.get("source", ""))])
            )
            # So khớp theo dạng đã chuẩn hoá: '39/2016/TT-NHNN' phải khớp doc_id
            # '39-2016-TT-NHNN', nên thay mọi ký tự không phải chữ/số bằng '-'.
            if not any(item in haystack for item in doc_filters):
                return False
        return True

    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_filter: list[str] | None = None,
        metadata_filter: dict[str, str] | None = None,
    ) -> list[ScoredChunk]:
        if not self.chunks or not self.avg_doc_length:
            return []

        query_terms = tokenize_legal(query)
        if not query_terms:
            return []

        doc_filters = [
            "-".join(part for part in fold_vietnamese(item).replace("/", "-").split("-") if part)
            for item in doc_filter or []
        ]

        scored: list[ScoredChunk] = []
        for counts, length, chunk in zip(self.term_counts, self.doc_lengths, self.chunks, strict=True):
            if not self._passes_filters(chunk, doc_filters, metadata_filter):
                continue
            score = 0.0
            for term in query_terms:
                freq = counts.get(term, 0)
                if not freq:
                    continue
                denominator = freq + self.k1 * (
                    1 - self.b + self.b * length / self.avg_doc_length
                )
                score += self.idf.get(term, 0.0) * (freq * (self.k1 + 1)) / denominator
            if score > 0:
                scored.append(ScoredChunk(chunk=chunk, score=score))

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]
