"""Tính Precision@k, Recall@k, MRR cho retrieval pháp lý.

Quy tắc so khớp: so theo `(số hiệu văn bản đã chuẩn hoá, dieu, khoan)`, không so chuỗi
tự do — nhãn của người dùng không bị hỏng khi tiêu đề văn bản đổi.
"""

from __future__ import annotations

import re

from src.legal_rag.documents import LegalChunk
from src.legal_rag.eval.questions import EvalQuestion, GoldEntry
from src.legal_rag.retrieval.bm25_retriever import ScoredChunk


def slugify_doc_number(value: str) -> str:
    """Chuẩn hoá số hiệu văn bản y như `_slugify()` của crawler, rồi hạ chữ thường.

    Nhờ vậy '11/2021/TT-NHNN' trong file câu hỏi khớp doc_id '11-2021-TT-NHNN'.
    """
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()


def chunk_matches(chunk: LegalChunk, gold: GoldEntry) -> bool:
    """Chunk có đúng là đáp án `gold` không. `gold.khoan` rỗng = mọi Khoản đều đúng."""
    if slugify_doc_number(chunk.doc_id) != slugify_doc_number(gold.doc):
        return False
    if str(chunk.metadata.get("dieu", "")) != gold.dieu:
        return False
    if not gold.khoan:
        return True
    return str(chunk.metadata.get("khoan", "")) == gold.khoan


def _is_relevant(chunk: LegalChunk, question: EvalQuestion) -> bool:
    return any(chunk_matches(chunk, gold) for gold in question.relevant)


def precision_at_k(results: list[ScoredChunk], question: EvalQuestion, k: int) -> float:
    if k <= 0:
        return 0.0
    top = results[:k]
    hits = sum(1 for item in top if _is_relevant(item.chunk, question))
    return hits / k


def recall_at_k(results: list[ScoredChunk], question: EvalQuestion, k: int) -> float:
    if not question.relevant:
        return 0.0
    top = [item.chunk for item in results[:k]]
    covered = sum(1 for gold in question.relevant if any(chunk_matches(c, gold) for c in top))
    return covered / len(question.relevant)


def reciprocal_rank(results: list[ScoredChunk], question: EvalQuestion) -> float:
    for rank, item in enumerate(results, start=1):
        if _is_relevant(item.chunk, question):
            return 1.0 / rank
    return 0.0


def question_is_answerable(question: EvalQuestion, chunks: list[LegalChunk]) -> bool:
    """Câu hỏi này có thể trả lời được bằng corpus hiện có không.

    False khi: chưa gắn nhãn (`relevant` rỗng), hoặc nhãn trỏ tới văn bản/Điều không có
    trong corpus. Hai trường hợp đó phải được BÁO RIÊNG, không tính thành 0 điểm — nếu
    tính thành 0 thì một bộ câu hỏi làm dở sẽ trông như retrieval tệ.
    """
    if not question.relevant:
        return False
    return all(any(chunk_matches(chunk, gold) for chunk in chunks) for gold in question.relevant)
