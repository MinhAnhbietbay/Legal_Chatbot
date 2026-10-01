#!/usr/bin/env python3
"""Đo chất lượng retrieval: so BM25 với baseline TF-IDF trên bộ câu hỏi tự gắn nhãn.

Ví dụ:
    python3 scripts/legalrag_eval_retrieval.py \
        --input data/legal/raw \
        --questions docs/eval/retrieval_questions.yaml
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.legal_rag.chunking import chunk_documents
from src.legal_rag.corpus_filter import filter_banking_docs
from src.legal_rag.documents import LegalChunk
from src.legal_rag.eval.metrics import (
    precision_at_k,
    question_is_answerable,
    recall_at_k,
    reciprocal_rank,
)
from src.legal_rag.eval.questions import EvalQuestion, load_questions
from src.legal_rag.ingestion.json_loader import load_legal_documents
from src.legal_rag.retrieval.bm25_retriever import BM25LegalRetriever, ScoredChunk
from src.legal_rag.retrieval.simple_retriever import SimpleLegalRetriever


METRIC_COLUMNS = ("P@1", "P@3", "P@5", "R@5", "R@10", "MRR")


@dataclass
class ReportTable:
    rows: dict[str, dict[str, float]] = field(default_factory=dict)
    used_question_ids: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)
    anchored_share: float = 0.0
    doc_without_article_share: float = 0.0
    chunk_count: int = 0


def corpus_quality(chunks: list[LegalChunk]) -> tuple[float, float]:
    """Trả về (tỉ lệ chunk có neo Điều-Khoản, tỉ lệ văn bản không parse được Điều nào)."""
    if not chunks:
        return 0.0, 0.0
    anchored = sum(1 for c in chunks if c.metadata.get("structure") != "fallback")

    docs_with_article: set[str] = set()
    all_docs: set[str] = set()
    for chunk in chunks:
        all_docs.add(chunk.doc_id)
        if chunk.metadata.get("structure") != "fallback":
            docs_with_article.add(chunk.doc_id)
    without = len(all_docs - docs_with_article)
    return anchored / len(chunks), (without / len(all_docs) if all_docs else 0.0)


def _search(retriever: object, query: str, top_k: int) -> list[ScoredChunk]:
    """Gọi retriever, quy về cùng một dạng kết quả.

    `SimpleLegalRetriever` (baseline) trả về list[LegalChunk] không có điểm, nên bọc lại
    bằng điểm giả giảm dần theo thứ hạng — metric chỉ cần THỨ HẠNG, không cần giá trị điểm.
    """
    results = retriever.search(query, top_k=top_k)  # type: ignore[attr-defined]
    if results and isinstance(results[0], ScoredChunk):
        return results  # type: ignore[return-value]
    return [ScoredChunk(chunk=c, score=float(len(results) - i)) for i, c in enumerate(results)]


def build_report(
    chunks: list[LegalChunk],
    questions: list[EvalQuestion],
    retrievers: dict[str, object],
) -> ReportTable:
    table = ReportTable(chunk_count=len(chunks))
    table.anchored_share, table.doc_without_article_share = corpus_quality(chunks)

    usable: list[EvalQuestion] = []
    for question in questions:
        if not question.relevant:
            table.skipped[question.id] = "chưa gắn nhãn (relevant rỗng)"
        elif not question_is_answerable(question, chunks):
            table.skipped[question.id] = "nhãn trỏ ngoài corpus"
        else:
            usable.append(question)
    table.used_question_ids = [q.id for q in usable]

    for name, retriever in retrievers.items():
        totals = dict.fromkeys(METRIC_COLUMNS, 0.0)
        for question in usable:
            results = _search(retriever, question.question, top_k=10)
            totals["P@1"] += precision_at_k(results, question, 1)
            totals["P@3"] += precision_at_k(results, question, 3)
            totals["P@5"] += precision_at_k(results, question, 5)
            totals["R@5"] += recall_at_k(results, question, 5)
            totals["R@10"] += recall_at_k(results, question, 10)
            totals["MRR"] += reciprocal_rank(results, question)
        count = len(usable)
        table.rows[name] = {k: (v / count if count else 0.0) for k, v in totals.items()}
    return table


def format_report(table: ReportTable) -> str:
    lines = [
        f"Chunk: {table.chunk_count}",
        f"Câu hỏi dùng được: {len(table.used_question_ids)}",
    ]
    if table.skipped:
        lines.append("Câu hỏi bị bỏ qua (KHÔNG tính thành 0 điểm):")
        for qid, reason in table.skipped.items():
            lines.append(f"  - {qid}: {reason}")
    lines.append("")
    header = "retriever".ljust(12) + "".join(col.rjust(8) for col in METRIC_COLUMNS)
    lines.append(header)
    for name, metrics in table.rows.items():
        lines.append(name.ljust(12) + "".join(f"{metrics[col]:8.3f}" for col in METRIC_COLUMNS))
    lines.append("")
    lines.append(f"Chunk có neo Điều-Khoản chính xác: {table.anchored_share:.1%}")
    lines.append(f"Văn bản không parse được Điều nào : {table.doc_without_article_share:.1%}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/legal/raw", help="File hoặc thư mục JSON/JSONL")
    parser.add_argument("--questions", default="docs/eval/retrieval_questions.yaml")
    parser.add_argument("--max-chunk-chars", type=int, default=1400)
    parser.add_argument("--chunk-overlap", type=int, default=180)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    docs = filter_banking_docs(load_legal_documents(args.input))
    chunks = chunk_documents(
        docs, max_chunk_chars=args.max_chunk_chars, chunk_overlap=args.chunk_overlap
    )
    questions = load_questions(args.questions)
    retrievers = {
        "TF-IDF": SimpleLegalRetriever(chunks),
        "BM25": BM25LegalRetriever(chunks),
    }
    print(format_report(build_report(chunks, questions, retrievers)))


if __name__ == "__main__":
    main()
