"""Dependency-light lexical retriever for development and tests."""

from __future__ import annotations

from collections import Counter
from math import log

from src.legal_rag.corpus_filter import normalize_vietnamese
from src.legal_rag.documents import LegalChunk


def tokenize(text: str) -> list[str]:
    return [token for token in normalize_vietnamese(text).split() if len(token) > 2]


class SimpleLegalRetriever:
    """Small TF-IDF-like retriever used before ChromaDB is populated."""

    def __init__(self, chunks: list[LegalChunk]):
        self.chunks = chunks
        self.term_counts = [Counter(tokenize(chunk.content + " " + chunk.title)) for chunk in chunks]
        doc_freq: Counter[str] = Counter()
        for counts in self.term_counts:
            doc_freq.update(counts.keys())
        total = max(1, len(chunks))
        self.idf = {term: log((1 + total) / (1 + freq)) + 1 for term, freq in doc_freq.items()}

    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_filter: list[str] | None = None,
    ) -> list[LegalChunk]:
        query_terms = Counter(tokenize(query))
        scores: list[tuple[float, LegalChunk]] = []
        filters = [normalize_vietnamese(item) for item in doc_filter or []]

        for counts, chunk in zip(self.term_counts, self.chunks, strict=False):
            if filters:
                doc_text = normalize_vietnamese(" ".join([chunk.doc_id, chunk.title, chunk.metadata.get("source", "")]))
                if not any(item in doc_text for item in filters):
                    continue
            score = sum(counts.get(term, 0) * self.idf.get(term, 1.0) for term in query_terms)
            if score > 0:
                scores.append((score, chunk))

        return [chunk for _, chunk in sorted(scores, key=lambda item: item[0], reverse=True)[:top_k]]

